"""Tests of the web search client of Google."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google_custom_search import (  # noqa: E402
    BlockedError,
    EmptyResultsError,
    GoogleSearchClient,
    InvalidRequestError,
)
from tests.fixtures import BLOCKED_HTML, EMPTY_HTML, SERP_HTML  # noqa: E402


class FakeFetcher:
    """The fetcher of the client in the tests: the answer is known."""

    def __init__(self, handler) -> None:
        self.handler = handler
        self.calls: list[dict] = []

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def fetch(self, params: dict, proxy: str = "") -> str:
        self.calls.append(dict(params))
        answer = self.handler(params)
        if isinstance(answer, Exception):
            raise answer
        return answer


def client_with(handler, **kwargs) -> GoogleSearchClient:
    fetcher = FakeFetcher(handler)
    client = GoogleSearchClient(fetcher=fetcher, pool_url="", **kwargs)
    client.fake = fetcher
    return client


def test_build_params_carries_the_query_and_the_filters():
    client = GoogleSearchClient()
    params = client.build_params(
        "rust async",
        num=25,
        start=10,
        site="github.com",
        file_type="pdf",
        language="en",
        country="us",
    )
    assert params["q"] == "rust async github.com"
    assert params["as_sitesearch"] == "github.com"
    assert params["start"] == 10
    assert params["hl"] == "en"
    assert params["gl"] == "us"
    assert params["as_filetype"] == "pdf"
    assert "num" not in params


@pytest.mark.asyncio
async def test_search_answers_with_the_hits_of_the_page():
    client = client_with(lambda params: SERP_HTML)
    answer = await client.search("rust async", num=4)
    assert len(answer.hits) == 4
    assert answer.hits[0].url == "https://rust-lang.github.io/async-book/08_ecosystem/00_chapter.html"
    assert answer.hits[0].rank == 1
    assert answer.hits[0].snippet.startswith("The async book is a chapter")
    assert answer.pages_fetched == 1
    assert answer.engine == "google"
    assert len(client.fake.calls) == 1


@pytest.mark.asyncio
async def test_search_asks_the_pages_of_a_long_answer_at_the_same_time():
    client = client_with(lambda params: SERP_HTML)
    answer = await client.search("rust async", num=20)
    starts = sorted(call["start"] for call in client.fake.calls)
    assert starts == [0, 10]
    assert len(answer.hits) == 4


@pytest.mark.asyncio
async def test_search_keeps_the_hits_of_the_host_that_was_asked_for():
    client = client_with(lambda params: SERP_HTML)
    answer = await client.search("tokio", site="tokio.rs")
    urls = [hit.url for hit in answer.hits]
    assert urls == ["https://tokio.rs/tokio/tutorial/async"]
    assert all("tokio.rs" in url for url in urls)


@pytest.mark.asyncio
async def test_search_reports_a_block_of_google():
    client = client_with(lambda params: BLOCKED_HTML)
    with pytest.raises(BlockedError):
        await client.search("rust async")


@pytest.mark.asyncio
async def test_search_raises_when_the_query_has_no_hit():
    client = client_with(lambda params: EMPTY_HTML)
    with pytest.raises(EmptyResultsError):
        await client.search("rust async")
    answer = await client.search("rust async", allow_empty=True)
    assert answer.hits == ()


@pytest.mark.asyncio
async def test_search_refuses_an_empty_query():
    client = client_with(lambda params: SERP_HTML)
    with pytest.raises(InvalidRequestError):
        await client.search("   ")


@pytest.mark.asyncio
async def test_search_many_keeps_the_answers_that_worked():
    def handler(params):
        if params["q"] == "bad":
            return BlockedError("Google answered with a block")
        return SERP_HTML

    client = client_with(handler)
    answers = await client.search_many(["rust", "bad", "tokio"])
    assert len(answers) == 2
