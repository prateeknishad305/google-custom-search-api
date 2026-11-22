"""Tests of the Custom Search JSON API client."""

from __future__ import annotations

import httpx
import pytest

from google_custom_search import (
    AuthenticationError,
    EmptyResultsError,
    GoogleCustomSearchClient,
    InvalidRequestError,
)

PAGE = {
    "kind": "customsearch#search",
    "searchInformation": {"totalResults": "42"},
    "search": {"searchTerms": "rust"},
    "items": [
        {
            "title": "The Async Ecosystem",
            "link": "https://rust-lang.github.io/async-book/08_ecosystem/00_chapter.html",
            "snippet": "A chapter about <b>async</b>.",
            "displayLink": "rust-lang.github.io",
            "fileFormat": "HTML",
            "mime": "text/html",
        },
        {
            "title": "Tokio tutorial",
            "link": "https://tokio.rs/tokio/tutorial/async",
            "snippet": "Learn async.",
            "displayLink": "tokio.rs",
        },
    ],
}


def client_with(handler, **kwargs) -> GoogleCustomSearchClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return GoogleCustomSearchClient("key", "cx", http_client=http_client, **kwargs)


def test_build_params_carries_the_query_and_the_filters():
    client = GoogleCustomSearchClient("key", "cx")
    params = client.build_params(
        "rust async",
        num=25,
        start=10,
        site_search="github.com",
        file_type="pdf",
        language="en",
        country="us",
    )
    assert params["q"] == "rust async"
    assert params["num"] == 10
    assert params["start"] == 10
    assert params["siteSearchFilter"] == "github.com"
    assert params["fileType"] == "pdf"
    assert params["lr"] == "en"
    assert params["gl"] == "us"
    assert params["key"] == "key"
    assert params["cx"] == "cx"


@pytest.mark.asyncio
async def test_search_answers_with_the_hits_of_the_api():
    calls: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        return httpx.Response(200, json=PAGE)

    client = client_with(handler)
    answer = await client.search("rust async", num=2)
    assert len(answer.hits) == 2
    assert answer.hits[0].url == "https://rust-lang.github.io/async-book/08_ecosystem/00_chapter.html"
    assert answer.hits[0].rank == 1
    assert answer.hits[0].snippet == "A chapter about async."
    assert answer.total == 42
    assert answer.pages_fetched == 1
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_search_sends_the_pages_of_a_long_answer_at_the_same_time():
    starts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        starts.append(request.url.params.get("start", ""))
        return httpx.Response(200, json=PAGE)

    client = client_with(handler)
    answer = await client.search("rust async", num=25)
    assert sorted(starts) == ["0", "10", "20"]
    assert len(answer.hits) == 6


@pytest.mark.asyncio
async def test_search_reports_the_error_of_the_api():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "bad request"}})

    client = client_with(handler)
    with pytest.raises(InvalidRequestError):
        await client.search("rust async")


@pytest.mark.asyncio
async def test_search_reports_the_missing_key():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"message": "forbidden"}})

    client = client_with(handler)
    with pytest.raises(AuthenticationError):
        await client.search("rust async")


@pytest.mark.asyncio
async def test_search_raises_when_the_query_has_no_hit():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"searchInformation": {"totalResults": "0"}, "items": []})

    client = client_with(handler)
    with pytest.raises(EmptyResultsError):
        await client.search("rust async")
    answer = await client.search("rust async", allow_empty=True)
    assert answer.hits == ()


@pytest.mark.asyncio
async def test_search_many_keeps_the_answers_that_worked():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("q") == "bad":
            return httpx.Response(400, json={"error": {"message": "bad request"}})
        return httpx.Response(200, json=PAGE)

    client = client_with(handler)
    answers = await client.search_many(["rust", "bad", "tokio"])
    assert len(answers) == 2
