"""Command line of the Custom Search JSON API client.

    python -m google_custom_search.cli "rust async runtime" --num 20
    python -m google_custom_search.cli "rust async runtime" --site github.com
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .client import GoogleCustomSearchClient
from .config import ConfigurationError, Settings
from .errors import CustomSearchError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="google-custom-search", description="Search with the Custom Search JSON API.")
    parser.add_argument("query", help="the query")
    parser.add_argument("--num", type=int, default=10, help="the number of hits (default: 10)")
    parser.add_argument("--start", type=int, default=0, help="the first hit of the answer")
    parser.add_argument("--site", default=None, help="only the hits of this host")
    parser.add_argument("--filetype", default=None, help="only the hits of this file type")
    parser.add_argument("--hl", default=None, help="the language of the hits")
    parser.add_argument("--gl", default=None, help="the country of the hits")
    parser.add_argument("--safe", default=None, help="active, passive or off")
    parser.add_argument("--date-restrict", default=None, help="d1, w1, m1 or y1")
    parser.add_argument("--json", action="store_true", help="answers with JSON")
    return parser


async def run(args: argparse.Namespace) -> int:
    try:
        settings = Settings.from_env()
    except ConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    client = GoogleCustomSearchClient.from_settings(settings)
    try:
        answer = await client.search(
            args.query,
            num=args.num,
            start=args.start,
            site_search=args.site,
            file_type=args.filetype,
            language=args.hl,
            country=args.gl,
            safe=args.safe,
            date_restrict=args.date_restrict,
        )
    except CustomSearchError as exc:
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
