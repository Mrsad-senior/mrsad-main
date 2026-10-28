"""Web Push subscription management for the approver PWA (delivery is done by the approval service)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from mirsad.api.deps import get_components, require_user
from mirsad.api.schemas import ErrorResponses

router = APIRouter(prefix="/api/push", tags=["push"], responses=ErrorResponses.AUTH)


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=16, max_length=256)
    auth: str = Field(min_length=8, max_length=128)


class PushSubscription(BaseModel):
    """The browser's ``PushSubscription.toJSON()`` value."""

    endpoint: str = Field(max_length=1024)
    keys: PushKeys
    expirationTime: float | None = None  # noqa: N815 - browser field name

    @field_validator("endpoint")
    @classmethod
    def _https_only(cls, value: str) -> str:
        # The server POSTs to this URL; other schemes would turn push delivery into an SSRF primitive.
        if not value.startswith("https://"):
            raise ValueError("push endpoint must be an https:// URL")
        return value


class Unsubscribe(BaseModel):
    endpoint: str = Field(max_length=1024)


class VapidKey(BaseModel):
    public_key: str
    enabled: bool


@router.get("/vapid", response_model=VapidKey)
def vapid(request: Request, _user=Depends(require_user())) -> VapidKey:  # noqa: B008
    settings = get_components(request).settings
    return VapidKey(public_key=settings.vapid_public_key,
                    enabled=bool(settings.vapid_public_key and settings.vapid_private_key))


@router.post("/subscribe", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def subscribe(body: PushSubscription, request: Request, user=Depends(require_user())) -> Response:  # noqa: B008
    from mirsad.approvals import save_push_subscription

    comps = get_components(request)
    try:
        save_push_subscription(comps.db, user.username, body.model_dump())
    except (ValueError, LookupError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/unsubscribe", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def unsubscribe(body: Unsubscribe, request: Request, _user=Depends(require_user())) -> Response:  # noqa: B008
    from mirsad.approvals import delete_push_subscriptions

    delete_push_subscriptions(get_components(request).db, [body.endpoint])
    return Response(status_code=status.HTTP_204_NO_CONTENT)
