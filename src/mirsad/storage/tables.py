"""ORM tables (SQLAlchemy 2.0 typed declarative mapping).

Only portable column types are used (Integer, String, Text, Float, Boolean) so the
same schema runs on SQLite (default) and PostgreSQL. Timestamps are UNIX epoch
seconds stored as floats, matching the ``ts``/``created_at`` fields of the shared
pydantic models.
"""

from __future__ import annotations

import time

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

USER_ROLES = ("admin", "approver", "auditor")
USER_LANGS = ("en", "ar")


class Base(DeclarativeBase):
    """Declarative base shared by every Mirsad table."""


class UserRow(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'approver', 'auditor')", name="ck_users_role"),
        CheckConstraint("lang IN ('en', 'ar')", name="ck_users_lang"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    lang: Mapped[str] = mapped_column(String(4), nullable=False, default="en")
    created_at: Mapped[float] = mapped_column(Float, nullable=False, default=time.time)
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    push_subscriptions: Mapped[list[PushSubscriptionRow]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class AgentRow(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    policy_agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False, default=time.time)
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_seen_at: Mapped[float | None] = mapped_column(Float, nullable=True)


class PolicyRow(Base):
    __tablename__ = "policies"

    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    yaml_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False, default=time.time)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditEventRow(Base):
    """One link of the HMAC hash chain. ``seq`` is assigned by the writer, never autoincremented."""

    __tablename__ = "audit_events"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    ts: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    tool: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    call_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    action: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    risk: Mapped[str | None] = mapped_column(String(16), nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)


class ApprovalRow(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    expires_at: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True, default="pending")
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    call_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    tool: Mapped[str] = mapped_column(String(128), nullable=False)
    arguments_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    decision_json: Mapped[str] = mapped_column(Text, nullable=False)
    summary_en: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary_ar: Mapped[str] = mapped_column(Text, nullable=False, default="")
    risk: Mapped[str] = mapped_column(String(16), nullable=False, default="low")
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class PushSubscriptionRow(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    auth: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False, default=time.time)

    user: Mapped[UserRow] = relationship(back_populates="push_subscriptions")
