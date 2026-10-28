from __future__ import annotations

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateIndex, CreateTable

from mirsad.storage import Base, Database, PolicyRow, PushSubscriptionRow, UserRow

EXPECTED_TABLES = {"users", "agents", "policies", "audit_events", "approvals", "push_subscriptions"}


def test_create_all_creates_every_table_and_is_idempotent(db):
    db.create_all()  # second call must not fail
    assert EXPECTED_TABLES <= set(inspect(db.engine).get_table_names())


def test_audit_events_has_required_indexes(db):
    indexed = {tuple(ix["column_names"]) for ix in inspect(db.engine).get_indexes("audit_events")}
    for column in ("ts", "agent_id", "tool", "action", "session_id", "event_type"):
        assert (column,) in indexed


def test_sqlite_pragmas_wal_and_foreign_keys(db):
    with db.engine.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_session_commits_and_rolls_back(db):
    with db.session() as sess:
        sess.add(PolicyRow(version="a" * 64, yaml_text="version: 1", created_by="test", active=True))
    with pytest.raises(RuntimeError), db.session() as sess:
        sess.add(PolicyRow(version="b" * 64, yaml_text="version: 1", created_by="test"))
        sess.flush()
        raise RuntimeError("boom")
    with db.session() as sess:
        versions = set(sess.scalars(select(PolicyRow.version)).all())
    assert versions == {"a" * 64}


def test_in_memory_database_is_shared_between_sessions():
    mem = Database("sqlite://")
    mem.create_all()
    with mem.session() as sess:
        sess.add(UserRow(username="noura", password_hash="x", role="admin"))
    with mem.session() as sess:
        assert sess.scalar(select(UserRow.username)) == "noura"


def test_role_check_constraint_rejects_unknown_role(db):
    with pytest.raises(IntegrityError), db.session() as sess:
        sess.add(UserRow(username="eve", password_hash="x", role="superuser"))


def test_push_subscriptions_cascade_when_user_deleted(db):
    with db.session() as sess:
        user = UserRow(username="approver1", password_hash="x", role="approver")
        sess.add(user)
        sess.flush()
        sess.add(PushSubscriptionRow(user_id=user.id, endpoint="https://push.example/1", p256dh="k", auth="a"))
    with db.session() as sess:
        sess.execute(text("DELETE FROM users WHERE username = 'approver1'"))  # raw SQL: relies on the FK
    with db.session() as sess:
        assert sess.scalar(select(PushSubscriptionRow.id)) is None


def test_schema_compiles_for_postgresql():
    dialect = postgresql.dialect()
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=dialect))
        assert "CREATE TABLE" in ddl
        for index in table.indexes:
            str(CreateIndex(index).compile(dialect=dialect))


def test_file_database_creates_parent_directory(tmp_path):
    target = tmp_path / "nested" / "dir" / "m.db"
    database = Database(f"sqlite:///{target}")
    database.create_all()
    assert target.exists()
    database.dispose()


def test_empty_url_rejected():
    with pytest.raises(ValueError):
        Database("")
