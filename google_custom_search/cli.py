"""Command line of the web search client of Google.

    python -m google_custom_search.cli "rust async runtime" --num 20
    python -m google_custom_search.cli "rust async runtime" --site github.com
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .client import GoogleSearchClient
from .config import ConfigurationError, Settings
from .errors import GoogleSearchError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="google-custom-search", description="Search the web with Google.")
    parser.add_argument("query", nargs="?", help="the query")
    parser.add_argument("--query", dest="query_flag", default=None, help="the query")
    parser.add_argument("--num", type=int, default=10, help="the number of hits (default: 10)")
    parser.add_argument("--start", type=int, default=0, help="the first hit of the answer")
    parser.add_argument("--site", default=None, help="only the hits of this host")
    parser.add_argument("--filetype", default=None, help="only the hits of this file type")
    parser.add_argument("--hl", default=None, help="the language of the hits")
    parser.add_argument("--gl", default=None, help="the country of the hits")
    parser.add_argument("--safe", default=None, help="active, passive or off")
    parser.add_argument("--url", default=None, help="the result page of Google (default: www.google.com/search)")
    parser.add_argument("--proxy", default=None, help="the exit of the request, http://host:port")
    parser.add_argument("--timeout", type=float, default=None, help="the timeout of one request in seconds")
    parser.add_argument("--mode", default=None, choices=["auto", "browser", "http"], help="how the page is asked")
    parser.add_argument("--browser", default=None, choices=["chromium", "firefox"], help="the browser that renders the page")
    parser.add_argument("--json", action="store_true", help="answers with JSON")
    return parser


async def run(args: argparse.Namespace) -> int:
    query = args.query or args.query_flag
    if not query:
        print("error: the query is empty", file=sys.stderr)
        return 2
    try:
        settings = Settings.from_env()
    except ConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    client = GoogleSearchClient(
        endpoint=args.url or settings.endpoint,
        timeout=args.timeout if args.timeout else settings.timeout,
        max_results=settings.max_results,
        proxy=args.proxy if args.proxy else settings.proxy,
        user_agent=settings.user_agent,
        hl=args.hl or settings.hl,
        gl=args.gl or settings.gl,
        safe=args.safe or settings.safe,
        max_concurrency=settings.max_concurrency,
        mode=args.mode or settings.mode,
        browser=args.browser or settings.browser,
        executable_path=settings.executable_path,
        pool_url=settings.pool_url,
        exits_per_search=settings.exits_per_search,
        race_size=settings.race_size,
    )
    try:
        answer = await client.search(
            query,
            num=args.num,
            start=args.start,
            site=args.site,
            file_type=args.filetype,
            language=args.hl,
            country=args.gl,
            safe=args.safe,
        )
    except GoogleSearchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        await client.aclose()

    if args.json:
        print(json.dumps(answer.to_dict(), indent=2, ensure_ascii=False))
        return 0
    for hit in answer.hits:
        print(f"{hit.rank:>3}. {hit.title}")
        print(f"     {hit.url}")
        if hit.snippet:
            print(f"     {hit.snippet[:160]}")
    print(f"\n{len(answer.hits)} hits in {answer.duration_ms}ms")
    return 0


def main() -> int:
    return asyncio.run(run(build_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
