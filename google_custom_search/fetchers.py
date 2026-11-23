"""The two ways of asking Google.

Google does not put the hits into the answer of a plain request any more: the
page of a request without a browser is the shell of the page, the hits are
painted by the browser. The client therefore has two fetchers:

``HttpFetcher``
    A plain request with ``httpx``. It is the light way and it is the way that
    works where Google still answers with the static page.

``BrowserFetcher``
    A real browser that renders the page of the result. The browser of the
    project is Chromium, camoufox is the second choice. The browser is opened
    once and every request gets its own context with its own exit.

Both fetchers answer with the HTML of the page, the parser of the package
reads the hits out of it.
"""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlencode

import httpx

from .config import DEFAULT_USER_AGENT
from .errors import TransportError

CHROMIUM_BINARY = "/usr/bin/chromium"
CAMOUFOX_BINARY = "/opt/camoufox/camoufox-bin"
FIREFOX_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"

CHROMIUM_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-software-rasterizer",
    "--mute-audio",
    "--hide-scrollbars",
    "--disable-extensions",
    "--no-first-run",
    "--disable-features=TranslateUI,AutomationControlled,MediaRouter",
    "--lang=en-US",
    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
    "--webrtc-ip-handling-policy=disable_non_proxied_udp",
    "--disable-sync",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-default-apps",
    "--disable-hang-monitor",
    "--disable-popup-blocking",
    "--disable-prompt-on-repost",
    "--disable-client-side-phishing-detection",
    "--metrics-recording-only",
    "--no-default-browser-check",
    "--safebrowsing-disable-auto-update",
    "--disable-blink-features=AutomationControlled",
    # Some proxy providers break the HTTP/2 of Chromium towards Google: the
    # request then stalls forever. HTTP/1.1 is the safe way over a proxy.
    "--disable-http2",
]

BLOCKED_RESOURCES = {"image", "media", "font", "imageset"}

# Hides the traces of the automation. Runs before the first script of the page.
STEALTH_JS = """
try {
  Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
} catch {}
try {
  Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
  Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
} catch {}
try {
  window.chrome = window.chrome || {};
  window.chrome.runtime = window.chrome.runtime || {};
} catch {}
try {
  const q = navigator.permissions && navigator.permissions.query;
  if (q) {
    navigator.permissions.query = (p) =>
      p && p.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : q.call(navigator.permissions, p);
  }
} catch {}
try {
  Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
  Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
  Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0 });
  Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
} catch {}
try {
  const gl = document.createElement('canvas').getContext('webgl');
  if (gl) {
    const getParameter = gl.getParameter.bind(gl);
    gl.getParameter = (parameter) => {
      if (parameter === 37445) return 'Intel Inc.';
      if (parameter === 37446) return 'Intel Iris OpenGL Engine';
      return getParameter(parameter);
    };
  }
} catch {}
"""

CONSENT_COOKIES = [
    {
        "name": "CONSENT",
        "value": "YES+cb.20210328-17-p0.en+FX+0",
        "domain": ".google.com",
        "path": "/",
    },
    {"name": "SOCS", "value": "CAI", "domain": ".google.com", "path": "/"},
]


class HttpFetcher:
    """Asks Google with a plain request."""

    def __init__(
        self,
        *,
        endpoint: str,
        timeout: float = 15.0,
        proxy: str = "",
        user_agent: str = DEFAULT_USER_AGENT,
        hl: str = "en",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self.proxy = proxy
        self.user_agent = user_agent
        self.hl = hl
        self.extra_headers = headers or {}
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "user-agent": self.user_agent,
                    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "accept-language": f"{self.hl},{self.hl};q=0.9,en;q=0.8",
                    "upgrade-insecure-requests": "1",
                    **self.extra_headers,
                },
                follow_redirects=True,
                proxy=self.proxy or None,
            )
        return self._client

    async def fetch(self, params: dict[str, Any], proxy: str = "") -> str:
        try:
            response = await self._http().get(self.endpoint, params=params)
        except httpx.HTTPError as exc:
            raise TransportError(f"Google could not be reached: {exc}") from exc
        if response.status_code >= 400:
            raise TransportError(f"Google answered HTTP {response.status_code}")
        return response.text


class BrowserFetcher:
    """Renders the page of the result with a real browser."""

    def __init__(
        self,
        *,
        endpoint: str,
        timeout: float = 15.0,
        proxy: str = "",
        browser: str = "chromium",
        executable_path: str = "",
        headless: bool = True,
        locale: str = "en-US",
        timezone: str = "America/New_York",
        user_agent: str = "",
        ready_timeout: float = 8.0,
        block_assets: bool = True,
    ) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self.proxy = proxy
        self.browser = (browser or "chromium").strip().lower()
        self.executable_path = executable_path or (
            CHROMIUM_BINARY if self.browser == "chromium" else CAMOUFOX_BINARY
        )
        self.headless = headless
        self.locale = locale
        self.timezone = timezone
        self.user_agent = user_agent
        self.ready_timeout = ready_timeout
        self.block_assets = block_assets
        self._playwright: Any = None
        self._browser: Any = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Launches the browser, the first request pays for it."""

        async with self._lock:
            if self._browser is not None:
                return
            try:
                from playwright.async_api import async_playwright
            except ImportError as exc:
                raise TransportError(
                    "the browser of the client needs playwright (pip install playwright)"
                ) from exc
            self._playwright = await async_playwright().start()
            if self.browser == "firefox":
                options: dict[str, Any] = {"headless": self.headless}
                if self.executable_path:
                    options["executable_path"] = self.executable_path
                self._browser = await self._playwright.firefox.launch(**options)
            else:
                args = list(CHROMIUM_ARGS)
                self._browser = await self._playwright.chromium.launch(
                    headless=self.headless,
                    executable_path=self.executable_path or None,
                    args=args,
                    ignore_default_args=["--enable-automation"],
                )

    async def close(self) -> None:
        async with self._lock:
            if self._browser is not None:
                try:
                    await self._browser.close()
                except Exception:
                    pass
                self._browser = None
            if self._playwright is not None:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None

    async def _user_agent(self) -> str:
        """The browser of the request says what it really is."""

        if self.user_agent:
            return self.user_agent
        if self.browser == "firefox":
            return FIREFOX_UA
        try:
            version = self._browser.version
            if callable(version):
                version = await version()
        except Exception:
            version = ""
        version = str(version or "")
        major = version.split(".")[0] if version else "131"
        if not major.isdigit():
            major = "131"
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36"
        )

    async def fetch(self, params: dict[str, Any], proxy: str = "") -> str:
        """Renders the page of the result, the exit of the request is optional."""

        await self.start()
        browser = self._browser
        if browser is None:
            raise TransportError("the browser did not start")
        query = urlencode({key: value for key, value in params.items() if value is not None})
        url = f"{self.endpoint}?{query}"
        exit_url = proxy or self.proxy
        context = None
        try:
            options: dict[str, Any] = {
                "locale": self.locale,
                "timezone_id": self.timezone,
                "user_agent": await self._user_agent(),
                "viewport": {"width": 1366, "height": 900},
                "color_scheme": "light",
            }
            if exit_url:
                options["proxy"] = _proxy_options(exit_url)
            context = await browser.new_context(**options)
            await context.add_cookies(CONSENT_COOKIES)
            await context.add_init_script(STEALTH_JS)
            page = await context.new_page()
            if self.block_assets:
                await page.route("**/*", _route_without_assets)
            await page.goto(
                url,
                wait_until="commit",
                timeout=int(self.timeout * 1000),
            )
            try:
                await page.wait_for_selector("h3", timeout=int(self.ready_timeout * 1000))
            except Exception:
                pass
            await _dismiss_consent(page)
            return await page.content()
        except Exception as exc:
            raise TransportError(f"the browser could not render the page: {exc}") from exc
        finally:
            if context is not None:
                try:
                    await context.close()
                except Exception:
                    pass


async def _route_without_assets(route: Any) -> None:
    """The pictures and the fonts are of no use for the hits, they only cost time."""

    try:
        if route.request.resource_type in BLOCKED_RESOURCES:
            await route.abort()
            return
    except Exception:
        pass
    try:
        await route.continue_()
    except Exception:
        pass


async def _dismiss_consent(page: Any) -> None:
    """The cookie page of Google is in the way of the hits."""

    try:
        await page.evaluate(
            """
            const sels = ['#L2AGLb', '#W0wltc', 'button#L2AGLb',
              'form[action*="consent"] button',
              'button[aria-label*="Accept"]',
              'button[aria-label*="Agree"]'];
            for (const sel of sels) {
              const el = document.querySelector(sel);
              if (el) { el.click(); return true; }
            }
            return false;
            """
        )
    except Exception:
        return


def _proxy_options(proxy: str) -> dict[str, str]:
    """The proxy of the browser in the shape of playwright."""

    from urllib.parse import urlparse

    parsed = urlparse(proxy)
    if not parsed.hostname:
        return {"server": proxy}
    options = {
        "server": f"{parsed.scheme or 'http'}://{parsed.hostname}:{parsed.port or 8080}",
    }
    if parsed.username:
        options["username"] = parsed.username
    if parsed.password:
        options["password"] = parsed.password
    return options


def browser_available() -> bool:
    """Whether the browser of the client can be used."""

    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    return True


__all__ = [
    "BrowserFetcher",
    "HttpFetcher",
    "browser_available",
    "CAMOUFOX_BINARY",
    "CHROMIUM_BINARY",
    "FIREFOX_UA",
]
