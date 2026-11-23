"""Configuration of the Google web search client.

The client talks to Google itself, there is no API key and no search engine id:
a full web search is a request to the result page of Google, the client reads
the hits out of the answer. The settings belong to the operator of the service,
they are read from the environment:

    GOOGLE_SEARCH_ENDPOINT    the result page of Google, only changed for tests
    GOOGLE_SEARCH_TIMEOUT     the timeout of one request in seconds
    GOOGLE_SEARCH_MAX_RESULTS the highest number of hits one search may answer
    GOOGLE_SEARCH_PROXY       the exit of the request, "http://host:port"
    GOOGLE_SEARCH_USER_AGENT  the browser the request pretends to be
    GOOGLE_SEARCH_HL          the language of the hits
    GOOGLE_SEARCH_GL          the country of the hits
    GOOGLE_SEARCH_MAX_CONCURRENCY  how many pages are asked at the same time
    GOOGLE_SEARCH_MODE        browser, http or auto
    GOOGLE_SEARCH_BROWSER     chromium or firefox
    GOOGLE_SEARCH_BROWSER_PATH the binary of the browser, empty picks the default
    GOOGLE_SEARCH_POOL        the list of the exits, empty asks without a list
    GOOGLE_SEARCH_EXITS       how many exits one search may ask
    GOOGLE_SEARCH_RACE        how many exits are asked at the same time
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .pool import DEFAULT_POOL_URL

DEFAULT_ENDPOINT = "https://www.google.com/search"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
DEFAULT_BROWSER = "chromium"
DEFAULT_BROWSER_PATH = ""

ENV_ENDPOINT = "GOOGLE_SEARCH_ENDPOINT"
ENV_TIMEOUT = "GOOGLE_SEARCH_TIMEOUT"
ENV_MAX_RESULTS = "GOOGLE_SEARCH_MAX_RESULTS"
ENV_PROXY = "GOOGLE_SEARCH_PROXY"
ENV_USER_AGENT = "GOOGLE_SEARCH_USER_AGENT"
ENV_HL = "GOOGLE_SEARCH_HL"
ENV_GL = "GOOGLE_SEARCH_GL"
ENV_SAFE = "GOOGLE_SEARCH_SAFE"
ENV_MAX_CONCURRENCY = "GOOGLE_SEARCH_MAX_CONCURRENCY"
ENV_MODE = "GOOGLE_SEARCH_MODE"
ENV_BROWSER = "GOOGLE_SEARCH_BROWSER"
ENV_BROWSER_PATH = "GOOGLE_SEARCH_BROWSER_PATH"
ENV_POOL = "GOOGLE_SEARCH_POOL"
ENV_EXITS = "GOOGLE_SEARCH_EXITS"
ENV_RACE = "GOOGLE_SEARCH_RACE"


class ConfigurationError(RuntimeError):
    """Raised when a setting of the service is not a number."""


def _float_env(name: str, default: float, source: dict) -> float:
    raw = str(source.get(name, "") or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} has to be a number, got {raw!r}") from exc
    return value if value > 0 else default


def _int_env(name: str, default: int, source: dict) -> int:
    raw = str(source.get(name, "") or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} has to be a number, got {raw!r}") from exc
    return value if value > 0 else default


@dataclass(frozen=True)
class Settings:
    """Everything the client needs to talk to Google."""

    endpoint: str = DEFAULT_ENDPOINT
    timeout: float = 15.0
    max_results: int = 100
    proxy: str = ""
    user_agent: str = DEFAULT_USER_AGENT
    hl: str = "en"
    gl: str = "us"
    safe: str = ""
    max_concurrency: int = 4
    mode: str = "auto"
    browser: str = DEFAULT_BROWSER
    executable_path: str = DEFAULT_BROWSER_PATH
    pool_url: str = DEFAULT_POOL_URL
    exits_per_search: int = 4
    race_size: int = 3

    @classmethod
    def from_env(cls, env: dict | None = None) -> "Settings":
        source = os.environ if env is None else env
        return cls(
            endpoint=(source.get(ENV_ENDPOINT) or DEFAULT_ENDPOINT).strip(),
            timeout=_float_env(ENV_TIMEOUT, 15.0, source),
            max_results=_int_env(ENV_MAX_RESULTS, 100, source),
            proxy=(source.get(ENV_PROXY) or "").strip(),
            user_agent=(source.get(ENV_USER_AGENT) or DEFAULT_USER_AGENT).strip(),
            hl=(source.get(ENV_HL) or "en").strip(),
            gl=(source.get(ENV_GL) or "us").strip(),
            safe=(source.get(ENV_SAFE) or "").strip(),
            max_concurrency=_int_env(ENV_MAX_CONCURRENCY, 4, source),
            mode=(source.get(ENV_MODE) or "auto").strip().lower(),
            browser=(source.get(ENV_BROWSER) or DEFAULT_BROWSER).strip().lower(),
            executable_path=(source.get(ENV_BROWSER_PATH) or DEFAULT_BROWSER_PATH).strip(),
            pool_url=str(source.get(ENV_POOL, DEFAULT_POOL_URL) or "").strip(),
            exits_per_search=_int_env(ENV_EXITS, 4, source),
            race_size=_int_env(ENV_RACE, 3, source),
        )
