"""Client of the web search of Google.

Google has no API for a full web search any more, the answer comes from the
result page itself. This client asks that page, reads the hits out of it and
puts the exact destination of every hit in the answer.

    from google_custom_search import GoogleSearchClient

    client = GoogleSearchClient()
    answer = await client.search("rust async runtime", num=25)
    for hit in answer.hits:
        print(hit.url)

The pages of a long answer do not depend on each other: they are asked at the
same time.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from typing import Any, Iterable, Sequence

from .config import DEFAULT_ENDPOINT, DEFAULT_USER_AGENT, Settings
from .dork import enforce_dork, parse_dork, site_as_terms
from .errors import (
    BlockedError,
    EmptyResultsError,
    GoogleSearchError,
    InvalidRequestError,
)
from .fetchers import (
    BrowserFetcher,
    HttpFetcher,
    browser_available,
)
from .models import SearchHit, SearchResponse
from .parser import apply_inline_destinations, extract_results
from .pool import DEFAULT_POOL_URL, ExitPool

PAGE_SIZE = 10
USER_AGENT = DEFAULT_USER_AGENT

BLOCK_MARKERS = (
    "unusual traffic",
    "our systems have detected",
    "/sorry/index",
    "consent.google.com",
    "before you continue to google search",
    "detected unusual traffic",
    "please click here if you are not redirected",
)


class GoogleSearchClient:
    """Talks to the result page of Google."""

    def __init__(
        self,
        *,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 15.0,
        max_results: int = 100,
        proxy: str = "",
        user_agent: str = USER_AGENT,
        hl: str = "en",
        gl: str = "us",
        safe: str = "",
        max_concurrency: int = 4,
        mode: str = "auto",
        browser: str = "chromium",
        executable_path: str = "",
        pool_url: str = DEFAULT_POOL_URL,
        exits_per_search: int = 4,
        race_size: int = 3,
        exits: Sequence[str] | None = None,
        fetcher: Any = None,
    ) -> None:
        if not endpoint:
            raise InvalidRequestError("the endpoint is empty")
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_results = max_results
        self.proxy = proxy
        self.user_agent = user_agent
        self.hl = hl
        self.gl = gl
        self.safe = safe
        self.max_concurrency = max(1, int(max_concurrency))
        self.mode = (mode or "auto").strip().lower()
        self.browser = (browser or "chromium").strip().lower()
        self.executable_path = executable_path or ""
        self.pool_url = pool_url
        self.exits_per_search = max(1, int(exits_per_search))
        self.race_size = max(1, int(race_size))
        self.exits = list(exits or [])
        self._pool = ExitPool(url=pool_url) if pool_url else None
        self._fetcher = fetcher
        self._owns_fetcher = fetcher is None

    @classmethod
    def from_settings(cls, settings: Settings, **kwargs: Any) -> "GoogleSearchClient":
        return cls(
            endpoint=settings.endpoint,
            timeout=settings.timeout,
            max_results=settings.max_results,
            proxy=settings.proxy,
            user_agent=settings.user_agent,
            hl=settings.hl,
            gl=settings.gl,
            safe=settings.safe,
            max_concurrency=settings.max_concurrency,
            mode=kwargs.pop("mode", settings.mode),
            browser=kwargs.pop("browser", settings.browser),
            executable_path=kwargs.pop("executable_path", settings.executable_path),
            pool_url=kwargs.pop("pool_url", settings.pool_url),
            exits_per_search=kwargs.pop("exits_per_search", settings.exits_per_search),
            race_size=kwargs.pop("race_size", settings.race_size),
            **kwargs,
        )

    async def __aenter__(self) -> "GoogleSearchClient":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Closes the browser and the connection pool of the client."""

        if self._fetcher is not None and self._owns_fetcher:
            await self._fetcher.close()
            self._fetcher = None

    def _build_fetcher(self) -> Any:
        """The fetcher of the client: a browser when there is one."""

        mode = self.mode
        if mode == "auto":
            mode = "browser" if browser_available() else "http"
        if mode == "browser":
            return BrowserFetcher(
                endpoint=self.endpoint,
                timeout=self.timeout,
                proxy=self.proxy,
                browser=self.browser,
                executable_path=self.executable_path,
                locale=f"{self.hl}-{self.gl.upper()}",
            )
        return HttpFetcher(
            endpoint=self.endpoint,
            timeout=self.timeout,
            proxy=self.proxy,
            user_agent=self.user_agent,
            hl=self.hl,
        )

    def fetcher(self) -> Any:
        if self._fetcher is None:
            self._fetcher = self._build_fetcher()
        return self._fetcher

    async def _exits(self) -> list[str]:
        """The exits of the request: the next ones of the pool of exits."""

        if self.exits:
            return list(self.exits)
        if not self.pool_url:
            return [self.proxy]
        exits = await self._pool.load()
        if not exits:
            return [self.proxy]
        return self._pool.take(self.exits_per_search)

    def build_params(
        self,
        query: str,
        *,
        start: int = 0,
        num: int = PAGE_SIZE,
        site: str | None = None,
        file_type: str | None = None,
        language: str | None = None,
        country: str | None = None,
        safe: str | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """The parameters of one request to the result page of Google."""

        text = str(query or "").strip()
        if site:
            site = str(site).strip().lower()
            text = f"{text} site:{site}" if text else f"site:{site}"
        dork = parse_dork(text)
        if dork.site_targets and all(_is_host_target(target) for target in dork.site_targets):
            if not _env_flag("GOOGLE_SITE_OPERATOR"):
                text = site_as_terms(text, dork.site_targets).strip()
                if len(dork.site_targets) == 1:
                    params_site = dork.site_targets[0]
                else:
                    params_site = ""
            else:
                params_site = ""
        else:
            params_site = ""

        params: dict[str, Any] = {
            "q": text,
            "start": max(0, int(start)),
            "hl": (language or self.hl or "en").strip(),
            "gl": (country or self.gl or "us").strip(),
        }
        count = max(1, min(int(num), PAGE_SIZE))
        if count != PAGE_SIZE:
            params["num"] = count
        if params_site:
            params["as_sitesearch"] = params_site
        filetypes = list(dork.operators.get("filetype") or [])
        if file_type:
            filetypes.append(str(file_type).strip().lower().lstrip("."))
        if len(set(filetypes)) == 1:
            params["as_filetype"] = filetypes[0]
        safe_value = (safe or self.safe or "").strip()
        if safe_value:
            params["safe"] = safe_value
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
    ) -> list[dict[str, Any]]:
        """One request to the result page of Google, the hits of that page.

        Google blocks the address of a data centre fast. When the client has
        a list of exits, it asks a few of them at the same time and the first
        exit that answers with hits wins, the others are dropped.
        """

        params = self.build_params(query, start=start, num=num, **kwargs)
        fetcher = self.fetcher()
        await fetcher.start()
        exits = await self._exits()
        if not exits:
            exits = [""]
        last_error: GoogleSearchError | None = None
        answered = False
        for group in _groups(exits, self.race_size):
            results, error, did_answer = await self._race(fetcher, params, group)
            answered = answered or did_answer
            if error is not None:
                last_error = error
            if results:
                return results
        if not answered and last_error is not None:
            raise last_error
        return []

    async def _race(
        self,
        fetcher: Any,
        params: dict[str, Any],
        exits: Sequence[str],
    ) -> tuple[list[dict[str, Any]], GoogleSearchError | None, bool]:
        """Asks the exits of the group at the same time, the first hits win."""

        pending = {
            asyncio.ensure_future(self._fetch_with_exit(fetcher, params, exit_url)): exit_url
            for exit_url in exits
        }
        results: list[dict[str, Any]] = []
        error: GoogleSearchError | None = None
        answered = False
        try:
            while pending:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    page_results, task_error, did_answer = task.result()
                    answered = answered or did_answer
                    if task_error is not None and error is None:
                        error = task_error
                    if page_results and not results:
                        results = page_results
                if results:
                    break
        finally:
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
        return results, error, answered

    async def _fetch_with_exit(
        self,
        fetcher: Any,
        params: dict[str, Any],
        exit_url: str,
    ) -> tuple[list[dict[str, Any]], GoogleSearchError | None, bool]:
        """One request through one exit, the hits or the reason of the miss."""

        try:
            html = await fetcher.fetch(params, proxy=exit_url)
        except GoogleSearchError as exc:
            return [], exc, False
        try:
            _raise_when_blocked(html)
        except BlockedError as exc:
            return [], exc, False
        results = apply_inline_destinations(extract_results(html), html)
        return results, None, True

    async def search(
        self,
        query: str,
        *,
        num: int = PAGE_SIZE,
        start: int = 0,
        site: str | None = None,
        file_type: str | None = None,
        language: str | None = None,
        country: str | None = None,
        safe: str | None = None,
        extra_params: dict[str, Any] | None = None,
        allow_empty: bool = False,
    ) -> SearchResponse:
        """Searches and answers with the hits of the result page.

        More than ten hits are more than one request, the requests are sent at
        the same time and the hits are put back in the order of the pages.
        """

        text = str(query or "").strip()
        if not text:
            raise InvalidRequestError("the query is empty")
        wanted = max(1, min(int(num), self.max_results))
        first = max(0, int(start))
        offsets = [first + index * PAGE_SIZE for index in range((wanted + PAGE_SIZE - 1) // PAGE_SIZE)]

        began = time.monotonic()
        limit = asyncio.Semaphore(self.max_concurrency)

        async def fetch(offset: int) -> list[dict[str, Any]]:
            async with limit:
                return await self.search_page(
                    text,
                    start=offset,
                    num=min(PAGE_SIZE, wanted - (offset - first)),
                    site=site,
                    file_type=file_type,
                    language=language,
                    country=country,
                    safe=safe,
                    extra_params=extra_params,
                )

        pages = await asyncio.gather(*(fetch(offset) for offset in offsets), return_exceptions=True)

        hits: list[SearchHit] = []
        errors: list[BaseException] = []
        seen: set[str] = set()
        pages_ok = 0
        for page in pages:
            if isinstance(page, BaseException):
                errors.append(page)
                continue
            pages_ok += 1
            for item in page:
                url = str(item.get("url") or "").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                hits.append(SearchHit.from_serp(item, rank=len(hits) + 1))

        dork = parse_dork(text if not site else f"{text} site:{site}".strip())
        if dork.site_targets:
            kept = enforce_dork([hit.to_dict() for hit in hits], dork)
            kept_urls = {item["url"] for item in kept}
            hits = [hit for hit in hits if hit.url in kept_urls]

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
                rank=index,
                resolved=hit.resolved,
                source=hit.source,
            )

        return SearchResponse(
            query=text,
            hits=tuple(hits),
            total=len(hits),
            pages_fetched=pages_ok,
            duration_ms=int((time.monotonic() - began) * 1000),
            source="google",
            engine="google",
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


def _groups(items: Sequence[str], size: int) -> list[list[str]]:
    """Splits the exits into groups of `size`, the groups are asked one by one."""

    step = max(1, int(size))
    return [list(items[index:index + step]) for index in range(0, len(items), step)]


def _is_host_target(target: str) -> bool:
    value = str(target or "").strip().lower()
    if value.startswith("www."):
        value = value[4:]
    return bool(re.match(r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}$", value))


def _env_flag(name: str) -> bool:
    return str(os.environ.get(name, "0")).strip().lower() in ("1", "true", "yes", "on")


def _raise_when_blocked(html: str) -> None:
    """Google answered with a block, a challenge or a consent page."""

    text = str(html or "")
    lowered = text.lower()
    for marker in BLOCK_MARKERS:
        if marker in lowered:
            raise BlockedError(f"Google answered with a block ({marker})")


__all__ = [
    "GoogleSearchClient",
    "PAGE_SIZE",
    "SearchHit",
    "SearchResponse",
    "BlockedError",
    "EmptyResultsError",
    "GoogleSearchError",
    "InvalidRequestError",
    "TransportError",
]
