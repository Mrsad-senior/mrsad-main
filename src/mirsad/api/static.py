"""Serving the built dashboard (``index.html``) and approver PWA (``approve.html``) with SPA fallback."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

log = logging.getLogger("mirsad.api")

_API_PREFIXES = ("api", "v1", "mcp", "docs", "redoc", "openapi.json", "healthz")
_NO_CACHE = {"Cache-Control": "no-cache"}


def install_static(app: FastAPI, static_dir: Path) -> None:
    """Mount ``/assets`` and register the catch-all SPA route. Must be called after all API routes."""
    root = static_dir.resolve()
    index = root / "index.html"
    approve = root / "approve.html"
    if (root / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")
    else:
        log.info("static assets not found under %s; serving API only", root)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> Response:
        first = full_path.split("/", 1)[0]
        if first in _API_PREFIXES:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
        if not index.is_file():
            return JSONResponse({
                "name": "Mirsad", "detail": "The web dashboard has not been built.",
                "hint": "cd web && npm install && npm run build:gateway  (outputs to src/mirsad/static/)",
                "api_docs": "/docs", "health": "/healthz"})
        if full_path:
            candidate = (root / full_path).resolve()
            if candidate.is_file() and root in candidate.parents:
                return FileResponse(candidate, headers=_NO_CACHE if candidate.suffix == ".html" else {})
            if "." in full_path.rsplit("/", 1)[-1]:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")  # missing file, not a route
        if (first == "approve") and approve.is_file():
            return FileResponse(approve, headers=_NO_CACHE)
        return FileResponse(index, headers=_NO_CACHE)
