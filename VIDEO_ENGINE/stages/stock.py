"""Asset Collection providers: stock image and video search for the requirements of a project (NASA, Wikimedia Commons, Openverse, Internet Archive, Pexels, Pixabay).
Official APIs only, standard library only, keys from the environment (PEXELS_API_KEY, PIXABAY_API_KEY; NASA, Commons, Openverse and the Internet Archive need none). A provider without
its key is reported "unavailable" and skipped. Every result keeps its source page, author, licence and attribution: rights are decided per item, never per
provider, and anything unclear is marked commercial_use_known=None for the user to judge. Nothing is downloaded until the user picks one result."""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from pydantic import BaseModel

TIMEOUT = 12
MAX_BYTES = 30 * 1024 * 1024
MAX_VIDEO_BYTES = 150 * 1024 * 1024
PER_PROVIDER = 6
UA = "audio-to-video/1.0 (local tool)"
DOWNLOAD_HOSTS = ("images-assets.nasa.gov", "upload.wikimedia.org", "thumb.wikimedia.org", "images.pexels.com", "videos.pexels.com", "pixabay.com", "staticflickr.com", "archive.org", "images.unsplash.com")
FREE_LICENSES = {"by": "CC BY", "by-sa": "CC BY-SA", "cc0": "CC0", "pdm": "Public Domain Mark"}      # Openverse licence codes that allow commercial use AND changes (a crop or a dim is a change: no -nd, no -nc)
OPENVERSE_TIMEOUT = 45                       # an anonymous Openverse query answers in 15 to 20 s
MAX_ARCHIVE_SECONDS = 900                    # a recording of hours says nothing about its title: only short items of the Internet Archive


class StockError(Exception):
    """A provider answered with an error (the message is safe to show; it never contains a key)."""


class StockAsset(BaseModel):
    id: str
    provider: str
    provider_asset_id: str
    source_page_url: str = ""
    download_url: str | None = None
    media_type: str = "image"
    title: str = ""
    thumbnail_url: str | None = None
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None                # videos only
    license_name: str = ""
    license_url: str = ""
    attribution_text: str = ""
    author: str = ""
    commercial_use_known: bool | None = None       # None = not enough evidence: the user decides
    search_query: str = ""
    retrieved_at: str = ""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _open(url: str, headers: dict | None = None, limit: int = MAX_BYTES, timeout: float = TIMEOUT) -> bytes:
    """The only network call (tests replace it). One bounded retry for timeouts and 5xx; 429 is reported, never hammered. Reads at most limit+1 bytes."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    for attempt in (0, 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(limit + 1)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise StockError("rate limit reached, try again later") from e
            if e.code >= 500 and attempt == 0:
                continue
            raise StockError(f"provider answered HTTP {e.code}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt == 0:
                continue
            raise StockError("provider did not answer in time") from e
    raise StockError("provider did not answer")


def _json(url: str, headers: dict | None = None, timeout: float | None = None) -> dict:
    try:
        data = json.loads(_open(url, headers) if timeout is None else _open(url, headers, timeout=timeout))
    except ValueError as e:
        raise StockError("provider sent an unreadable answer") from e
    if not isinstance(data, dict):
        raise StockError("provider sent an unexpected answer")
    return data


def _plain(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def _clean_author(html: str) -> str:
    """The Commons "Artist" field as a credit: tags stripped, a leading file name ("X.jpg: ...") and a "derivative work" chain removed, at most 80 characters."""
    a = re.sub(r"^[\w\-. ()%,]+\.(?:jpe?g|png|webm|ogv|svg|gif|tiff?):\s*", "", _plain(html), flags=re.I)
    a = re.sub(r"\s*derivative work:?\s*", " / ", a, flags=re.I)
    a = re.sub(r"\s*\(\s*talk\s*\)", "", a)
    return (a if len(a) <= 80 else a[:79].rstrip(" /,;") + "…").strip(" /")


# ---------- adapters: provider answer -> StockAsset (a malformed item is skipped, never fatal) ----------
def nasa(q: str) -> list[StockAsset]:
    d = _json("https://images-api.nasa.gov/search?" + urllib.parse.urlencode({"q": q, "media_type": "image"}))
    out = []
    for it in d.get("collection", {}).get("items", [])[:PER_PROVIDER]:
        try:
            meta, links = it["data"][0], it.get("links") or []
            nid = meta["nasa_id"]
            thumb = next((l["href"] for l in links if l.get("render") == "image"), None)
            out.append(StockAsset(id=f"nasa:{nid}", provider="nasa", provider_asset_id=nid, source_page_url=f"https://images.nasa.gov/details/{urllib.parse.quote(nid)}",
                                  download_url=(thumb or "").replace("~thumb", "~medium") or None, thumbnail_url=thumb, title=meta.get("title", ""),
                                  license_name="NASA media guidelines (credit required; third-party content may be restricted)",
                                  license_url="https://www.nasa.gov/nasa-brand-center/images-and-media/",
                                  attribution_text=f"Credit: {meta.get('secondary_creator') or meta.get('center') or 'NASA'}", author=meta.get("secondary_creator", ""),
                                  commercial_use_known=None, search_query=q, retrieved_at=_now()))
        except (KeyError, IndexError, TypeError):
            continue
    return out


def wikimedia(q: str) -> list[StockAsset]:
    d = _json("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search", "gsrsearch": f"{q} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": PER_PROVIDER * 2,     # twice as many: digitised book plates are filtered out later
        "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": 1600}))
    out = []
    for page in (d.get("query", {}).get("pages") or {}).values():
        try:
            ii = page["imageinfo"][0]
            ext = ii.get("extmetadata", {})
            lic = (ext.get("LicenseShortName") or {}).get("value", "")
            free = bool(re.match(r"(CC0|Public domain|PD|CC BY(-SA)?\b)", lic, re.I)) and "NC" not in lic.upper() and "ND" not in lic.upper()
            author = _clean_author((ext.get("Artist") or {}).get("value", ""))
            out.append(StockAsset(id=f"wikimedia:{page['pageid']}", provider="wikimedia", provider_asset_id=str(page["pageid"]),
                                  source_page_url=ii.get("descriptionurl", ""), download_url=ii.get("thumburl") or ii.get("url"), thumbnail_url=ii.get("thumburl"),
                                  title=page.get("title", "").removeprefix("File:"), width=ii.get("width"), height=ii.get("height"), license_name=lic,
                                  license_url=(ext.get("LicenseUrl") or {}).get("value", ""), author=author,
                                  attribution_text=f"{author} / Wikimedia Commons / {lic}".strip(" /"), commercial_use_known=True if free else None,
                                  search_query=q, retrieved_at=_now()))
        except (KeyError, IndexError, TypeError):
            continue
    return out


def pexels(q: str) -> list[StockAsset]:
    d = _json("https://api.pexels.com/v1/search?" + urllib.parse.urlencode({"query": q, "per_page": PER_PROVIDER}), {"Authorization": os.environ["PEXELS_API_KEY"]})
    out = []
    for p in d.get("photos", []):
        try:
            out.append(StockAsset(id=f"pexels:{p['id']}", provider="pexels", provider_asset_id=str(p["id"]), source_page_url=p.get("url", ""),
                                  download_url=p["src"].get("large2x") or p["src"]["original"], thumbnail_url=p["src"].get("medium"), title=p.get("alt", ""),
                                  width=p.get("width"), height=p.get("height"), license_name="Pexels License", license_url="https://www.pexels.com/license/",
                                  author=p.get("photographer", ""), attribution_text=f"Photo by {p.get('photographer', '')} on Pexels", commercial_use_known=True,
                                  search_query=q, retrieved_at=_now()))
        except (KeyError, TypeError):
            continue
    return out


def pixabay(q: str) -> list[StockAsset]:
    d = _json("https://pixabay.com/api/?" + urllib.parse.urlencode({"key": os.environ["PIXABAY_API_KEY"], "q": q, "image_type": "photo", "per_page": max(3, PER_PROVIDER), "safesearch": "true"}))
    out = []
    for p in d.get("hits", [])[:PER_PROVIDER]:
        try:
            out.append(StockAsset(id=f"pixabay:{p['id']}", provider="pixabay", provider_asset_id=str(p["id"]), source_page_url=p.get("pageURL", ""),
                                  download_url=p.get("largeImageURL"), thumbnail_url=p.get("webformatURL"), title=p.get("tags", ""), width=p.get("imageWidth"),
                                  height=p.get("imageHeight"), license_name="Pixabay Content License", license_url="https://pixabay.com/service/license-summary/",
                                  author=p.get("user", ""), attribution_text=f"Image by {p.get('user', '')} from Pixabay", commercial_use_known=True,
                                  search_query=q, retrieved_at=_now()))
        except (KeyError, TypeError):
            continue
    return out


def _host_ok(url: str) -> bool:
    u = urllib.parse.urlparse(url or "")
    return u.scheme == "https" and any((u.hostname or "") == h or (u.hostname or "").endswith("." + h) for h in DOWNLOAD_HOSTS)


def openverse(q: str) -> list[StockAsset]:
    """Openverse (the open-licence search of WordPress, no key; anonymous use is rate limited, which the 24 h query cache keeps small). Only items whose file lives on a permitted host and whose licence
    allows commercial use and changes; Flickr serves them at 1024 px at most."""
    d = _json("https://api.openverse.org/v1/images/?" + urllib.parse.urlencode({"q": q, "license_type": "commercial", "page_size": PER_PROVIDER * 3, "mature": "false"}), timeout=OPENVERSE_TIMEOUT)
    out = []
    for r in d.get("results", []):
        try:
            lic = str(r["license"]).lower()
            if lic not in FREE_LICENSES or not _host_ok(r["url"]):
                continue
            ver = f" {r['license_version']}" if r.get("license_version") else ""
            name = f"{FREE_LICENSES[lic]}{ver}"
            creator = r.get("creator") or ""
            out.append(StockAsset(id=f"openverse:{r['id']}", provider="openverse", provider_asset_id=str(r["id"]), source_page_url=r.get("foreign_landing_url", ""), download_url=r["url"],
                                  thumbnail_url=r.get("thumbnail"), title=r.get("title") or "", width=r.get("width"), height=r.get("height"), license_name=name, license_url=r.get("license_url") or "",
                                  author=creator, attribution_text=(r.get("attribution") or f"{creator} / {r.get('source', 'Openverse')} / {name}").strip(" /"), commercial_use_known=True,
                                  search_query=q, retrieved_at=_now()))
        except (KeyError, TypeError):
            continue
        if len(out) >= PER_PROVIDER:
            break
    return out


def unsplash(q: str) -> list[StockAsset]:
    """Official Unsplash Search Photos API (requires UNSPLASH_ACCESS_KEY)."""
    d = _json("https://api.unsplash.com/search/photos?" + urllib.parse.urlencode({"query": q, "per_page": PER_PROVIDER, "orientation": "landscape"}), {"Authorization": f"Client-ID {os.environ['UNSPLASH_ACCESS_KEY']}"})
    out = []
    for p in d.get("results", []):
        try:
            urls = p.get("urls") or {}
            user = p.get("user") or {}
            out.append(StockAsset(id=f"unsplash:{p['id']}", provider="unsplash", provider_asset_id=str(p["id"]),
                                  source_page_url=p.get("links", {}).get("html", ""),
                                  download_url=urls.get("regular") or urls.get("full"),
                                  thumbnail_url=urls.get("small"), title=p.get("description") or p.get("alt_description") or "",
                                  width=p.get("width"), height=p.get("height"),
                                  license_name="Unsplash License", license_url="https://unsplash.com/license",
                                  author=user.get("name") or user.get("username", ""),
                                  attribution_text=f"Photo by {user.get('name', '')} on Unsplash",
                                  commercial_use_known=True, search_query=q, retrieved_at=_now()))
        except (KeyError, TypeError):
            continue
    return out


PROVIDERS = {"nasa": (nasa, None), "wikimedia": (wikimedia, None), "openverse": (openverse, None), "pexels": (pexels, "PEXELS_API_KEY"), "pixabay": (pixabay, "PIXABAY_API_KEY"), "unsplash": (unsplash, "UNSPLASH_ACCESS_KEY")}


# ---------- video adapters (same rules: official APIs, one malformed item is skipped) ----------
def _best_video(files: list[dict], max_width: int = 1920) -> dict | None:
    """The widest file that fits max_width (a 4K file would only cost the CPU render time); the smallest one when every file is larger."""
    usable = [f for f in files if f.get("url") and f.get("width")]
    fitting = [f for f in usable if f["width"] <= max_width]
    return max(fitting, key=lambda f: f["width"]) if fitting else min(usable, key=lambda f: f["width"], default=None)


def pexels_videos(q: str) -> list[StockAsset]:
    d = _json("https://api.pexels.com/v1/videos/search?" + urllib.parse.urlencode({"query": q, "per_page": PER_PROVIDER}), {"Authorization": os.environ["PEXELS_API_KEY"]})
    out = []
    for v in d.get("videos", []):
        try:
            f = _best_video([{"url": x.get("link"), "width": x.get("width")} for x in v.get("video_files", []) if x.get("file_type") == "video/mp4"])
            if not f:
                continue
            user = v.get("user") or {}
            out.append(StockAsset(id=f"pexels-video:{v['id']}", provider="pexels", provider_asset_id=str(v["id"]), source_page_url=v.get("url", ""), download_url=f["url"],
                                  media_type="video", thumbnail_url=v.get("image"), title=q, width=v.get("width"), height=v.get("height"), duration_s=v.get("duration"),
                                  license_name="Pexels License", license_url="https://www.pexels.com/license/", author=user.get("name", ""),
                                  attribution_text=f"Video by {user.get('name', '')} on Pexels", commercial_use_known=True, search_query=q, retrieved_at=_now()))
        except (KeyError, TypeError):
            continue
    return out


def pixabay_videos(q: str) -> list[StockAsset]:
    d = _json("https://pixabay.com/api/videos/?" + urllib.parse.urlencode({"key": os.environ["PIXABAY_API_KEY"], "q": q, "per_page": max(3, PER_PROVIDER), "safesearch": "true"}))
    out = []
    for p in d.get("hits", [])[:PER_PROVIDER]:
        try:
            f = _best_video(list((p.get("videos") or {}).values()))
            if not f:
                continue
            out.append(StockAsset(id=f"pixabay-video:{p['id']}", provider="pixabay", provider_asset_id=str(p["id"]), source_page_url=p.get("pageURL", ""), download_url=f["url"],
                                  media_type="video", thumbnail_url=f"https://i.vimeocdn.com/video/{p['picture_id']}_640x360.jpg" if p.get("picture_id") else None,
                                  title=p.get("tags", ""), width=f.get("width"), height=f.get("height"), duration_s=p.get("duration"),
                                  license_name="Pixabay Content License", license_url="https://pixabay.com/service/license-summary/", author=p.get("user", ""),
                                  attribution_text=f"Video by {p.get('user', '')} from Pixabay", commercial_use_known=True, search_query=q, retrieved_at=_now()))
        except (KeyError, TypeError):
            continue
    return out


def nasa_videos(q: str) -> list[StockAsset]:
    d = _json("https://images-api.nasa.gov/search?" + urllib.parse.urlencode({"q": q, "media_type": "video"}))
    out = []
    for it in d.get("collection", {}).get("items", [])[:3]:                       # each video needs a second request for its file list: only the first few
        try:
            meta, links = it["data"][0], it.get("links") or []
            nid = meta["nasa_id"]
            files = json.loads(_open(urllib.parse.quote(it["href"], safe=":/")))
            mp4 = [u for u in files if isinstance(u, str) and u.lower().endswith(".mp4") and "preview" not in u.lower()]
            pick = next((u for u in mp4 if "~medium" in u), None) or next((u for u in mp4 if "~orig" not in u), None) or (mp4[0] if mp4 else None)
            if not pick:
                continue
            out.append(StockAsset(id=f"nasa-video:{nid}", provider="nasa", provider_asset_id=nid, source_page_url=f"https://images.nasa.gov/details/{urllib.parse.quote(nid)}",
                                  download_url=pick.replace("http://", "https://"), media_type="video", thumbnail_url=next((l["href"] for l in links if l.get("render") == "image"), None),
                                  title=meta.get("title", ""), license_name="NASA media guidelines (credit required; third-party content may be restricted)",
                                  license_url="https://www.nasa.gov/nasa-brand-center/images-and-media/", author=meta.get("secondary_creator", ""),
                                  attribution_text=f"Credit: {meta.get('secondary_creator') or meta.get('center') or 'NASA'}", commercial_use_known=None, search_query=q, retrieved_at=_now()))
        except (KeyError, IndexError, TypeError, ValueError, StockError):
            continue
    return out


def _wikimedia_derivative(vi: dict) -> tuple[str | None, int | None, int | None]:
    """The transcode to use for a Commons video: the widest WebM/VP9 derivative up to 1920 wide (originals can be 4K and gigabytes), else the original file. -> (url, width, height)"""
    ders = [d for d in vi.get("derivatives", []) if "vp9" in str(d.get("type", "")).lower() and d.get("src") and d.get("width") and d["width"] <= 1920 and not str(d["src"]).endswith("utm_content=original")]
    best = max(ders, key=lambda d: d["width"], default=None)
    return (best["src"], best["width"], best.get("height")) if best else (vi.get("url"), vi.get("width"), vi.get("height"))


def wikimedia_videos(q: str) -> list[StockAsset]:
    d = _json("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search", "gsrsearch": f"{q} filetype:video", "gsrnamespace": 6, "gsrlimit": PER_PROVIDER,
        "prop": "videoinfo", "viprop": "url|size|mime|derivatives|extmetadata", "viurlwidth": 1280}))
    out = []
    for page in (d.get("query", {}).get("pages") or {}).values():
        try:
            ii = page["videoinfo"][0]
            ext = ii.get("extmetadata", {})
            lic = (ext.get("LicenseShortName") or {}).get("value", "")
            free = bool(re.match(r"(CC0|Public domain|PD|CC BY(-SA)?\b)", lic, re.I)) and "NC" not in lic.upper() and "ND" not in lic.upper()
            author = _clean_author((ext.get("Artist") or {}).get("value", ""))
            url, w, h = _wikimedia_derivative(ii)
            if not url:
                continue
            out.append(StockAsset(id=f"wikimedia-video:{page['pageid']}", provider="wikimedia", provider_asset_id=str(page["pageid"]), source_page_url=ii.get("descriptionurl", ""),
                                  download_url=url, media_type="video", thumbnail_url=ii.get("thumburl"), title=page.get("title", "").removeprefix("File:"),
                                  width=w, height=h, duration_s=ii.get("duration"), license_name=lic, license_url=(ext.get("LicenseUrl") or {}).get("value", ""),
                                  author=author, attribution_text=f"{author} / Wikimedia Commons / {lic}".strip(" /"), commercial_use_known=True if free else None,
                                  search_query=q, retrieved_at=_now()))
        except (KeyError, IndexError, TypeError):
            continue
    return out


def _archive_licence(url: str) -> str | None:
    """The licence of an Internet Archive item from its licenseurl; None when it does not allow commercial use and changes (or is unknown)."""
    u = (url or "").lower()
    if "publicdomain/zero" in u:
        return "CC0 1.0"
    if "publicdomain/mark" in u:
        return "Public Domain Mark 1.0"
    m = re.search(r"creativecommons\.org/licenses/(by|by-sa)/([\d.]+)", u)
    return f"{FREE_LICENSES[m.group(1)]} {m.group(2)}" if m else None


def archive_videos(q: str) -> list[StockAsset]:
    """Internet Archive (no key): short items with a free licence, the H.264 derivative the Archive makes of every upload. The item's metadata gives the file list and the duration."""
    d = _json("https://archive.org/advancedsearch.php?" + urllib.parse.urlencode({"q": f"({q}) AND mediatype:movies AND licenseurl:*", "fl[]": ["identifier", "title", "creator", "licenseurl"], "rows": 30,
                                                                              "sort[]": "downloads desc", "output": "json"}, doseq=True))
    out = []
    for doc in d.get("response", {}).get("docs", []):
        if len(out) >= 3:                                                   # each item needs a second request for its files
            break
        lic = _archive_licence(doc.get("licenseurl") if isinstance(doc.get("licenseurl"), str) else "")
        if not lic:
            continue
        try:
            ident = doc["identifier"]
            files = _json(f"https://archive.org/metadata/{urllib.parse.quote(ident)}").get("files", [])
            mp4 = [f for f in files if str(f.get("name", "")).lower().endswith(".mp4") and f.get("format") in ("h.264", "MPEG4") and str(f.get("width", "")).isdigit()]
            best = _best_video([{"url": f["name"], "width": int(f["width"]), "height": int(f.get("height") or 0), "length": f.get("length")} for f in mp4])
            length = float(best["length"]) if best and best.get("length") else None
            if not best or not length or length > MAX_ARCHIVE_SECONDS:
                continue
            creator = doc.get("creator") if isinstance(doc.get("creator"), str) else ""
            title = doc.get("title") if isinstance(doc.get("title"), str) else ident
            out.append(StockAsset(id=f"archive-video:{ident}", provider="archive", provider_asset_id=ident, source_page_url=f"https://archive.org/details/{urllib.parse.quote(ident)}",
                                  download_url=f"https://archive.org/download/{urllib.parse.quote(ident)}/{urllib.parse.quote(best['url'])}", media_type="video",
                                  thumbnail_url=f"https://archive.org/services/img/{urllib.parse.quote(ident)}", title=title, width=best["width"], height=best.get("height") or None, duration_s=length,
                                  license_name=lic, license_url=doc["licenseurl"], author=creator, attribution_text=f"{creator or 'Unknown'} / Internet Archive / {lic}",
                                  commercial_use_known=True, search_query=q, retrieved_at=_now()))
        except (KeyError, TypeError, ValueError, StockError):
            continue
    return out


VIDEO_PROVIDERS = {"nasa": (nasa_videos, None), "wikimedia": (wikimedia_videos, None), "archive": (archive_videos, None), "pexels": (pexels_videos, "PEXELS_API_KEY"), "pixabay": (pixabay_videos, "PIXABAY_API_KEY")}


def providers_status() -> dict:
    """{provider: {"available": bool, "reason": str}}; only names of environment variables are ever shown."""
    return {n: {"available": key is None or bool(os.environ.get(key)), "reason": "" if key is None or os.environ.get(key) else f"set {key} to enable"}
            for n, (_, key) in PROVIDERS.items()}


def _rank(a: StockAsset, want_ratio: float | None) -> tuple:
    ratio_gap = abs(a.width / a.height - want_ratio) if want_ratio and a.width and a.height else 1.0
    return (0 if a.commercial_use_known else 1, round(ratio_gap, 1), -(a.width or 0), a.id)


def available_providers(kind: str = "image") -> tuple[str, ...]:
    """The providers that would be asked for this kind of media now (those whose key, if they need one, is set): part of the key of the query cache, so a provider that is added or a key that is
    set is used at once instead of after the 24 h of the cache."""
    return tuple(n for n, (_, key) in (VIDEO_PROVIDERS if kind == "video" else PROVIDERS).items() if key is None or os.environ.get(key))


def search(query: str, aspect: str = "16:9", kind: str = "image") -> tuple[list[StockAsset], dict]:
    """Results of every available provider, ranked (known rights, aspect ratio, size), duplicates by id removed. One provider failing never fails the rest.
    kind: "image" (default, the existing behaviour) or "video"."""
    w, _, h = aspect.partition(":")
    want = float(w) / float(h) if w.replace(".", "").isdigit() and h.replace(".", "").isdigit() and float(h) else None
    found, seen, state = [], set(), {}
    for name, (fn, key) in (VIDEO_PROVIDERS if kind == "video" else PROVIDERS).items():
        if key and not os.environ.get(key):
            state[name] = {"ok": False, "error": f"unavailable: set {key}"}
            continue
        try:
            items = fn(query)
            state[name] = {"ok": True, "count": len(items)}
        except StockError as e:
            state[name] = {"ok": False, "error": str(e)}
            continue
        for a in items:
            if a.id not in seen:
                seen.add(a.id)
                found.append(a)
    return sorted(found, key=lambda a: _rank(a, want)), state


# ---------- per project ----------
def _load(f: Path, default):
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else default
    except (OSError, ValueError):
        return default


def candidates_of(pdir: Path) -> dict:
    return _load(pdir / "candidates.json", {}).get("slots", {})


def _query(text: str) -> str:
    return " ".join(re.sub(r"[^A-Za-z0-9 ]+", " ", text).split()[:8])


def collect(pdir: Path, slots: list[str] | None = None) -> dict:
    """Search for the given requirements (default: all required ones). Results are kept per slot in candidates.json; nothing is downloaded."""
    pm = _load(pdir / "prompts_map.json", {"prompts": []})["prompts"]
    out, state = dict(_load(pdir / "candidates.json", {}).get("slots", {})), {}
    for p in pm:
        if (slots is not None and p["slot"] not in slots) or not p.get("required", True):
            continue
        res, state = search(_query(p["text"]), p.get("ratio", "16:9"))
        out[p["slot"]] = [a.model_dump() for a in res]
    data = {"slots": out, "providers": state or providers_status(), "at": _now()}
    (pdir / "candidates.json").write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return data


def _is_video(data: bytes) -> bool:
    """MP4/MOV (ftyp box), WebM/Matroska (EBML header) or Ogg."""
    return data[4:8] == b"ftyp" or data[:4] == b"\x1aE\xdf\xa3" or data[:4] == b"OggS"


def permitted_url(cand: dict) -> str:
    """The download URL a provider gave, only when it is https on a known provider host (also what ffmpeg may read directly for a video)."""
    u = urllib.parse.urlparse(cand.get("download_url") or "")
    host = u.hostname or ""
    if u.scheme != "https" or not any(host == h or host.endswith("." + h) for h in DOWNLOAD_HOSTS):
        raise StockError("this result has no permitted download address")
    return u.geturl()


def download(cand: dict) -> bytes:
    """Only the download URL a provider gave, only https on a known provider host, only an image (or, for a video result, a video), bounded in size."""
    url = permitted_url(cand)
    video = cand.get("media_type") == "video"
    limit = MAX_VIDEO_BYTES if video else MAX_BYTES
    data = _open(url) if not video else _open(url, None, limit)
    if len(data) > limit:
        raise StockError("the file is too large")
    if video:
        if not _is_video(data):
            raise StockError("the download is not a video")
    elif not (data[:4] == b"\x89PNG" or data[:3] == b"\xff\xd8\xff" or data[:4] == b"RIFF"):
        raise StockError("the download is not an image")
    return data


def record_credit(pdir: Path, slot: str, cand: dict, file: str) -> None:
    f = pdir / "credits.json"
    rows = [r for r in _load(f, []) if r.get("slot") != slot]
    rows.append({"slot": slot, "file": file, "provider": cand["provider"], "source_page_url": cand.get("source_page_url", ""), "author": cand.get("author", ""),
                 "license_name": cand.get("license_name", ""), "license_url": cand.get("license_url", ""), "attribution_text": cand.get("attribution_text", ""),
                 "commercial_use_known": cand.get("commercial_use_known"), "at": _now()})
    f.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
