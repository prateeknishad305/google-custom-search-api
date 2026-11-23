"""Tests of the HTTP service."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google_custom_search import server  # noqa: E402
from google_custom_search.models import SearchHit, SearchResponse  # noqa: E402


def fake_client(monkeypatch, handler) -> None:
    class Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def search(self, query, **kwargs):
            payload = handler(query, kwargs)
            if isinstance(payload, Exception):
                raise payload
            hits = tuple(
                SearchHit.from_serp(item, rank=index + 1)
                for index, item in enumerate(payload.get("results", []))
            )
            return SearchResponse(query=query, hits=hits, total=len(hits), pages_fetched=1)

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(server, "build_client", lambda: Client())


PAGE = {
    "results": [
        {
            "title": "The Async Ecosystem",
            "url": "https://rust-lang.github.io/async-book/08_ecosystem/00_chapter.html",
            "snippet": "A chapter about <b>async</b>.",
        }
    ]
}


def test_health_says_that_the_service_is_ready(monkeypatch):
    with TestClient(server.app) as client:
        answer = client.get("/health")
    assert answer.status_code == 200
    assert answer.json()["configured"] is True
    assert answer.json()["engine"] == "google"


def test_search_answers_with_the_shape_of_the_renderer(monkeypatch):
    fake_client(monkeypatch, lambda query, kwargs: PAGE)
    with TestClient(server.app) as client:
        answer = client.get("/api/search", params={"q": "rust async runtime", "num": 5})
    body = answer.json()
    assert answer.status_code == 200
    assert body["success"] is True
    assert body["engine"] == "google"
    assert body["count"] == 1
    assert body["results"][0]["url"] == "https://rust-lang.github.io/async-book/08_ecosystem/00_chapter.html"
    assert body["results"][0]["snippet"] == "A chapter about async."


def test_search_passes_the_filters_to_the_client(monkeypatch):
    seen: dict = {}

    def handler(query, kwargs):
        seen.update(kwargs)
        return PAGE

    fake_client(monkeypatch, handler)
    with TestClient(server.app) as client:
        answer = client.get(
            "/api/search",
            params={"q": "rust", "site": "github.com", "filetype": "pdf", "hl": "en", "gl": "us"},
        )
    assert answer.status_code == 200
    assert seen["site"] == "github.com"
    assert seen["file_type"] == "pdf"
    assert seen["language"] == "en"
    assert seen["country"] == "us"


def test_search_reports_the_error_of_the_client(monkeypatch):
    from google_custom_search.errors import BlockedError

    fake_client(monkeypatch, lambda query, kwargs: BlockedError("Google answered with a block"))
    with TestClient(server.app) as client:
        answer = client.get("/api/search", params={"q": "rust"})
    assert answer.status_code == 502
    assert answer.json()["success"] is False
