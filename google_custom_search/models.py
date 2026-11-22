"""The result model of the Custom Search JSON API.

The shape of a hit follows the shape of the renderer
(``gsearch-renderer``): ``title``, ``url`` and ``snippet`` are the fields a
caller expects, the rest of the answer of the API is kept as it is.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SearchHit:
    """One hit of the API."""

    title: str
    url: str
    snippet: str = ""
    display_link: str = ""
    file_format: str = ""
    mime: str = ""
    rank: int = 0
    metags: tuple[str, ...] = ()
    sitelinks: tuple[dict[str, Any], ...] = ()
    pagemap: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, item: dict[str, Any], rank: int = 0) -> "SearchHit":
        link = item.get("link") or item.get("url") or ""
        pagemap = item.get("pagemap") or {}
        metags = item.get("metaTags") or []
        sitelinks = item.get("sitelinks") or []
        return cls(
            title=str(item.get("title") or "").strip(),
            url=str(link).strip(),
            snippet=_clean_html(item.get("snippet") or ""),
            display_link=str(item.get("displayLink") or "").strip(),
            file_format=str(item.get("fileFormat") or "").strip(),
            mime=str(item.get("mime") or "").strip(),
            rank=rank,
            metags=tuple(str(tag) for tag in metags if isinstance(tag, dict)),
            sitelinks=tuple(link for link in sitelinks if isinstance(link, dict)),
            pagemap=pagemap if isinstance(pagemap, dict) else {},
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["metags"] = list(self.metags)
        data["sitelinks"] = list(self.sitelinks)
        return data


@dataclass(frozen=True)
class SearchResponse:
    """The answer of one search."""

    query: str
    hits: tuple[SearchHit, ...]
    total: int = 0
    pages_fetched: int = 0
    duration_ms: int = 0
    searches: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": "google_cse",
            "query": self.query,
            "count": len(self.hits),
            "total_results": self.total,
            "pages_fetched": self.pages_fetched,
            "duration_ms": self.duration_ms,
            "results": [hit.to_dict() for hit in self.hits],
            "searches": [dict(search) for search in self.searches],
        }


def _clean_html(value: Any) -> str:
    """Turns the HTML of a snippet into plain text."""

    import html
    import re

    text = re.sub(r"<[^>]+>", "", str(value))
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()
