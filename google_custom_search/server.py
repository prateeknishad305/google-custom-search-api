"""A small HTTP service around the web search of Google.

The answer has the same shape as the renderer of the Node project
(``gsearch-renderer``), so a caller can switch between both without touching
the rest of the code:

    GET /api/search?q=rust+async+runtime&num=10
    GET /health
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from .client import GoogleSearchClient
from .config import ConfigurationError, Settings
from .errors import GoogleSearchError
from .models import SearchResponse

_client: GoogleSearchClient | None = None


def build_client() -> GoogleSearchClient:
    """The client of the service, built from the environment."""

    return GoogleSearchClient.from_settings(Settings.from_env())


def get_client() -> GoogleSearchClient:
    """The client of the service, it is opened once and kept for the service.

    The browser of the client is the slow part of a request: a new client per
    request would open a new browser per request.
    """

    global _client
    if _client is None:
        _client = build_client()
    return _client


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Closes the browser of the client when the service stops."""

    global _client
    yield
    if _client is not None:
        await _client.aclose()
        _client = None


app = FastAPI(
    title="Google Web Search API",
    version="2.0.0",
    description="A thin service around the web search of Google.",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, Any]:
    """Says whether the service is able to search."""

    try:
        settings = Settings.from_env()
    except ConfigurationError as exc:
        return {"status": "degraded", "configured": False, "error": str(exc)}
    return {
        "status": "ok",
        "configured": True,
        "engine": "google",
        "endpoint": settings.endpoint,
    }


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
) -> JSONResponse:
    """Searches and answers with the hits of the result page of Google."""

    began = time.monotonic()
    client: GoogleSearchClient | None = None
    try:
        client = get_client()
        answer = await client.search(
            q,
            num=num,
            start=start,
            site=site,
            file_type=filetype,
            language=hl,
            country=gl,
            safe=safe,
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
    except GoogleSearchError as exc:
        code = f"HTTP_{exc.status}" if getattr(exc, "status", None) else "API_ERROR"
        return JSONResponse(
            status_code=502,
            content={
                "success": False,
                "code": code,
                "error": str(exc),
                "count": 0,
                "results": [],
            },
        )
    finally:
        if client is not None and client is not _client:
            try:
                await client.aclose()
            except Exception:
                pass

    body = answer.to_dict()
    body.update(
        {
            "success": body["count"] > 0,
            "requested_engine": "google",
            "engine": "google",
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
