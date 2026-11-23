"""Reads the hits out of the result page of Google.

The page of Google holds the hits twice: as HTML (the title, the visible cite
and the snippet) and as inline data (the title next to the real destination of
the hit). The inline data is the exact address, the visible cite is often cut
short. The parser reads both and puts the exact address in the hit.

The rules of the pairing are the ones of the renderer (``gsearch-renderer``):
a title that starts with the title of the hit, a title that has three of its
words in common and a host that matches.
"""

from __future__ import annotations

import html as html_lib
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

try:  # the DOM parser is the accurate one
    from lxml import html as lxml_html
except ImportError:  # pragma: no cover - lxml is a dependency of the package
    lxml_html = None

SNIPPET_CLASSES = ("VwiC3b", "aCOpRe", "IsZvec", "st")
CITE_CLASSES = ("qLRx3b", "tjvcx", "ylcaW")
IGNORED_CLASSES = ("HiHjCd", "St0YAf", "O1MEtf", "related-question-pair", "OSJXUb")
IGNORED_TAGS = ("nav", "header")

DATE_LIKE = re.compile(
    r"^\d+\s+(?:second|minute|hour|day|week|month|year)s?\s+ago$", re.IGNORECASE
)
DATE_LIKE_ALT = re.compile(
    r"^(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}$",
    re.IGNORECASE,
)

# The inline data of the result page: title, null, favicon, host, sources, the
# exact destination.
INLINE_RESULT_RE = re.compile(
    r'"((?:[^"\\]|\\.){3,250})",null,"(?:[^"\\]|\\.){0,800}","(https?://(?:[^"\\]|\\.)+)",'
    r'\[[^\]]{0,400}\],"(https?://(?:[^"\\]|\\.)+)"'
)

# The entities of the HTML, spelled out so that they survive every copy.
_AMP = chr(38)
ENTITY_MAP = (
    (_AMP + "amp;", _AMP),
    (_AMP + "lt;", "<"),
    (_AMP + "gt;", ">"),
    (_AMP + "quot;", chr(34)),
    (_AMP + "#39;", chr(39)),
    (_AMP + "#x27;", chr(39)),
)

STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "from", "how", "why", "what", "when",
    "are", "was", "were", "you", "your", "its", "has", "have", "not", "but", "all",
    "can", "will", "does", "into", "out", "about", "more", "most", "some", "any",
    "here", "they", "them", "their", "there", "then", "than", "also", "just", "like",
    "part", "using", "use", "used", "make", "made", "get", "got", "new", "one",
}


def decode_entities(value: str) -> str:
    """Decodes the entities of Google, the ones that carry a character."""

    text = str(value or "")
    for entity, char in ENTITY_MAP:
        text = text.replace(entity, char)
    return text


def decode_js_escapes(value: str) -> str:
    """Decodes the escapes of the inline data (\\u003d, \\u0026, ...)."""

    text = str(value or "")
    text = re.sub(
        r"\\\\u([0-9a-f]{4})",
        lambda match: chr(int(match.group(1), 16)),
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\\u([0-9a-f]{4})",
        lambda match: chr(int(match.group(1), 16)),
        text,
        flags=re.IGNORECASE,
    )
    return text.replace("\\/", "/").replace('\\"', '"')


def normalize_text(value: str) -> str:
    """Puts the text of a title or of a snippet in one line."""

    return re.sub(r"\s+", " ", html_lib.unescape(str(value or ""))).strip()


def title_tokens(title: str) -> list[str]:
    """The words of a title that carry meaning."""

    text = re.sub(r"<[^>]+>", " ", str(title or "").lower())
    return [token for token in re.split(r"[^a-z0-9]+", text) if len(token) > 2]


def stop_tokens(tokens: list[str]) -> list[str]:
    """The words of a title without the words every title has."""

    return [token for token in tokens if token not in STOP_WORDS]


def title_similarity(a_tokens: list[str], b_tokens: list[str]) -> float:
    """How many words of the title are also in the other title."""

    if not a_tokens or not b_tokens:
        return 0.0
    other = set(b_tokens)
    hits = sum(1 for token in set(a_tokens) if token in other)
    return hits / len(a_tokens)


def token_hits(a_tokens: list[str], b_tokens: list[str]) -> int:
    """How many words of the title are also in the other title."""

    other = set(b_tokens)
    return sum(1 for token in set(a_tokens) if token in other)


def normalize_title(title: str) -> str:
    """The title in the form two titles are compared in."""

    text = re.sub(r"[^a-z0-9]+", " ", str(title or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def clean_url(url: str) -> str:
    """Cleans a URL: no hash, no tracking parameters."""

    text = str(url or "").strip()
    if not text:
        return ""
    try:
        parsed = urlparse(text)
    except ValueError:
        return text
    if not parsed.scheme or not parsed.netloc:
        return text
    dropped = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid")
    query = [(key, val) for key, val in parse_qs(parsed.query, keep_blank_values=True).items() if key not in dropped]
    flat = [(key, value) for key, values in query for value in values]
    return parsed._replace(query=urlencode(flat), fragment="").geturl()


def urlencode(pairs: list[tuple[str, str]]) -> str:
    """The query of a URL, without the help of the standard library."""

    from urllib.parse import quote

    return "&".join(f"{quote(key)}={quote(value)}" for key, value in pairs)


def is_google_host(host: str) -> bool:
    """Whether the host belongs to Google."""

    name = str(host or "").lower()
    return name == "google.com" or name.endswith(".google.com")


def google_redirect_href(href: str) -> str:
    """The relative redirect of Google, empty when the link is a real link."""

    raw = decode_entities(str(href or "").strip())
    if not raw:
        return ""
    if re.match(r"^/(?:goto|url)\?", raw, re.IGNORECASE):
        return raw
    try:
        parsed = urlparse(raw)
    except ValueError:
        return ""
    if is_google_host(parsed.hostname or "") and re.match(r"^/(?:goto|url)/?$", parsed.path or "", re.IGNORECASE):
        return f"{parsed.path}{parsed.search}"
    return ""


def unwrap_google_href(href: str) -> str:
    """The address inside a redirect of Google, empty when there is none."""

    text = str(href or "").strip()
    for _ in range(4):
        relative = text.startswith("/url?") or text.startswith("/goto?")
        try:
            parsed = urlparse(text)
        except ValueError:
            return ""
        is_google_path = is_google_host(parsed.hostname or "") and re.match(
            r"^/(?:url|goto)/?$", parsed.path or "", re.IGNORECASE
        )
        if not (relative or is_google_path):
            break
        params = parse_qs(parsed.query)
        values = params.get("url") or params.get("q") or params.get("u") or []
        if not values:
            break
        text = values[0]
    try:
        text = unquote(text)
    except Exception:
        pass
    return decode_entities(text).strip()


def decode_google_href(href: str) -> str:
    """The address of a link of the result page, empty when it is no address."""

    text = str(href or "").strip()
    if not text:
        return ""
    if text.startswith("/"):
        text = "https://www.google.com" + text
    inner = unwrap_google_href(text)
    if inner:
        text = inner
    if not re.match(r"^https?://", text, re.IGNORECASE):
        return ""
    try:
        parsed = urlparse(text)
    except ValueError:
        return ""
    host = (parsed.hostname or "").lower()
    if is_google_host(host) or host.endswith("googleusercontent.com") or host.endswith("gstatic.com"):
        return ""
    return clean_url(text)


def cite_to_url(displayed: str) -> str:
    """The address of a visible cite, empty when the cite carries no address."""

    text = normalize_text(displayed)
    if not text:
        return ""
    truncated = bool(re.search(r"\.{3}|…", text))
    parts = [part.strip() for part in re.split(r"\s*[›>]\s*", text)]
    elided_at = -1
    for index, part in enumerate(parts):
        if index > 0 and part in ("...", "…") and index < len(parts) - 1:
            elided_at = index
    kept = [part for part in parts if part and part not in ("...", "…")]
    if not kept:
        return ""
    host = kept[0]
    if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", host, re.IGNORECASE):
        return ""
    path_parts = [part.lstrip("/") for part in kept[1:] if part]
    if elided_at >= 0:
        path_parts = []
    if truncated and path_parts:
        path_parts = path_parts[:-1]
    path = "/" + "/".join(path_parts) if path_parts else ""
    return f"https://{host}{path}"


def is_prefix_url(shorter: str, longer: str) -> bool:
    """Whether the first address is the beginning of the second one."""

    a = str(shorter or "")
    b = str(longer or "")
    if not a or not b or a == b or not b.startswith(a):
        return False
    return bool(re.search(r"[/:?&=.]", a[-1])) or len(b) > len(a) + 4


def _classes(element: Any) -> set[str]:
    return set((element.get("class") or "").split())


def _has_any_class(element: Any, names: tuple[str, ...]) -> bool:
    classes = _classes(element)
    return any(name in classes for name in names)


def _text_of(element: Any) -> str:
    if element is None:
        return ""
    return normalize_text(" ".join(element.itertext()))


def _snippet_of(element: Any) -> Any:
    for child in element.iter():
        if child is element:
            continue
        if _has_any_class(child, SNIPPET_CLASSES):
            return child
    return None


def _cite_of(element: Any) -> str:
    for child in element.iter():
        if child is element:
            continue
        if child.tag == "cite" or _has_any_class(child, CITE_CLASSES):
            text = _text_of(child)
            if not text or DATE_LIKE.match(text) or DATE_LIKE_ALT.match(text):
                continue
            return text
    return ""


def _ignored_heading(heading: Any) -> bool:
    text = _text_of(heading)
    if len(text) < 3 or len(text) > 200:
        return True
    lowered = text.lower()
    if lowered.startswith(("ai mode", "ai overview", "try ai mode")):
        return True
    if re.match(r"^https?://", text, re.IGNORECASE):
        return True
    parent = heading.getparent()
    while parent is not None:
        if parent.tag in IGNORED_TAGS:
            return True
        if _has_any_class(parent, IGNORED_CLASSES):
            return True
        parent = parent.getparent()
    return False


def _card_of(heading: Any, body: Any) -> Any:
    element = heading.getparent()
    fallback = None
    for _ in range(10):
        if element is None or element is body:
            break
        fallback = element
        heads = len(element.findall(".//h3"))
        if heads > 2:
            return fallback
        if _snippet_of(element) is not None:
            return element
        element = element.getparent()
    return fallback if fallback is not None else heading.getparent()


def _anchor_of(heading: Any, card: Any) -> Any:
    element = heading.getparent()
    while element is not None:
        if element.tag == "a" and element.get("href"):
            return element
        element = element.getparent()
    for anchor in card.iter("a"):
        if not anchor.get("href"):
            continue
        if anchor.find(".//h3") is not None:
            return anchor
    for anchor in card.iter("a"):
        href = anchor.get("href") or ""
        if href.startswith("http"):
            return anchor
    return None


def _snippet_text(card: Any, heading: Any) -> str:
    elements = list(card.iter())
    try:
        position = elements.index(heading)
    except ValueError:
        position = -1
    fallback = ""
    for offset, element in enumerate(elements):
        if not _has_any_class(element, SNIPPET_CLASSES):
            continue
        text = _text_of(element)
        if len(text) <= 12:
            continue
        text = text[:400]
        if position >= 0 and offset > position:
            return text
        if not fallback:
            fallback = text
    return fallback


def _result_from_heading(heading: Any, body: Any) -> dict[str, Any] | None:
    if _ignored_heading(heading):
        return None
    title = _text_of(heading)
    if not title:
        return None
    card = _card_of(heading, body)
    anchor = _anchor_of(heading, card)
    if anchor is None:
        return None
    href = decode_entities(anchor.get("href") or "").strip()
    display_link = _cite_of(card)
    cite_truncated = bool(re.search(r"\.{3}|…", display_link))
    destination = decode_google_href(href)
    resolved = bool(destination)
    if not destination and display_link:
        fallback = cite_to_url(display_link)
        if fallback and not cite_truncated:
            destination = fallback
            resolved = True
    if not destination:
        redirect = google_redirect_href(href)
        if redirect:
            destination = redirect
    return {
        "title": title,
        "url": destination,
        "snippet": _snippet_text(card, heading),
        "display_link": display_link,
        "cite_truncated": cite_truncated,
        "resolved": resolved,
        "goto_href": google_redirect_href(href),
    }


def extract_results(html: str) -> list[dict[str, Any]]:
    """The hits of a result page of Google."""

    text = str(html or "")
    if not text.strip():
        return []
    if lxml_html is None:
        return _extract_results_regex(text)
    try:
        body = lxml_html.fromstring(text)
    except Exception:
        return _extract_results_regex(text)
    results: list[dict[str, Any]] = []
    for heading in body.iter("h3"):
        item = _result_from_heading(heading, body)
        if item and item["url"]:
            results.append(item)
    if not results:
        return _extract_results_regex(text)
    return results


_BLOCK_RE = re.compile(
    r'<div[^>]*class="[^"]*\bg\b[^"]*"[^>]*>([\s\S]*?)(?=<div[^>]*class="[^"]*\bg\b|$)', re.IGNORECASE
)
_TITLE_PAIR_RE = re.compile(
    r'<h3[^>]*>([\s\S]*?)</h3>[\s\S]*?<a\b[^>]*href="([^"]+)"[^>]*>'
    r'|<a\b[^>]*href="([^"]+)"[^>]*>[\s\S]*?<h3[^>]*>([\s\S]*?)</h3>',
    re.IGNORECASE,
)
_CITE_RE = re.compile(r"<cite[^>]*>([\s\S]*?)</cite>", re.IGNORECASE)
_SNIPPET_RE = re.compile(
    r'<(?:div|span)[^>]*class="[^"]*(?:VwiC3b|aCOpRe|MUxGbd|IsZvec)[^"]*"[^>]*>([\s\S]*?)</(?:div|span)>',
    re.IGNORECASE,
)


def _strip_tags(value: str) -> str:
    return normalize_text(re.sub(r"<[^>]+>", " ", str(value or "")))


def _extract_results_regex(text: str) -> list[dict[str, Any]]:
    """The hits of a result page that the DOM parser could not read."""

    results: list[dict[str, Any]] = []
    blocks = _BLOCK_RE.findall(text) or [text]
    for block in blocks:
        pairs = _TITLE_PAIR_RE.findall(block)
        for title_a, href_a, href_b, title_b in pairs:
            title = _strip_tags(title_a or title_b)
            href = decode_entities(href_a or href_b)
            if not title or len(title) < 3 or not href:
                continue
            cite_match = _CITE_RE.search(block)
            display_link = _strip_tags(cite_match.group(1)) if cite_match else ""
            snippet_match = _SNIPPET_RE.search(block)
            snippet = _strip_tags(snippet_match.group(1)) if snippet_match else ""
            destination = decode_google_href(href)
            resolved = bool(destination)
            if not destination and display_link:
                fallback = cite_to_url(display_link)
                if fallback and not re.search(r"\.{3}|…", display_link):
                    destination = fallback
                    resolved = True
            if not destination:
                redirect = google_redirect_href(href)
                if redirect:
                    destination = redirect
            if not destination:
                continue
            results.append(
                {
                    "title": title,
                    "url": destination,
                    "snippet": snippet[:400],
                    "display_link": display_link,
                    "cite_truncated": bool(re.search(r"\.{3}|…", display_link)),
                    "resolved": resolved,
                    "goto_href": google_redirect_href(href),
                }
            )
    return results


def harvest_inline_destinations(html: str) -> list[dict[str, str]]:
    """The exact destination of every hit of the inline data of the page."""

    text = decode_entities(str(html or ""))
    harvests: list[dict[str, str]] = []
    for match in INLINE_RESULT_RE.finditer(text):
        title = decode_entities(decode_js_escapes(match.group(1))).strip()
        host = decode_js_escapes(match.group(2))
        url = decode_js_escapes(match.group(3)).strip()
        if not title or not url:
            continue
        try:
            hostname = (urlparse(url).hostname or "").lower()
        except ValueError:
            hostname = ""
        harvests.append({"title": title, "url": clean_url(url), "host": hostname})
    return harvests


def cite_host(result: dict[str, Any]) -> str:
    """The host of the visible cite of a hit."""

    display = str(result.get("display_link") or "").strip()
    if not display:
        return ""
    first = re.split(r"\s*[›>]\s*", display)[0].strip()
    if not first or " " in first:
        return ""
    return first.lower()


def match_inline_destination(result: dict[str, Any], harvests: list[dict[str, str]]) -> str:
    """The exact destination of a hit, empty when the pairing is not sure."""

    if not harvests:
        return ""
    title = normalize_title(str(result.get("title") or ""))
    if not title:
        return ""
    host = cite_host(result)
    tokens = title_tokens(str(result.get("title") or ""))
    key = stop_tokens(tokens)
    scored: list[tuple[float, str]] = []
    for harvest in harvests:
        if host and harvest.get("host") and harvest["host"] != host:
            continue
        other = normalize_title(harvest.get("title") or "")
        if not other:
            continue
        score = 0.0
        if other == title:
            score = 1.0
        elif other.startswith(title) or title.startswith(other):
            score = 0.92
        else:
            hits = token_hits(key or tokens, title_tokens(harvest.get("title") or ""))
            if hits >= 3:
                score = title_similarity(key or tokens, title_tokens(harvest.get("title") or "")) * 0.9
        if score < 0.6:
            continue
        scored.append((score, harvest.get("url") or ""))
    if not scored:
        return ""
    scored.sort(key=lambda pair: pair[0], reverse=True)
    if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.08:
        return ""
    return scored[0][1]


def apply_inline_destinations(results: list[dict[str, Any]], html: str) -> list[dict[str, Any]]:
    """Puts the exact destination of the inline data into the hits."""

    harvests = harvest_inline_destinations(html)
    if not harvests:
        return results
    used: set[str] = set()
    for result in results:
        current = str(result.get("url") or "")
        lossy = not current.startswith("http")
        if not lossy and result.get("display_link") and result.get("cite_truncated"):
            lossy = True
        if not lossy:
            continue
        match = ""
        for harvest in harvests:
            if harvest.get("url") in used:
                continue
            match = match_inline_destination(result, [harvest])
            if match:
                used.add(match)
                break
        if match:
            result["url"] = match
            result["resolved"] = True
    return results
