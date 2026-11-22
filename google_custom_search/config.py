"""Configuration of the Google Custom Search JSON API client.

The API key and the search engine id belong to the operator of the service,
they are never part of the source tree. They are read from the environment:

    GOOGLE_CSE_API_KEY   the key of the Custom Search JSON API
    GOOGLE_CSE_CX        the id of the programmable search engine
    GOOGLE_CSE_ENDPOINT  the endpoint, only changed for tests
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

ENV_API_KEY = "GOOGLE_CSE_API_KEY"
ENV_CX = "GOOGLE_CSE_CX"
ENV_ENDPOINT = "GOOGLE_CSE_ENDPOINT"
ENV_TIMEOUT = "GOOGLE_CSE_TIMEOUT"
ENV_MAX_RESULTS = "GOOGLE_CSE_MAX_RESULTS"


class ConfigurationError(RuntimeError):
    """Raised when the service is started without the credentials it needs."""


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "")
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} has to be a number, got {raw!r}") from exc
    return value if value > 0 else default


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "")
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} has to be a number, got {raw!r}") from exc
    return value if value > 0 else default


@dataclass(frozen=True)
class Settings:
    """Everything the client needs to talk to the Custom Search JSON API."""

    api_key: str
    cx: str
    endpoint: str = DEFAULT_ENDPOINT
    timeout: float = 10.0
    max_results: int = 100

    @classmethod
    def from_env(cls, env: dict | None = None) -> "Settings":
        source = os.environ if env is None else env
        api_key = (source.get(ENV_API_KEY) or "").strip()
        cx = (source.get(ENV_CX) or "").strip()
        missing = [name for name, value in ((ENV_API_KEY, api_key), (ENV_CX, cx)) if not value]
        if missing:
            raise ConfigurationError(
                "missing credentials: " + ", ".join(missing) + " (set them in the environment)"
            )
        return cls(
            api_key=api_key,
            cx=cx,
            endpoint=(source.get(ENV_ENDPOINT) or DEFAULT_ENDPOINT).strip(),
            timeout=_float_env(ENV_TIMEOUT, 10.0) if env is None else float(source.get(ENV_TIMEOUT, 10.0) or 10.0),
            max_results=_int_env(ENV_MAX_RESULTS, 100) if env is None else int(source.get(ENV_MAX_RESULTS, 100) or 100),
        )
