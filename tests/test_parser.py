"""Tests of the parser of the result page of Google."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google_custom_search.parser import (  # noqa: E402
    apply_inline_destinations,
    cite_to_url,
    decode_google_href,
    extract_results,
    harvest_inline_destinations,
    title_tokens,
)
from tests.fixtures import SERP_HTML  # noqa: E402


def test_extract_results_reads_the_hits_of_the_page():
    results = extract_results(SERP_HTML)
    titles = [item["title"] for item in results]
    assert "The Async Ecosystem - Rust Async Book" in titles
    assert "Tokio tutorial" in titles
    assert len(results) == 4


def test_extract_results_reads_a_direct_link_and_the_snippet():
    results = extract_results(SERP_HTML)
    first = results[0]
    assert first["url"] == "https://rust-lang.github.io/async-book/08_ecosystem/00_chapter.html"
    assert first["snippet"].startswith("The async book is a chapter")
    assert first["resolved"] is True


def test_extract_results_unwraps_the_url_parameter():
    results = extract_results(SERP_HTML)
    tokio = next(item for item in results if item["title"] == "Tokio tutorial")
    assert tokio["url"] == "https://tokio.rs/tokio/tutorial/async"


def test_extract_results_keeps_an_encrypted_destination_open():
    results = extract_results(SERP_HTML)
    encrypted = next(item for item in results if item["title"] == "Encrypted destination")
    assert encrypted["url"].startswith("/goto?url=")
    assert encrypted["resolved"] is False
    assert encrypted["cite_truncated"] is True


def test_extract_results_reads_the_visible_cite():
    results = extract_results(SERP_HTML)
    first = results[0]
    assert "rust-lang.github.io" in first["display_link"]
    assert first["cite_truncated"] is False


def test_harvest_inline_destinations_reads_the_exact_address():
    harvests = harvest_inline_destinations(SERP_HTML)
    urls = [item["url"] for item in harvests]
    assert "https://tokio.rs/tokio/tutorial/async" in urls
    assert "https://github.com/rust-lang/tokio" in urls


def test_apply_inline_destinations_fills_the_encrypted_destination():
    results = extract_results(SERP_HTML)
    results = apply_inline_destinations(results, SERP_HTML)
    encrypted = next(item for item in results if item["title"] == "Encrypted destination")
    assert encrypted["url"] == "https://github.com/rust-lang/tokio"
    assert encrypted["resolved"] is True


def test_cite_to_url_builds_the_address_of_a_cite():
    assert cite_to_url("tokio.rs › tokio › tutorial › async") == "https://tokio.rs/tokio/tutorial/async"


def test_cite_to_url_drops_the_path_of_a_cut_cite():
    assert cite_to_url("tokio.rs › … › async") == "https://tokio.rs"
    assert cite_to_url("tokio.rs › tokio › tutorial …") == "https://tokio.rs/tokio"


def test_decode_google_href_refuses_a_link_of_google():
    assert decode_google_href("https://www.google.com/search?q=x") == ""
    assert decode_google_href("/url?q=https://example.com/page") == "https://example.com/page"


def test_title_tokens_keeps_the_words_that_carry_meaning():
    assert title_tokens("The Async Ecosystem - Rust Async Book") == [
        "the",
        "async",
        "ecosystem",
        "rust",
        "async",
        "book",
    ]
