"""Request/response models of the REST API that are not part of ``mirsad.models``."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["admin", "approver", "auditor"]
Lang = Literal["en", "ar"]

SLUG_PATTERN = r"^[a-z0-9][a-z0-9_-]{1,63}$"
USERNAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.@-]{2,63}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UserOut(BaseModel):
    username: str
    role: Role
    display_name: str = ""
    lang: str = "en"


class UserRecord(UserOut):
    created_at: float | None = None
    disabled: bool = False


class LoginRequest(StrictModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - OAuth2 token type, not a secret
    expires_in: int
    user: UserOut


class AgentOut(BaseModel):
    id: str
    name: str
    description: str = ""
    policy_agent_id: str
    key_prefix: str | None = None
    created_at: float | None = None
    disabled: bool = False
    last_seen_at: float | None = None


class AgentWithKey(BaseModel):
    agent: AgentOut
    api_key: str = Field(description="Shown only once. Store it in a secret manager.")
    warnings: list[str] = Field(default_factory=list)


class Problem(BaseModel):
    detail: str


class ErrorResponses:
    """Shared OpenAPI ``responses=`` fragments."""

    AUTH: dict[int | str, dict[str, Any]] = {401: {"model": Problem, "description": "Not authenticated"},
                                             403: {"model": Problem, "description": "Insufficient role"}}
    AGENT: dict[int | str, dict[str, Any]] = {401: {"model": Problem, "description": "Missing/invalid agent key"}}
    NOT_FOUND: dict[int | str, dict[str, Any]] = {404: {"model": Problem, "description": "Not found"}}
