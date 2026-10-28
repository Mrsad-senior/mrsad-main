"""Engine and session management.

SQLite is the default backend: every new connection gets ``foreign_keys=ON``,
``journal_mode=WAL`` (file databases only: readers never block the audit writer)
and ``synchronous=NORMAL`` (safe with WAL). Any other SQLAlchemy URL, e.g.
``postgresql+psycopg://...``, is passed through unchanged.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from mirsad.storage.tables import Base

log = logging.getLogger("mirsad.storage")

SQLITE_BUSY_TIMEOUT_S = 30.0


class Database:
    """Thin wrapper owning the SQLAlchemy engine and session factory."""

    def __init__(self, url: str) -> None:
        if not url:
            raise ValueError("database url must not be empty")
        self.url = url
        parsed = make_url(url)
        self.is_sqlite = parsed.get_backend_name() == "sqlite"
        self.is_memory = self.is_sqlite and parsed.database in (None, "", ":memory:")

        kwargs: dict[str, Any] = {"future": True}
        if self.is_sqlite:
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": SQLITE_BUSY_TIMEOUT_S}
            if self.is_memory:
                # One shared connection, otherwise every session would see its own empty database.
                kwargs["poolclass"] = StaticPool
            elif parsed.database:
                Path(parsed.database).expanduser().parent.mkdir(parents=True, exist_ok=True)
        else:
            kwargs["pool_pre_ping"] = True

        self.engine: Engine = create_engine(url, **kwargs)
        if self.is_sqlite:
            event.listen(self.engine, "connect", self._sqlite_pragmas)
        self._sessionmaker = sessionmaker(bind=self.engine, expire_on_commit=False)
        log.debug("database engine created for %s", parsed.render_as_string(hide_password=True))

    def _sqlite_pragmas(self, dbapi_conn: Any, _record: Any) -> None:
        cur = dbapi_conn.cursor()
        try:
            cur.execute("PRAGMA foreign_keys=ON")
            if not self.is_memory:
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")
        finally:
            cur.close()

    def create_all(self) -> None:
        """Create every table and index that does not exist yet (idempotent)."""
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Transactional scope: commit on success, roll back on error, always close."""
        sess = self._sessionmaker()
        try:
            yield sess
            sess.commit()
        except BaseException:
            sess.rollback()
            raise
        finally:
            sess.close()

    def dispose(self) -> None:
        """Close pooled connections (tests, shutdown)."""
        self.engine.dispose()

    def __repr__(self) -> str:
        return f"Database({make_url(self.url).render_as_string(hide_password=True)!r})"
