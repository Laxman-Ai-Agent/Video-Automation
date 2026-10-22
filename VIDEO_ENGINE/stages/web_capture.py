"""Web capture for Asset Collection: a screenshot of ONE element (an infobox, a table) of a public reference page, with the provenance of the capture. Discovery uses the free Wikipedia API.

Boundaries (a capture is never a way around an access control):
- only https pages on a short allowlist of public reference hosts (Wikipedia, Wikimedia, NASA, NOAA, USGS), re-checked after every redirect;
- robots.txt is read first: a path it disallows, or a robots.txt that cannot be read, means no capture;
- no login, no cookies, no CAPTCHA handling: a page that does not simply load is reported as it is;
- the page text is licensed per page (Wikipedia: CC BY-SA 4.0) but the images inside it carry their own licences, so a capture is rights class C (a person confirms the use at Final QC).
The browser is Playwright's own Chromium (already installed for the project's end-to-end tests); nothing is downloaded here."""
from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from pathlib import Path

from . import stock

CAPTURE_HOSTS = ("wikipedia.org", "wikimedia.org", "nasa.gov", "noaa.gov", "usgs.gov")
SECTIONS = {"infobox": ".infobox", "table": "table.wikitable", "top": None}          # None = the top of the page
VIEWPORT = (1600, 1000)
NAV_TIMEOUT_MS = 30_000
MIN_SIZE = (240, 120)
MAX_PNG_BYTES = 12 * 1024 * 1024
ROBOTS_TOKEN = "audio-to-video"
HIDE_CSS = "#siteNotice, .mw-dismissable-notice, .vector-sticky-header, .vector-page-toolbar, .cookie-notice { display: none !important; }"


class CaptureError(Exception):
    """The capture is not possible or not allowed: the message is the exact cause and is safe to show."""


def host_allowed(url: str, hosts: tuple[str, ...] = CAPTURE_HOSTS, https_only: bool = True) -> bool:
    u = urllib.parse.urlparse(url)
    host = u.hostname or ""
    return (u.scheme == "https" or not https_only and u.scheme == "http") and any(host == h or host.endswith("." + h) for h in hosts)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def resolve_redirects(url: str, hosts: tuple[str, ...] = CAPTURE_HOSTS, https_only: bool = True, max_hops: int = 5) -> str:
    """Follow the redirects of `url` by hand, one hop at a time, and check EVERY hop against the allowlist before anything is fetched from it: the browser is only pointed at the final address."""
    opener = urllib.request.build_opener(_NoRedirect)
    for _ in range(max_hops + 1):
        if not host_allowed(url, hosts, https_only):
            raise CaptureError(f"the page redirected to a host that is not allowed: {urllib.parse.urlparse(url).hostname}")
        try:
            with opener.open(urllib.request.Request(url, headers={"User-Agent": stock.UA}), timeout=stock.TIMEOUT) as r:
                return url if r.status < 300 else _hop(url, r.headers.get("Location"))
        except urllib.error.HTTPError as e:
            if 300 <= e.code < 400 and e.headers.get("Location"):
                url = _hop(url, e.headers["Location"])
                continue
            raise CaptureError(f"the page answered HTTP {e.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise CaptureError(f"the page could not be reached ({getattr(e, 'reason', e)})") from None
    raise CaptureError("too many redirects")


def _hop(base: str, location: str | None) -> str:
    if not location:
        raise CaptureError("the page redirected without an address")
    return urllib.parse.urljoin(base, location)


def robots_allows(url: str) -> tuple[bool, str]:
    """(allowed, reason). A missing robots.txt (HTTP 404) allows; one that cannot be read does not."""
    u = urllib.parse.urlparse(url)
    try:
        body = stock._open(f"{u.scheme}://{u.netloc}/robots.txt").decode("utf-8", "replace")
    except stock.StockError as e:
        return (True, "no robots.txt") if "HTTP 404" in str(e) else (False, f"robots.txt could not be read ({e})")
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(body.splitlines())
    ok = rp.can_fetch(ROBOTS_TOKEN, url)
    return ok, "allowed by robots.txt" if ok else "disallowed by robots.txt"


def search_pages(q: str) -> list[stock.StockAsset]:
    """Candidate reference pages for a query from the Wikipedia search API (no key). Each keeps its page URL and the licence of the page text."""
    d = stock._json("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({"action": "query", "format": "json", "list": "search", "srsearch": q, "srlimit": stock.PER_PROVIDER, "srprop": "snippet"}))
    out = []
    for hit in (d.get("query") or {}).get("search", []):
        try:
            title, pid = hit["title"], hit["pageid"]
            url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
            out.append(stock.StockAsset(id=f"wikipedia-page:{pid}", provider="wikipedia", provider_asset_id=str(pid), source_page_url=url, download_url=url, media_type="page", title=title,
                                        license_name="CC BY-SA 4.0 (page text); images on the page carry their own licences", license_url="https://creativecommons.org/licenses/by-sa/4.0/",
                                        attribution_text=f"{title}, Wikipedia contributors, CC BY-SA 4.0", commercial_use_known=None, search_query=q, retrieved_at=stock._now()))
        except (KeyError, TypeError):
            continue
    return out


def capture(url: str, dest: Path, section: str = "infobox", *, selector: str | None = None, hosts: tuple[str, ...] = CAPTURE_HOSTS, https_only: bool = True,
            check_robots: bool = True) -> dict:
    """Screenshot the element (the section's CSS selector, else the top of the page) of an allowed page to `dest` (PNG). Returns the capture record:
    {final_url, title, captured_at, selector, region, width, height, text_sha256, text_excerpt}."""
    if not host_allowed(url, hosts, https_only):
        raise CaptureError(f"capture is limited to https pages on reference hosts ({', '.join(hosts)}): {urllib.parse.urlparse(url).hostname}")
    url = resolve_redirects(url, hosts, https_only)                      # every hop is checked before the browser sees the page
    if check_robots and not (r := robots_allows(url))[0]:
        raise CaptureError(r[1])
    sel = selector or SECTIONS.get(section)
    try:
        from playwright.sync_api import Error as PlaywrightError, sync_playwright
    except ImportError as e:
        raise CaptureError("Playwright is not installed") from e
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_context(viewport={"width": VIEWPORT[0], "height": VIEWPORT[1]}, user_agent=stock.UA).new_page()
                blocked: list[str] = []

                def guard(route, request):                                       # a navigation (the page or a redirect) to a host that is not allowed is stopped before it is fetched
                    if request.is_navigation_request() and request.frame == page.main_frame and not host_allowed(request.url, hosts, https_only):
                        blocked.append(urllib.parse.urlparse(request.url).hostname or request.url)
                        route.abort("blockedbyclient")
                    else:
                        route.continue_()
                page.route("**/*", guard)
                try:
                    resp = page.goto(url, wait_until="load", timeout=NAV_TIMEOUT_MS)
                except PlaywrightError:
                    if blocked:
                        raise CaptureError(f"the page redirected to a host that is not allowed: {blocked[0]}") from None
                    raise
                if resp is None or resp.status >= 400:
                    raise CaptureError(f"the page answered HTTP {resp.status if resp else 'nothing'}")
                page.add_style_tag(content=HIDE_CSS)
                page.wait_for_timeout(400)
                loc = page.locator(sel).first if sel and page.locator(sel).count() else None
                if loc is not None:
                    loc.evaluate("e => e.scrollIntoView({block: 'start', inline: 'nearest'})")
                    page.wait_for_timeout(250)
                    box = loc.evaluate("e => { const r = e.getBoundingClientRect(); return {x: r.x, y: r.y, width: r.width, height: r.height}; }")                  # viewport coordinates
                    box["y"] = max(box["y"], 0.0)
                    box["width"] = min(box["width"], VIEWPORT[0] - box["x"])
                    box["height"] = min(box["height"], VIEWPORT[1] - box["y"])                       # a very tall infobox is cut to its top: the part that fits the viewport is readable on a video card
                    page.screenshot(path=str(dest), clip=box, timeout=20_000)
                    text = loc.inner_text(timeout=5_000)
                elif section == "top" or sel is None:
                    box = {"x": 0, "y": 0, "width": VIEWPORT[0], "height": VIEWPORT[1]}
                    page.screenshot(path=str(dest), clip=box)
                    text = page.inner_text("body", timeout=5_000)
                else:
                    raise CaptureError(f"the page has no '{section}' section ({sel})")
                title, final = page.title(), page.url
            finally:
                browser.close()
    except PlaywrightError as e:
        raise CaptureError(f"the browser could not capture the page: {str(e).splitlines()[0][:200]}") from e
    if not dest.is_file() or dest.stat().st_size > MAX_PNG_BYTES:
        dest.unlink(missing_ok=True)
        raise CaptureError("the screenshot is missing or too large")
    from PIL import Image
    with Image.open(dest) as im:
        w, h = im.size
    if w < MIN_SIZE[0] or h < MIN_SIZE[1]:
        dest.unlink(missing_ok=True)
        raise CaptureError(f"the captured element is too small ({w}x{h})")
    text = " ".join(text.split())
    return {"final_url": final, "title": title, "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "selector": sel, "region": {k: round(float(v), 1) for k, v in box.items()}, "width": w, "height": h,
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "text_excerpt": text[:400]}
