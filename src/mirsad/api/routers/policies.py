"""Policy versions: list, validate, activate (hot-reloads the gateway) and roll back."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from mirsad.api.components import Components, build_engine, policy_agent_names
from mirsad.api.deps import get_components, require_user
from mirsad.api.schemas import ErrorResponses, Problem, StrictModel

log = logging.getLogger("mirsad.api")

router = APIRouter(prefix="/api/policies", tags=["policies"], responses=ErrorResponses.AUTH)
reader = require_user("admin", "auditor")
admin = require_user("admin")

MAX_POLICY_CHARS = 256_000


class PolicyVersion(BaseModel):
    version: str
    created_at: float | None = None
    created_by: str | None = None
    active: bool = False
    comment: str | None = None


class PolicyFull(PolicyVersion):
    yaml_text: str


class PolicyList(BaseModel):
    active: PolicyFull | None
    versions: list[PolicyVersion]


class PolicyText(StrictModel):
    yaml_text: str = Field(min_length=1, max_length=MAX_POLICY_CHARS)


class PolicyActivate(PolicyText):
    comment: str | None = Field(default=None, max_length=500)


class ValidationReport(BaseModel):
    valid: bool
    errors: list[str]


class ActivationResult(PolicyFull):
    previous_version: str | None = None
    mode: str = "enforce"
    agents: list[str] = Field(default_factory=list)


def validate_text(module: Any, yaml_text: str) -> list[str]:
    """Human-readable validation errors ([] when valid) using the policy module's validator."""
    validator = getattr(module, "validate_policy", None)
    if validator is not None:
        return list(validator(yaml_text))
    try:
        module.PolicyEngine.from_yaml(yaml_text)
    except Exception as exc:
        return [str(exc)]
    return []


def activate_engine(request: Request, comps: Components, engine: Any, yaml_text: str, *, user: str,
                    comment: str | None) -> ActivationResult:
    """Persist (if new), mark active, hot-swap the gateway policy and audit ``policy.activated``."""
    gateway = request.app.state.gateway
    previous = getattr(gateway.policy, "version", None)
    comps.policy_store.save(engine.version, yaml_text, created_by=user, comment=comment)
    comps.policy_store.activate(engine.version)
    gateway.set_policy(engine)
    comps.policy = engine
    for agent_id, name in policy_agent_names(engine).items():
        gateway.agent_names.setdefault(agent_id, name)
    mode = str(getattr(getattr(engine, "mode", "enforce"), "value", getattr(engine, "mode", "enforce")))
    comps.audit.append("policy.activated", policy_version=engine.version,
                       payload={"version": engine.version, "previous_version": previous, "activated_by": user,
                                "comment": comment, "mode": mode})
    log.info("policy %s activated by %s", engine.version[:12], user)
    row = comps.policy_store.get(engine.version) or {}
    return ActivationResult(**{**row, "yaml_text": yaml_text, "active": True}, previous_version=previous, mode=mode,
                            agents=list(engine.agent_ids()) if hasattr(engine, "agent_ids") else [])


@router.get("", response_model=PolicyList)
def list_policies(request: Request, _user=Depends(reader)) -> PolicyList:  # noqa: B008
    store = get_components(request).policy_store
    active = store.active()
    return PolicyList(active=PolicyFull(**active) if active else None,
                      versions=[PolicyVersion(**v) for v in store.list()])


@router.post("/validate", response_model=ValidationReport)
def validate(body: PolicyText, request: Request, _user=Depends(admin)) -> ValidationReport:  # noqa: B008
    errors = validate_text(get_components(request).policy_module, body.yaml_text)
    return ValidationReport(valid=not errors, errors=errors)


@router.put("", response_model=ActivationResult, responses={422: {"model": Problem}})
async def activate(body: PolicyActivate, request: Request, user=Depends(admin)) -> ActivationResult:  # noqa: B008
    comps = get_components(request)
    errors = await run_in_threadpool(validate_text, comps.policy_module, body.yaml_text)
    if errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail="Invalid policy: " + "; ".join(errors[:20]))
    try:
        engine = await run_in_threadpool(build_engine, comps.policy_module, body.yaml_text,
                                         request.app.state.gateway.policy)
    except Exception as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Invalid policy: {exc}") from exc
    return await run_in_threadpool(activate_engine, request, comps, engine, body.yaml_text,
                                   user=user.username, comment=body.comment)


@router.get("/{version}", response_model=PolicyFull, responses=ErrorResponses.NOT_FOUND)
def get_policy(version: str, request: Request, _user=Depends(reader)) -> PolicyFull:  # noqa: B008
    row = get_components(request).policy_store.get(version)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Policy version not found")
    return PolicyFull(**row)


@router.post("/{version}/activate", response_model=ActivationResult, responses=ErrorResponses.NOT_FOUND)
async def rollback(version: str, request: Request, user=Depends(admin)) -> ActivationResult:  # noqa: B008
    """Re-activate a stored version (rollback)."""
    comps = get_components(request)
    row = comps.policy_store.get(version)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Policy version not found")
    engine = await run_in_threadpool(build_engine, comps.policy_module, row["yaml_text"],
                                     request.app.state.gateway.policy)
    return await run_in_threadpool(activate_engine, request, comps, engine, row["yaml_text"],
                                   user=user.username, comment=row.get("comment"))
