"""Stock providers (backend/stock.py): normalisation, errors, missing keys, rights metadata, download rules, credits. The network is replaced
(stock._open / urllib), so nothing here needs internet or a key. Run: python -m pytest tests/test_stock.py -q"""
import io
import json
import urllib.error

import pytest

from backend import stock

NASA = {"collection": {"items": [
    {"data": [{"nasa_id": "PIA1", "title": "Mars", "center": "JPL"}], "links": [{"render": "image", "href": "https://images-assets.nasa.gov/image/PIA1/PIA1~thumb.jpg"}]},
    {"data": [{"title": "no id"}]},                                   # malformed: skipped
]}}
COMMONS = {"query": {"pages": {"1": {"pageid": 1, "title": "File:Nile.jpg", "imageinfo": [{
    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Nile.jpg", "thumburl": "https://upload.wikimedia.org/t/Nile.jpg", "width": 1600, "height": 900,
    "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"}, "Artist": {"value": "<a href='x'>Ann</a>"}, "LicenseUrl": {"value": "https://cc/by-sa"}}}]},
    "2": {"pageid": 2, "title": "File:Nc.jpg", "imageinfo": [{"thumburl": "https://upload.wikimedia.org/t/Nc.jpg", "extmetadata": {"LicenseShortName": {"value": "CC BY-NC 4.0"}}}]}}}}
OPENVERSE = {"results": [
    {"id": "ov1", "title": "Office", "creator": "Gus", "license": "by", "license_version": "2.0", "license_url": "https://creativecommons.org/licenses/by/2.0/", "url": "https://live.staticflickr.com/1/a_b.jpg",
     "foreign_landing_url": "https://www.flickr.com/photos/1/2", "width": 1024, "height": 683, "source": "flickr", "attribution": "\"Office\" by Gus is licensed under CC BY 2.0."},
    {"id": "ov2", "title": "NoDerivs", "creator": "X", "license": "by-nd", "url": "https://live.staticflickr.com/1/nd.jpg", "width": 1024, "height": 683},                    # no changes allowed: skipped
    {"id": "ov3", "title": "Elsewhere", "creator": "Y", "license": "cc0", "url": "https://evil.example.org/x.jpg", "width": 2000, "height": 1000},                         # a host that is not permitted: skipped
    {"id": "ov4", "title": "Public", "creator": "", "license": "pdm", "url": "https://live.staticflickr.com/4/p.jpg", "width": 1024, "height": 768, "source": "flickr"},
    {"title": "malformed"}]}
ARCHIVE_SEARCH = {"response": {"docs": [
    {"identifier": "short-cc", "title": "A short film", "creator": "Zed", "licenseurl": "https://creativecommons.org/licenses/by/4.0/"},
    {"identifier": "nc-film", "title": "NC film", "licenseurl": "https://creativecommons.org/licenses/by-nc/4.0/"},                                                             # not commercial: skipped
    {"identifier": "long-pd", "title": "A long recording", "licenseurl": "https://creativecommons.org/publicdomain/mark/1.0/"},                                                  # too long to judge by its title: skipped
    {"identifier": "pd-mark", "title": "Old city", "creator": ["A", "B"], "licenseurl": "https://creativecommons.org/publicdomain/mark/1.0/"}]}}
ARCHIVE_META = {"short-cc": {"files": [{"name": "film.mp4", "format": "h.264", "width": "640", "height": "480", "length": "120.5"}, {"name": "film.ogv", "format": "Ogg Video", "width": "640"},
                                       {"name": "film_512kb.mp4", "format": "512Kb MPEG4", "width": "320", "length": "120.5"}]},
                "long-pd": {"files": [{"name": "rec.mp4", "format": "h.264", "width": "640", "height": "480", "length": "7200"}]},
                "pd-mark": {"files": [{"name": "city.mp4", "format": "MPEG4", "width": "480", "height": "360", "length": "300"}]}}
PEXELS = {"photos": [{"id": 7, "url": "https://pexels.com/photo/7", "photographer": "Bo", "width": 4000, "height": 2250, "alt": "river",
                      "src": {"large2x": "https://images.pexels.com/7.jpg", "medium": "https://images.pexels.com/7m.jpg"}}, {"id": 8}]}
PIXABAY = {"hits": [{"id": 9, "pageURL": "https://pixabay.com/p/9", "user": "Cy", "largeImageURL": "https://pixabay.com/9.jpg", "imageWidth": 3000, "imageHeight": 2000, "tags": "sea"}]}


@pytest.fixture
def net(monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY", "k1")
    monkeypatch.setenv("PIXABAY_API_KEY", "k2")

    def fake(url, headers=None, **kw):
        host = url.split("/")[2]
        data = {"images-api.nasa.gov": NASA, "commons.wikimedia.org": COMMONS, "api.openverse.org": OPENVERSE, "api.pexels.com": PEXELS, "pixabay.com": PIXABAY}[host]
        return json.dumps(data).encode()
    monkeypatch.setattr(stock, "_open", fake)


def test_every_adapter_normalises_to_one_schema_and_keeps_rights(net):
    found, state = stock.search("river sunrise", "16:9")
    by = {a.provider: a for a in reversed(found)}      # the best-ranked result of each provider
    by["wikimedia"] = next(a for a in found if a.id == "wikimedia:1")
    assert set(by) == {"nasa", "wikimedia", "openverse", "pexels", "pixabay"} and all(s["ok"] for s in state.values())
    assert by["pexels"].attribution_text == "Photo by Bo on Pexels" and by["pexels"].commercial_use_known is True and by["pexels"].source_page_url
    assert by["nasa"].commercial_use_known is None and "credit" in by["nasa"].license_name.lower()             # unclear rights are never claimed as free
    assert by["wikimedia"].author == "Ann" and by["wikimedia"].license_name == "CC BY-SA 4.0" and by["wikimedia"].commercial_use_known is True
    assert next(a for a in found if a.id == "wikimedia:2").commercial_use_known is None                      # NC licence: not known as commercial
    assert all(a.search_query == "river sunrise" and a.retrieved_at for a in found)
    assert len({a.id for a in found}) == len(found) and "nasa:PIA1" in {a.id for a in found}               # malformed items were skipped


def test_known_rights_rank_first(net):
    found, _ = stock.search("river", "16:9")
    assert found[0].commercial_use_known is True and found[-1].commercial_use_known is None


def test_missing_keys_mark_a_provider_unavailable_without_a_request(monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    calls = []
    monkeypatch.setattr(stock, "_open", lambda url, headers=None, **kw: calls.append(url) or json.dumps(NASA if "nasa" in url else COMMONS).encode())
    found, state = stock.search("x")
    assert not state["pexels"]["ok"] and "PEXELS_API_KEY" in state["pexels"]["error"] and not any("pexels" in c or "pixabay" in c for c in calls)
    status = stock.providers_status()
    assert status["nasa"]["available"] and not status["pixabay"]["available"] and "PIXABAY_API_KEY" in status["pixabay"]["reason"]
    assert {a.provider for a in found} == {"nasa", "wikimedia"} or {a.provider for a in found} == {"nasa", "wikimedia", "openverse"}


def test_one_failing_provider_never_fails_the_search(net, monkeypatch):
    real = stock._open

    def flaky(url, headers=None, **kw):
        if "pexels" in url:
            raise stock.StockError("rate limit reached, try again later")
        if "nasa" in url:
            return b"{ not json"
        return real(url, headers, **kw)
    monkeypatch.setattr(stock, "_open", flaky)
    found, state = stock.search("river")
    assert state["pexels"]["error"].startswith("rate limit") and not state["nasa"]["ok"] and state["pixabay"]["ok"]
    assert {a.provider for a in found} == {"wikimedia", "openverse", "pixabay"}


def test_empty_results(monkeypatch):
    monkeypatch.setattr(stock, "_open", lambda url, headers=None, **kw: b"{}")
    found, state = stock.search("nothing")
    assert found == [] and state["nasa"] == {"ok": True, "count": 0}


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_http_errors_timeouts_and_retry(monkeypatch):
    calls = []

    def urlopen(req, timeout):
        calls.append(timeout)
        raise urllib.error.HTTPError(req.full_url, 429, "slow down", {}, None)
    monkeypatch.setattr(stock.urllib.request, "urlopen", urlopen)
    with pytest.raises(stock.StockError, match="rate limit") as e:
        stock._open("https://api.pexels.com/x", {"Authorization": "secret-key"})
    assert len(calls) == 1 and "secret-key" not in str(e.value) and calls[0] == stock.TIMEOUT          # 429 is never retried

    seq = iter([urllib.error.HTTPError("u", 503, "x", {}, None), Resp(b'{"ok": 1}')])

    def flaky(req, timeout):
        r = next(seq)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(stock.urllib.request, "urlopen", flaky)
    assert stock._json("https://x.test/") == {"ok": 1}                                                  # one bounded retry for a 5xx

    def timed_out(req, timeout):
        raise TimeoutError()
    monkeypatch.setattr(stock.urllib.request, "urlopen", timed_out)
    with pytest.raises(stock.StockError, match="did not answer"):
        stock._open("https://x.test/")


def test_download_only_from_permitted_https_hosts_and_only_images(monkeypatch):
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    monkeypatch.setattr(stock, "_open", lambda url, headers=None, **kw: png)
    assert stock.download({"download_url": "https://images.pexels.com/a.png"}) == png
    for bad in ("http://images.pexels.com/a.png", "https://evil.example/a.png", "https://images.pexels.com.evil.example/a.png", "file:///etc/passwd", None):
        with pytest.raises(stock.StockError, match="permitted"):
            stock.download({"download_url": bad})
    monkeypatch.setattr(stock, "_open", lambda url, headers=None, **kw: b"<html>not an image</html>")
    with pytest.raises(stock.StockError, match="not an image"):
        stock.download({"download_url": "https://images.pexels.com/a.png"})


PEXELS_V = {"videos": [{"id": 5, "url": "https://pexels.com/video/5", "image": "https://images.pexels.com/5.jpg", "duration": 12, "width": 3840, "height": 2160, "user": {"name": "Di"},
                        "video_files": [{"link": "https://videos.pexels.com/5-uhd.mp4", "file_type": "video/mp4", "width": 3840}, {"link": "https://videos.pexels.com/5-hd.mp4", "file_type": "video/mp4", "width": 1920},
                                        {"link": "https://videos.pexels.com/5-sd.mp4", "file_type": "video/mp4", "width": 960}, {"link": "https://videos.pexels.com/5.webm", "file_type": "video/webm", "width": 1920}]},
                       {"id": 6, "video_files": []}]}
PIXABAY_V = {"hits": [{"id": 3, "pageURL": "https://pixabay.com/v/3", "user": "Ed", "tags": "city", "duration": 9, "picture_id": "123",
                       "videos": {"large": {"url": "", "width": 0}, "medium": {"url": "https://cdn.pixabay.com/3m.mp4", "width": 1280, "height": 720}, "small": {"url": "https://cdn.pixabay.com/3s.mp4", "width": 640, "height": 360}}}]}
NASA_V = {"collection": {"items": [{"data": [{"nasa_id": "V1", "title": "Launch", "center": "KSC"}], "href": "https://images-assets.nasa.gov/video/V1/collection.json", "links": []}]}}
NASA_V_FILES = ["http://images-assets.nasa.gov/video/V1/V1~orig.mp4", "http://images-assets.nasa.gov/video/V1/V1~medium.mp4", "http://images-assets.nasa.gov/video/V1/V1~preview.mp4"]
COMMONS_V = {"query": {"pages": {"1": {"pageid": 1, "title": "File:Tide.webm", "videoinfo": [{
    "url": "https://upload.wikimedia.org/Tide.webm", "descriptionurl": "https://commons.wikimedia.org/wiki/File:Tide.webm", "duration": 20.5, "width": 3840, "height": 2160,
    "derivatives": [{"type": 'video/webm; codecs="vp9, opus"', "src": "https://upload.wikimedia.org/Tide.webm?utm_content=original", "width": 3840, "height": 2160},
                    {"type": 'video/webm; codecs="vp9, opus"', "src": "https://upload.wikimedia.org/Tide.webm.1080p.vp9.webm", "width": 1920, "height": 1080},
                    {"type": 'video/webm; codecs="vp9, opus"', "src": "https://upload.wikimedia.org/Tide.webm.480p.vp9.webm", "width": 854, "height": 480},
                    {"type": 'video/quicktime; codecs="mp4v"', "src": "https://upload.wikimedia.org/Tide.webm.360p.mpeg4.mov", "width": 640, "height": 360}],
    "extmetadata": {"LicenseShortName": {"value": "CC0"}, "Artist": {"value": "Fay"}}}]}}}}


@pytest.fixture
def vnet(monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY", "k1")
    monkeypatch.setenv("PIXABAY_API_KEY", "k2")

    def fake(url, headers=None, limit=0):
        if url.endswith("collection.json"):
            return json.dumps(NASA_V_FILES).encode()
        if url.startswith("https://archive.org/advancedsearch.php"):
            return json.dumps(ARCHIVE_SEARCH).encode()
        if url.startswith("https://archive.org/metadata/"):
            return json.dumps(ARCHIVE_META[url.rsplit("/", 1)[1]]).encode()
        data = {"images-api.nasa.gov": NASA_V, "commons.wikimedia.org": COMMONS_V, "api.pexels.com": PEXELS_V, "pixabay.com": PIXABAY_V}[url.split("/")[2]]
        return json.dumps(data).encode()
    monkeypatch.setattr(stock, "_open", fake)


def test_video_adapters_pick_a_cpu_friendly_file_and_keep_rights(vnet):
    found, state = stock.search("harbour", "16:9", kind="video")
    by = {a.provider: a for a in found}
    assert set(by) == {"nasa", "wikimedia", "archive", "pexels", "pixabay"} and all(s["ok"] for s in state.values()) and all(a.media_type == "video" for a in found)
    assert by["pexels"].download_url == "https://videos.pexels.com/5-hd.mp4" and by["pexels"].duration_s == 12 and by["pexels"].attribution_text == "Video by Di on Pexels"      # not the 4K file, not webm
    assert by["pixabay"].download_url == "https://cdn.pixabay.com/3m.mp4" and by["pixabay"].commercial_use_known is True                                                  # the empty "large" slot is skipped
    assert by["nasa"].download_url == "https://images-assets.nasa.gov/video/V1/V1~medium.mp4" and by["nasa"].commercial_use_known is None                                # https, medium, no preview file
    assert by["wikimedia"].duration_s == 20.5 and by["wikimedia"].commercial_use_known is True
    assert by["wikimedia"].download_url == "https://upload.wikimedia.org/Tide.webm.1080p.vp9.webm" and by["wikimedia"].width == 1920            # the 1080p transcode, not the 4K original
    assert [a.id for a in found if a.provider == "pexels"] == ["pexels-video:5"]                                                                                          # the item without a file is skipped


def test_video_download_checks_the_container_and_the_host(monkeypatch):
    mp4 = b"\x00\x00\x00\x18ftypmp42" + b"0" * 20
    monkeypatch.setattr(stock, "_open", lambda url, headers=None, limit=0: mp4)
    cand = {"download_url": "https://videos.pexels.com/a.mp4", "media_type": "video"}
    assert stock.download(cand) == mp4
    with pytest.raises(stock.StockError, match="permitted"):
        stock.download({"download_url": "https://evil.example/a.mp4", "media_type": "video"})
    monkeypatch.setattr(stock, "_open", lambda url, headers=None, limit=0: b"<html>no</html>" + b"0" * 20)
    with pytest.raises(stock.StockError, match="not a video"):
        stock.download(cand)
    monkeypatch.setattr(stock, "_open", lambda url, headers=None, limit=0: mp4 + b"0" * (stock.MAX_VIDEO_BYTES + 1))
    with pytest.raises(stock.StockError, match="too large"):
        stock.download(cand)


def test_wikimedia_thumbnail_host_is_permitted_but_lookalikes_are_not(monkeypatch):
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    monkeypatch.setattr(stock, "_open", lambda url, headers=None, limit=0: png)
    assert stock.download({"download_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/a/a3/X.jpg/1600px-X.jpg"}) == png        # Commons thumbnails are served from this host
    for bad in ("https://thumb.wikimedia.org.evil.example/x.jpg", "https://evilthumb.wikimedia.org.example/x.jpg", "http://thumb.wikimedia.org/x.jpg"):
        with pytest.raises(stock.StockError, match="permitted"):
            stock.download({"download_url": bad})


def test_commons_credits_are_short_and_readable():
    assert stock._clean_author("<a href='x'>Ann</a>") == "Ann"
    messy = "Mount_Everest_as_seen_from_Drukair2.jpg: shrimpo1967 derivative work: Papa Lima Whiskey 2 (talk)"
    assert stock._clean_author(messy) == "shrimpo1967 / Papa Lima Whiskey 2"
    long = "A" * 200
    assert len(stock._clean_author(long)) <= 80 and stock._clean_author(long).endswith("…")
    assert stock._clean_author("Luca Galuzzi (Lucag)") == "Luca Galuzzi (Lucag)"


# ---------- the providers that need no key: Openverse (photos) and the Internet Archive (videos) ----------
def test_openverse_keeps_only_free_licences_that_allow_changes_on_permitted_hosts(net):
    found, state = stock.search("office", "16:9")
    ov = {a.provider_asset_id: a for a in found if a.provider == "openverse"}
    assert state["openverse"]["ok"] and set(ov) == {"ov1", "ov4"}                                    # by-nd (no changes) and a host that is not permitted are skipped, so is the malformed item
    a = ov["ov1"]
    assert a.license_name == "CC BY 2.0" and a.commercial_use_known is True and a.download_url == "https://live.staticflickr.com/1/a_b.jpg" and a.author == "Gus"
    assert a.attribution_text == '"Office" by Gus is licensed under CC BY 2.0.' and a.source_page_url == "https://www.flickr.com/photos/1/2"
    assert ov["ov4"].license_name == "Public Domain Mark" and ov["ov4"].attribution_text == "flickr / Public Domain Mark"
    assert stock.permitted_url(a.model_dump()) == a.download_url                                       # Flickr's host is on the download allowlist


def test_internet_archive_videos_are_short_free_and_come_as_the_h264_file(vnet):
    found, _ = stock.search("film", "16:9", kind="video")
    ar = {a.provider_asset_id: a for a in found if a.provider == "archive"}
    assert set(ar) == {"short-cc", "pd-mark"}                                                          # a non-commercial licence and a two-hour recording are skipped
    a = ar["short-cc"]
    assert a.download_url == "https://archive.org/download/short-cc/film.mp4" and a.duration_s == 120.5 and a.width == 640 and a.media_type == "video"
    assert a.license_name == "CC BY 4.0" and a.commercial_use_known is True and a.attribution_text == "Zed / Internet Archive / CC BY 4.0"
    assert ar["pd-mark"].license_name == "Public Domain Mark 1.0" and ar["pd-mark"].author == "" and stock.permitted_url(a.model_dump()) == a.download_url


def test_archive_licences_allow_only_what_a_crop_or_a_dim_may_do():
    ok = stock._archive_licence
    assert ok("https://creativecommons.org/licenses/by/4.0/") == "CC BY 4.0" and ok("https://creativecommons.org/licenses/by-sa/3.0/") == "CC BY-SA 3.0"
    assert ok("https://creativecommons.org/publicdomain/zero/1.0/") == "CC0 1.0" and ok("https://creativecommons.org/publicdomain/mark/1.0/") == "Public Domain Mark 1.0"
    assert ok("https://creativecommons.org/licenses/by-nc/4.0/") is None and ok("https://creativecommons.org/licenses/by-nd/4.0/") is None and ok("") is None


def test_the_slow_anonymous_openverse_query_gets_a_longer_timeout(monkeypatch):
    seen = {}
    monkeypatch.setattr(stock, "_open", lambda url, headers=None, **kw: seen.update(kw) or b'{"results": []}')
    assert stock.openverse("x") == [] and seen == {"timeout": stock.OPENVERSE_TIMEOUT} and stock.OPENVERSE_TIMEOUT > stock.TIMEOUT
