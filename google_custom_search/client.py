"""Client of the Google Custom Search JSON API.

The API answers ten hits per request. A search of more hits is therefore more
than one request, and those requests do not depend on each other: they are
sent at the same time.

    from google_custom_search import GoogleCustomSearchClient

    client = GoogleCustomSearchClient(api_key="...", cx="...")
    answer = await client.search("rust async runtime", num=25)
    for hit in answer.hits:
        print(hit.url)
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Iterable, Sequence

import httpx

from .config import DEFAULT_ENDPOINT, Settings
from .errors import (
    AuthenticationError,
    CustomSearchError,
    EmptyResultsError,
    QuotaError,
    TransportError,
    error_for_status,
)
from .models import SearchHit, SearchResponse

PAGE_SIZE = 10
USER_AGENT = "google-custom-search-api/1.0"


class GoogleCustomSearchClient:
    """Talks to the Custom Search JSON API."""

    def __init__(
        self,
        api_key: str,
        cx: str,
        *,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 10.0,
        max_results: int = 100,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise AuthenticationError("the API key is empty")
        if not cx:
            raise CustomSearchError("the search engine id is empty")
        self.api_key = api_key
        self.cx = cx
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_results = max_results
        self._http = http_client
        self._owns_client = http_client is None

    @classmethod
    def from_settings(cls, settings: Settings, **kwargs: Any) -> "GoogleCustomSearchClient":
        return cls(
            settings.api_key,
            settings.cx,
            endpoint=settings.endpoint,
            timeout=settings.timeout,
            max_results=settings.max_results,
            **kwargs,
        )

    async def __aenter__(self) -> "GoogleCustomSearchClient":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Closes the connection pool of the client."""

        if self._http is not None and self._owns_client:
            await self._http.aclose()
            self._http = None

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"user-agent": USER_AGENT},
                follow_redirects=True,
            )
        return self._http

    def build_params(
        self,
        query: str,
        *,
        start: int = 0,
        num: int = PAGE_SIZE,
        site_search: str | None = None,
        file_type: str | None = None,
        language: str | None = None,
        country: str | None = None,
        safe: str | None = None,
        date_restrict: str | None = None,
        sort: str | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """The parameters of one request of the API."""

        params: dict[str, Any] = {
            "key": self.api_key,
            "cx": self.cx,
            "q": query,
            "num": max(1, min(int(num), PAGE_SIZE)),
            "start": max(0, int(start)),
        }
        if site_search:
            params["siteSearchFilter"] = site_search
        if file_type:
            params["fileType"] = file_type
        if language:
            params["lr"] = language
        if country:
            params["gl"] = country
        if safe:
            params["safe"] = safe
        if date_restrict:
            params["dateRestrict"] = date_restrict
        if sort:
            params["sort"] = sort
        if extra_params:
            params.update({str(key): value for key, value in extra_params.items() if value is not None})
        return params

    async def search_page(
        self,
        query: str,
        *,
        start: int = 0,
        num: int = PAGE_SIZE,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """One request of the API, the raw answer."""

        params = self.build_params(query, start=start, num=num, **kwargs)
        try:
            response = await self._client().get(self.endpoint, params=params)
        except httpx.HTTPError as exc:
            raise TransportError(f"the API could not be reached: {exc}") from exc
        if response.status_code >= 400:
            payload = _safe_json(response)
            message = _error_message(payload) or f"the API answered HTTP {response.status_code}"
            raise error_for_status(response.status_code, message, payload)
        payload = _safe_json(response)
        if not isinstance(payload, dict):
            raise CustomSearchError("the API did not answer with a JSON object")
        return payload

    async def search(
        self,
        query: str,
        *,
        num: int = PAGE_SIZE,
        start: int = 0,
        site_search: str | None = None,
        file_type: str | None = None,
        language: str | None = None,
        country: str | None = None,
        safe: str | None = None,
        date_restrict: str | None = None,
        sort: str | None = None,
        extra_params: dict[str, Any] | None = None,
        allow_empty: bool = False,
    ) -> SearchResponse:
        """Searches and answers with the hits of the API.

        More than ten hits are more than one request, the requests are sent at
        the same time and the hits are put back in the order of the API.
        """

        text = str(query or "").strip()
        if not text:
            raise CustomSearchError("the query is empty")
        wanted = max(1, min(int(num), self.max_results))
        first = max(0, int(start))
        # The API pages are ten hits, the first page may be cut short.
        offsets = [first + index * PAGE_SIZE for index in range((wanted + PAGE_SIZE - 1) // PAGE_SIZE)]

        began = time.monotonic()
        pages = await asyncio.gather(
            *(
                self.search_page(
                    text,
                    start=offset,
                    num=min(PAGE_SIZE, wanted - (offset - first)),
                    site_search=site_search,
                    file_type=file_type,
                    language=language,
                    country=country,
                    safe=safe,
                    date_restrict=date_restrict,
                    sort=sort,
                    extra_params=extra_params,
                )
                for offset in offsets
            ),
            return_exceptions=True,
        )

        hits: list[SearchHit] = []
        searches: list[dict[str, Any]] = []
        total = 0
        errors: list[BaseException] = []
        for payload in pages:
            if isinstance(payload, BaseException):
                errors.append(payload)
                continue
            total = max(total, int((payload.get("searchInformation") or {}).get("totalResults") or 0))
            for item in payload.get("items") or []:
                if not isinstance(item, dict):
                    continue
                hits.append(SearchHit.from_api(item, rank=len(hits) + 1))
            search = payload.get("search") or {}
            if isinstance(search, dict):
                searches.append(search)

        if errors and not hits:
            raise errors[0]
        if not hits and not allow_empty:
            raise EmptyResultsError(f"the query {text!r} did not answer with a hit")

        hits = hits[:wanted]
        for index, hit in enumerate(hits, start=1):
            hits[index - 1] = SearchHit(
                title=hit.title,
                url=hit.url,
                snippet=hit.snippet,
                display_link=hit.display_link,
                file_format=hit.file_format,
                mime=hit.mime,
                rank=index,
                metags=hit.metags,
                sitelinks=hit.sitelinks,
                pagemap=hit.pagemap,
            )

        return SearchResponse(
            query=text,
            hits=tuple(hits),
            total=total,
            pages_fetched=len(pages) - len(errors),
            duration_ms=int((time.monotonic() - began) * 1000),
            searches=tuple(searches),
        )

    async def search_many(
        self,
        queries: Iterable[str],
        *,
        num: int = PAGE_SIZE,
        **kwargs: Any,
    ) -> list[SearchResponse]:
        """Searches several queries at the same time."""

        texts = [str(query).strip() for query in queries if str(query).strip()]
        results = await asyncio.gather(
            *(self.search(text, num=num, **kwargs) for text in texts),
            return_exceptions=True,
        )
        answers: list[SearchResponse] = []
        for result in results:
            if isinstance(result, BaseException):
                continue
            answers.append(result)
        return answers


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _error_message(payload: dict[str, Any]) -> str:
    error = payload.get("error") or {}
    if isinstance(error, dict):
        message = error.get("message")
        if message:
            return str(message)
        details = error.get("errors")
        if isinstance(details, list) and details:
            first = details[0]
            if isinstance(first, dict) and first.get("message"):
                return str(first["message"])
    return ""


__all__ = [
    "GoogleCustomSearchClient",
    "PAGE_SIZE",
    "SearchHit",
    "SearchResponse",
    "AuthenticationError",
    "CustomSearchError",
    "EmptyResultsError",
    "QuotaError",
    "TransportError",
]
