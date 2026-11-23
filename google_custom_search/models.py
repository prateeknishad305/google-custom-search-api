"""The result model of the Google web search client.

The shape of a hit follows the shape of the renderer
(``gsearch-renderer``): ``title``, ``url`` and ``snippet`` are the fields a
caller expects, the rest of the answer of Google is kept as it is.
"""

from __future__ import annotations

import html as html_lib
import re
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SearchHit:
    """One hit of the result page of Google."""

    title: str
    url: str
    snippet: str = ""
    display_link: str = ""
    rank: int = 0
    resolved: bool = True
    source: str = "google"

    @classmethod
    def from_serp(cls, item: dict[str, Any], rank: int = 0) -> "SearchHit":
        return cls(
            title=str(item.get("title") or "").strip(),
            url=str(item.get("url") or "").strip(),
            snippet=_clean_html(item.get("snippet") or ""),
            display_link=str(item.get("display_link") or "").strip(),
            rank=rank,
            resolved=bool(item.get("resolved", True)),
            source=str(item.get("source") or "google"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SearchResponse:
    """The answer of one search."""

    query: str
    hits: tuple[SearchHit, ...]
    total: int = 0
    pages_fetched: int = 0
    duration_ms: int = 0
    source: str = "google"
    engine: str = "google"
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "source": self.source,
            "query": self.query,
            "count": len(self.hits),
            "total_results": self.total,
            "pages_fetched": self.pages_fetched,
            "duration_ms": self.duration_ms,
            "results": [hit.to_dict() for hit in self.hits],
            "diagnostics": dict(self.diagnostics),
        }


def _clean_html(value: Any) -> str:
    """Turns the HTML of a snippet into plain text."""

    text = re.sub(r"<[^>]+>", "", str(value))
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()
