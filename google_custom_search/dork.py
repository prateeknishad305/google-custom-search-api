"""The dork operators of a query.

The modern result page of Google ignores the ``site:`` operator, so the
operator is turned into a plain word of the query and into the parameter
``as_sitesearch``. The hits are checked a second time in the client: a hit of
another host is not a hit of the site that was asked for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

_SITE_RE = re.compile(r"(?<![A-Za-z0-9_])(-?)site:\s*([^\s]+)", re.IGNORECASE)
_FILETYPE_RE = re.compile(r"(?<![A-Za-z0-9_])filetype:\s*([^\s]+)", re.IGNORECASE)
_EXT_RE = re.compile(r"(?<![A-Za-z0-9_])ext:\s*([^\s]+)", re.IGNORECASE)
_HOST_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}$", re.IGNORECASE)


@dataclass
class DorkInfo:
    """The operators of a query."""

    site_targets: list[str] = field(default_factory=list)
    operators: dict[str, list[str]] = field(default_factory=dict)
    raw: str = ""

    @property
    def has_site(self) -> bool:
        return bool(self.site_targets)


def parse_dork(query: str) -> DorkInfo:
    """Reads the operators of a query."""

    text = str(query or "")
    sites: list[str] = []
    for match in _SITE_RE.finditer(text):
        for target in match.group(2).split(","):
            value = target.strip().lower()
            if value and value not in sites:
                sites.append(value)
    filetypes: list[str] = []
    for pattern in (_FILETYPE_RE, _EXT_RE):
        for match in pattern.finditer(text):
            value = match.group(1).strip().lower()
            if value and value not in filetypes:
                filetypes.append(value)
    return DorkInfo(site_targets=sites, operators={"filetype": filetypes}, raw=text)


def is_host_site_target(target: str) -> bool:
    """Whether the target of a ``site:`` operator is a host."""

    value = str(target or "").strip().lower()
    if not value or value.startswith("."):
        return False
    if value.startswith("www."):
        value = value[4:]
    return bool(_HOST_RE.match(value))


def site_as_terms(query: str, targets: list[str]) -> str:
    """Turns the ``site:`` operator into plain words of the query."""

    text = str(query or "")

    def replace(match: re.Match) -> str:
        target = match.group(2).strip().lower()
        if target not in targets:
            return match.group(0)
        return target

    return re.sub(r"(?<![A-Za-z0-9_])(-?)site:\s*([^\s]+)", replace, text, flags=re.IGNORECASE)


def host_of_result(result: dict[str, Any]) -> str:
    """The host of a hit."""

    url = str(result.get("url") or "")
    if url.startswith("http"):
        try:
            host = (urlparse(url).hostname or "").lower()
        except ValueError:
            host = ""
        if host:
            return host[4:] if host.startswith("www.") else host
    display = str(result.get("display_link") or "").strip()
    if display:
        first = re.split(r"\s*[›>]\s*", display)[0].strip().lower()
        first = first.split("/")[0]
        if first:
            return first[4:] if first.startswith("www.") else first
    return ""


def enforce_dork(results: list[dict[str, Any]], dork: DorkInfo) -> list[dict[str, Any]]:
    """Keeps the hits that are on the host the query asked for."""

    if not dork or not dork.site_targets:
        return results
    targets = [target[4:] if target.startswith("www.") else target for target in dork.site_targets]
    kept: list[dict[str, Any]] = []
    for result in results:
        host = host_of_result(result)
        if not host:
            continue
        if any(host == target or host.endswith("." + target) for target in targets):
            kept.append(result)
    return kept
