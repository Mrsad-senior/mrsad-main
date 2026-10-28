"""User management (admin). Password hashes are never returned; the last active admin is protected."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from mirsad.api.components import Components, generate_password
from mirsad.api.deps import get_components, require_user
from mirsad.api.schemas import USERNAME_PATTERN, ErrorResponses, Lang, Problem, Role, StrictModel, UserRecord

router = APIRouter(prefix="/api/users", tags=["users"], responses=ErrorResponses.AUTH)
admin = require_user("admin")

MIN_PASSWORD = 10


class UserCreate(StrictModel):
    username: str = Field(pattern=USERNAME_PATTERN)
    role: Role
    password: str | None = Field(default=None, min_length=MIN_PASSWORD, max_length=1024,
                                 description="Omit to have a strong password generated (returned once)")
    display_name: str = Field(default="", max_length=128)
    lang: Lang = "en"


class UserCreated(BaseModel):
    user: UserRecord
    generated_password: str | None = Field(default=None, description="Only present when the server generated it")


class UserPatch(StrictModel):
    role: Role | None = None
    display_name: str | None = Field(default=None, max_length=128)
    lang: Lang | None = None
    disabled: bool | None = None
    password: str | None = Field(default=None, min_length=MIN_PASSWORD, max_length=1024)


def _record(row: Any) -> UserRecord:
    return UserRecord(username=row.username, role=row.role, display_name=row.display_name or "", lang=row.lang,
                      created_at=row.created_at, disabled=bool(row.disabled))


def _get_or_404(comps: Components, username: str) -> Any:
    row = comps.auth.get_user(comps.db, username)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    return row


def _active_admins(comps: Components) -> int:
    return sum(1 for u in comps.auth.list_users(comps.db) if u.role == "admin" and not u.disabled)


@router.get("", response_model=list[UserRecord])
def list_users(request: Request, _user=Depends(admin)) -> list[UserRecord]:  # noqa: B008
    comps = get_components(request)
    return [_record(u) for u in comps.auth.list_users(comps.db)]


@router.post("", response_model=UserCreated, status_code=status.HTTP_201_CREATED,
             responses={409: {"model": Problem}, 422: {"model": Problem}})
def create_user(body: UserCreate, request: Request, user=Depends(admin)) -> UserCreated:  # noqa: B008
    comps = get_components(request)
    if comps.auth.get_user(comps.db, body.username) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Username already exists")
    generated = None if body.password else generate_password()
    try:
        comps.auth.create_user(comps.db, body.username, body.password or generated, body.role,
                               display_name=body.display_name, lang=body.lang)
    except ValueError as exc:  # includes AlreadyExistsError (race with a concurrent create)
        code = status.HTTP_409_CONFLICT if "exists" in str(exc) else status.HTTP_422_UNPROCESSABLE_CONTENT
        raise HTTPException(code, detail=str(exc)) from exc
    comps.audit.append("user.created", payload={"username": body.username, "role": body.role,
                                                 "created_by": user.username})
    return UserCreated(user=_record(_get_or_404(comps, body.username)), generated_password=generated)


@router.patch("/{username}", response_model=UserRecord,
              responses={**ErrorResponses.NOT_FOUND, 409: {"model": Problem}})
def update_user(username: str, body: UserPatch, request: Request, user=Depends(admin)) -> UserRecord:  # noqa: B008
    comps = get_components(request)
    current = _get_or_404(comps, username)
    demotes_admin = current.role == "admin" and not current.disabled and (
        (body.role is not None and body.role != "admin") or body.disabled is True)
    if demotes_admin and _active_admins(comps) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Cannot demote or disable the last active admin")
    changes = body.model_dump(exclude_none=True)
    try:
        updated = comps.auth.update_user(comps.db, username, **changes)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    comps.audit.append("user.updated", payload={
        "username": username, "updated_by": user.username,
        "changes": {k: v for k, v in changes.items() if k != "password"},
        # "*_at" keeps the audit redactor from masking this non-secret fact
        "password_changed_at": time.time() if "password" in changes else None})
    return _record(updated)


@router.delete("/{username}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
               responses={**ErrorResponses.NOT_FOUND, 409: {"model": Problem}})
def delete_user(username: str, request: Request, user=Depends(admin)) -> Response:  # noqa: B008
    comps = get_components(request)
    current = _get_or_404(comps, username)
    if username == user.username:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="You cannot delete your own account")
    if current.role == "admin" and not current.disabled and _active_admins(comps) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Cannot delete the last active admin")
    comps.auth.delete_user(comps.db, username)
    comps.audit.append("user.deleted", payload={"username": username, "deleted_by": user.username})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
