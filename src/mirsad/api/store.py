"""Data access owned by the API layer: policy versions and raw table access for statistics.

Users, agents and push subscriptions are managed through ``mirsad.auth`` / ``mirsad.approvals``.
The ``policies`` and ``audit_events`` tables are reflected with SQLAlchemy Core so this module
depends only on the table/column names fixed in the build spec, not on ORM class names.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    MetaData,
    String,
    Table,
    Text,
    insert,
    inspect,
    select,
    update,
)
from sqlalchemy.engine import Engine

log = logging.getLogger("mirsad.api")


def to_ts(value: Any) -> float | None:
    """Normalise a DB timestamp (float or datetime) to epoch seconds."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.timestamp()
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class Tables:
    """Lazily reflected spec tables sharing the ``Database`` engine."""

    def __init__(self, db: Any) -> None:
        self.db = db
        self._meta = MetaData()
        self._tables: dict[str, Table] = {}
        self._lock = threading.Lock()
        self._engine: Engine | None = None

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            engine = getattr(self.db, "engine", None)
            if engine is None:
                with self.db.session() as session:
                    engine = session.get_bind()
            self._engine = engine
        return self._engine

    @property
    def dialect(self) -> str:
        return self.engine.dialect.name

    def has(self, name: str) -> bool:
        return inspect(self.engine).has_table(name)

    def table(self, name: str) -> Table:
        with self._lock:
            if name not in self._tables:
                self._tables[name] = Table(name, self._meta, autoload_with=self.engine)
            return self._tables[name]

    def now_for(self, table: Table, column: str) -> Any:
        """A 'now' value of the right type for a timestamp column (DateTime or numeric)."""
        col = table.c[column]
        return datetime.now(UTC) if isinstance(col.type, DateTime) else time.time()


# --------------------------------------------------------------------------- policies

_POLICIES_FALLBACK = MetaData()
_policies_table = Table(
    "policies", _POLICIES_FALLBACK,
    Column("version", String(64), primary_key=True),
    Column("yaml_text", Text, nullable=False),
    Column("created_at", Float, nullable=False),
    Column("created_by", String(128)),
    Column("active", Boolean, default=False, nullable=False),
    Column("comment", Text),
)


class PolicyStore:
    """DB-persisted policy versions (content-addressed by the engine's sha256 version)."""

    def __init__(self, tables: Tables) -> None:
        self.tables = tables
        if not tables.has("policies"):  # storage area normally creates it; never fail without it
            log.warning("policies table missing; creating it")
            _POLICIES_FALLBACK.create_all(tables.engine, tables=[_policies_table])

    @property
    def _t(self) -> Table:
        return self.tables.table("policies")

    @staticmethod
    def _row(row: Any, *, with_yaml: bool = True) -> dict[str, Any]:
        m = row._mapping
        out = {"version": m["version"], "created_at": to_ts(m["created_at"]), "created_by": m["created_by"],
               "active": bool(m["active"]), "comment": m["comment"]}
        if with_yaml:
            out["yaml_text"] = m["yaml_text"]
        return out

    def get(self, version: str) -> dict[str, Any] | None:
        with self.tables.engine.connect() as conn:
            row = conn.execute(select(self._t).where(self._t.c.version == version)).first()
        return self._row(row) if row else None

    def get_yaml(self, version: str) -> str | None:
        """Gateway replay hook: version -> YAML text."""
        row = self.get(version)
        return row["yaml_text"] if row else None

    def active(self) -> dict[str, Any] | None:
        with self.tables.engine.connect() as conn:
            row = conn.execute(select(self._t).where(self._t.c.active.is_(True))
                               .order_by(self._t.c.created_at.desc())).first()
        return self._row(row) if row else None

    def active_version(self) -> str | None:
        with self.tables.engine.connect() as conn:
            return conn.execute(select(self._t.c.version).where(self._t.c.active.is_(True))
                                .order_by(self._t.c.created_at.desc())).scalar()

    def list(self) -> list[dict[str, Any]]:
        t = self._t
        cols = [t.c.version, t.c.created_at, t.c.created_by, t.c.active, t.c.comment]
        with self.tables.engine.connect() as conn:
            rows = conn.execute(select(*cols).order_by(t.c.created_at.desc())).all()
        return [self._row(r, with_yaml=False) for r in rows]

    def save(self, version: str, yaml_text: str, *, created_by: str, comment: str | None = None) -> dict[str, Any]:
        """Insert a version if it does not exist yet (versions are immutable)."""
        existing = self.get(version)
        if existing:
            return existing
        t = self._t
        with self.tables.engine.begin() as conn:
            conn.execute(insert(t).values(version=version, yaml_text=yaml_text,
                                          created_at=self.tables.now_for(t, "created_at"),
                                          created_by=created_by, active=False, comment=comment))
        return self.get(version) or {}

    def activate(self, version: str) -> None:
        t = self._t
        with self.tables.engine.begin() as conn:
            if conn.execute(select(t.c.version).where(t.c.version == version)).first() is None:
                raise KeyError(version)
            conn.execute(update(t).where(t.c.version != version).values(active=False))
            conn.execute(update(t).where(t.c.version == version).values(active=True))
