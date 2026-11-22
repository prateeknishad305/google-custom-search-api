"""A small HTTP service around the Google Custom Search JSON API.

The answer has the same shape as the renderer of the Node project
(``gsearch-renderer``), so a caller can switch between both without touching
the rest of the code:

    GET /api/search?q=rust+async+runtime&num=10
    GET /health
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from .client import GoogleCustomSearchClient
from .config import ConfigurationError, Settings
from .errors import CustomSearchError
from .models import SearchResponse

app = FastAPI(
    title="Google Custom Search API",
    version="1.0.0",
    description="A thin service around the Google Custom Search JSON API.",
)


def build_client() -> GoogleCustomSearchClient:
    """The client of the service, built from the environment."""

    return GoogleCustomSearchClient.from_settings(Settings.from_env())


@app.get("/health")
async def health() -> dict[str, Any]:
    """Says whether the service has the credentials it needs."""

    try:
        Settings.from_env()
    except ConfigurationError as exc:
        return {"status": "degraded", "configured": False, "error": str(exc)}
    return {"status": "ok", "configured": True}


@app.get("/api/search")
async def search(
    q: str = Query(..., description="the query"),
    num: int = Query(10, ge=1, le=100, description="the number of hits"),
    start: int = Query(0, ge=0, description="the first hit of the answer"),
    site: str | None = Query(None, description="only the hits of this host"),
    filetype: str | None = Query(None, description="only the hits of this file type"),
    hl: str | None = Query(None, description="the language of the hits"),
    gl: str | None = Query(None, description="the country of the hits"),
    safe: str | None = Query(None, description="active, passive or off"),
    date_restrict: str | None = Query(None, description="d1, w1, m1 or y1"),
) -> JSONResponse:
    """Searches and answers with the hits of the API."""

    began = time.monotonic()
    try:
        client = build_client()
        answer = await client.search(
            q,
            num=num,
            start=start,
            site_search=site,
            file_type=filetype,
            language=hl,
            country=gl,
            safe=safe,
            date_restrict=date_restrict,
            allow_empty=True,
        )
    except ConfigurationError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "code": "NOT_CONFIGURED",
                "error": str(exc),
                "count": 0,
                "results": [],
            },
        )
    except CustomSearchError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "success": False,
                "code": getattr(exc, "status", None) and f"HTTP_{exc.status}" or "API_ERROR",
                "error": str(exc),
                "count": 0,
                "results": [],
            },
        )

    body = answer.to_dict()
    body.update(
        {
            "success": body["count"] > 0,
            "requested_engine": "google_cse",
            "engine": "google_cse",
            "response_time_ms": int((time.monotonic() - began) * 1000),
        }
    )
    return JSONResponse(status_code=200, content=body)


def main() -> None:
    """Runs the service."""

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
