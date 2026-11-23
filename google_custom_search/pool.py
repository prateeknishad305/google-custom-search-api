"""The exits of the requests.

Google blocks the address of a data centre fast, so the client asks several
exits until one of them answers with the hits. The list of the exits comes
from a provider that hands out a fresh list, the exits that do not work any
more are put aside.

The list of the provider holds one exit per line:

    host:port:user:password
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

DEFAULT_POOL_URL = "https://etherealproxyfetch.onrender.com/live.txt"
HEALTH_URL = "https://www.google.com/generate_204"


@dataclass
class ExitPool:
    """The exits the client may use."""

    url: str = DEFAULT_POOL_URL
    timeout: float = 5.0
    ttl_ms: int = 900000
    max_exits: int = 40
    concurrency: int = 24
    exits: list[str] = field(default_factory=list)
    cursor: int = 0
    loaded_at: int = 0

    async def load(self) -> list[str]:
        """Reads the list of the provider and keeps the exits that work."""

        now = int(time.monotonic() * 1000)
        if self.exits and now - self.loaded_at < self.ttl_ms:
            return self.exits
        raw = ""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(self.url)
                raw = response.text
        except Exception:
            raw = ""
        exits = parse_pool(raw)[: self.max_exits]
        if exits:
            alive = await self._alive(exits)
            self.exits = alive or exits
            self.cursor = 0
            self.loaded_at = now
        return self.exits

    async def _alive(self, exits: list[str]) -> list[str]:
        """Keeps the exits that can reach Google."""

        limit = asyncio.Semaphore(self.concurrency)
        results: list[str] = []

        async def check(exit_url: str) -> None:
            async with limit:
                try:
                    async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, proxy=exit_url) as client:
                        response = await client.get(HEALTH_URL)
                    if response.status_code < 500:
                        results.append(exit_url)
                except Exception:
                    return

        await asyncio.gather(*(check(exit_url) for exit_url in exits))
        return results

    def take(self, count: int = 1) -> list[str]:
        """The next exits of the list, the order of the list is kept."""

        if not self.exits:
            return []
        picked: list[str] = []
        for _ in range(min(count, len(self.exits))):
            picked.append(self.exits[self.cursor % len(self.exits)])
            self.cursor += 1
        return picked


def parse_pool(raw: str) -> list[str]:
    """Turns the lines of the provider into the URLs of the exits."""

    exits: list[str] = []
    seen: set[str] = set()
    for line in str(raw or "").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        parts = text.split(":")
        if len(parts) < 4:
            continue
        host = parts[0].strip()
        port = parts[1].strip()
        user = parts[2].strip()
        password = ":".join(parts[3:]).strip()
        if not host or not port:
            continue
        url = f"http://{user}:{password}@{host}:{port}"
        if url in seen:
            continue
        seen.add(url)
        exits.append(url)
    return exits


__all__ = ["DEFAULT_POOL_URL", "ExitPool", "parse_pool"]
