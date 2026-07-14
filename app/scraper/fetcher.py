"""Headless-browser fetch layer.

Google requires JavaScript for search since early 2025, so a plain HTTP
client only ever sees a bot interstitial. A real Chromium passes the JS
challenge; the rendered DOM still contains the embedded JSON result data
that the parser consumes. The one critical trick: headless Chrome
advertises itself as "HeadlessChrome" in the user agent, which Google
instantly rejects — we strip that marker before browsing.
"""

import asyncio

from playwright.async_api import Browser, Playwright, async_playwright

# Consent cookie that skips the EU cookie wall.
_SOCS_COOKIE = {
    "name": "SOCS",
    "value": "CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg",
    "domain": ".google.com",
    "path": "/",
}

_STEALTH_JS = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
)

_DEVICE_PROFILES = {
    "desktop": {"viewport": {"width": 1440, "height": 900}},
    "mobile": {
        "viewport": {"width": 390, "height": 844},
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 "
            "Mobile/15E148 Safari/604.1"
        ),
        "is_mobile": True,
        "has_touch": True,
    },
    "tablet": {
        "viewport": {"width": 1024, "height": 1366},
        "user_agent": (
            "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 "
            "Mobile/15E148 Safari/604.1"
        ),
        "has_touch": True,
    },
}


class BlockedError(Exception):
    """Google served a CAPTCHA / unusual-traffic page."""


class GoogleFetcher:
    def __init__(self, max_concurrency: int = 3):
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._desktop_ua: str | None = None
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._lock = asyncio.Lock()

    async def startup(self) -> None:
        self._playwright = await async_playwright().start()
        launch_args = {
            "headless": True,
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        # Prefer the real installed Chrome (most authentic fingerprint),
        # fall back to Playwright's bundled Chromium.
        try:
            self._browser = await self._playwright.chromium.launch(
                channel="chrome", **launch_args
            )
        except Exception:
            self._browser = await self._playwright.chromium.launch(
                channel="chromium", **launch_args
            )
        ctx = await self._browser.new_context()
        page = await ctx.new_page()
        ua = await page.evaluate("navigator.userAgent")
        await ctx.close()
        self._desktop_ua = ua.replace("HeadlessChrome", "Chrome")

    async def shutdown(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _ensure_started(self) -> None:
        if self._browser is None:
            async with self._lock:
                if self._browser is None:
                    await self.startup()

    async def fetch(
        self,
        url: str,
        *,
        device: str = "desktop",
        hl: str = "en",
        chunk_url: str | None = None,
        timeout: float = 90.0,
    ) -> tuple[str, str | None]:
        """Load a Google results URL; return (rendered DOM, chunk HTML).

        When `chunk_url` is given (pagination), it is fetched from inside
        the established page session — same cookies, fingerprint, and
        trust level as the browser itself — and returned as the second
        element.

        Google occasionally serves a one-off CAPTCHA; a single retry with
        a fresh context usually clears it, so retry once before failing.
        """
        try:
            return await self._fetch_once(
                url, device=device, hl=hl, chunk_url=chunk_url, timeout=timeout
            )
        except BlockedError:
            await asyncio.sleep(2)
            return await self._fetch_once(
                url, device=device, hl=hl, chunk_url=chunk_url, timeout=timeout
            )

    async def _fetch_once(
        self,
        url: str,
        *,
        device: str,
        hl: str,
        chunk_url: str | None,
        timeout: float,
    ) -> tuple[str, str | None]:
        await self._ensure_started()
        profile = dict(_DEVICE_PROFILES.get(device, _DEVICE_PROFILES["desktop"]))
        profile.setdefault("user_agent", self._desktop_ua)
        async with self._semaphore:
            ctx = await self._browser.new_context(
                locale=f"{hl}-US" if hl == "en" else hl, **profile
            )
            try:
                await ctx.add_cookies([_SOCS_COOKIE])
                page = await ctx.new_page()
                await page.add_init_script(_STEALTH_JS)
                await page.goto(
                    url, wait_until="domcontentloaded", timeout=timeout * 1000
                )
                await page.wait_for_timeout(1500)
                if "/sorry/" in page.url:
                    raise BlockedError(
                        "Google served a CAPTCHA page (rate limited). "
                        "Retry later or route traffic through a proxy."
                    )
                chunk_html: str | None = None
                if chunk_url:
                    status, _, body = (
                        await page.evaluate(
                            "async url => {"
                            "  const r = await fetch(url, {credentials: 'include'});"
                            "  const t = await r.text();"
                            "  return r.status + '|SPLIT|' + t;"
                            "}",
                            chunk_url,
                        )
                    ).partition("|SPLIT|")
                    if status == "200":
                        chunk_html = body
                return await page.content(), chunk_html
            finally:
                await ctx.close()


fetcher = GoogleFetcher()
