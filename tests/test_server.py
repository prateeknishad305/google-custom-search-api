"""Tests of the HTTP service."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from google_custom_search import server

PAGE = {
    "searchInformation": {"totalResults": "42"},
    "items": [
        {
            "title": "The Async Ecosystem",
            "link": "https://rust-lang.github.io/async-book/08_ecosystem/00_chapter.html",
            "snippet": "A chapter about <b>async</b>.",
        }
    ],
}


def fake_client(monkeypatch, handler) -> None:
    class Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def search(self, query, **kwargs):
            payload = handler(query, kwargs)
            if isinstance(payload, Exception):
                raise payload
            from google_custom_search.models import SearchHit, SearchResponse

            hits = tuple(SearchHit.from_api(item, rank=index + 1) for index, item in enumerate(payload.get("items", [])))
            return SearchResponse(query=query, hits=hits, total=42, pages_fetched=1)

    monkeypatch.setattr(server, "build_client", lambda: Client())


def test_health_without_credentials(monkeypatch):
    monkeypatch.delenv("GOOGLE_CSE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CSE_CX", raising=False)
    with TestClient(server.app) as client:
        answer = client.get("/health")
    assert answer.status_code == 200
    assert answer.json()["configured"] is False


def test_search_answers_with_the_shape_of_the_renderer(monkeypatch):
    fake_client(monkeypatch, lambda query, kwargs: PAGE)
    with TestClient(server.app) as client:
        answer = client.get("/api/search", params={"q": "rust async runtime", "num": 5})
    body = answer.json()
    assert answer.status_code == 200
    assert body["success"] is True
    assert body["engine"] == "google_cse"
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
    assert seen["site_search"] == "github.com"
    assert seen["file_type"] == "pdf"
    assert seen["language"] == "en"
    assert seen["country"] == "us"
