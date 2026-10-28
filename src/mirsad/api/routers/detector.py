"""Detector playground endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from starlette.concurrency import run_in_threadpool

from mirsad.api.deps import get_components, require_user
from mirsad.api.schemas import ErrorResponses, StrictModel
from mirsad.models import DetectionResult

router = APIRouter(prefix="/api/detector", tags=["detector"], responses=ErrorResponses.AUTH)

MAX_SCAN_CHARS = 100_000


class ScanRequest(StrictModel):
    text: str = Field(max_length=MAX_SCAN_CHARS)


@router.post("/scan", response_model=DetectionResult)
async def scan(body: ScanRequest, request: Request, _user=Depends(require_user())) -> DetectionResult:  # noqa: B008
    detector = get_components(request).detector
    return await run_in_threadpool(detector.scan, body.text)
