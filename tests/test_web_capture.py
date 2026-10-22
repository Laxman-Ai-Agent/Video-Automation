"""Web capture (VIDEO_ENGINE/stages/web_capture.py): allowlist, robots.txt, Wikipedia result normalisation (fake network) and a REAL headless-browser capture of a local test page.
Run: python -m pytest tests/test_web_capture.py -q"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from VIDEO_ENGINE.stages import stock, web_capture as wc

PAGE = """<html><head><title>Test Mountain</title></head><body><div id="siteNotice">notice</div><h1>Test Mountain</h1>
<table class="infobox" style="width:520px;border:2px solid #333;font:20px sans-serif;border-spacing:0 14px"><tr><th colspan="2">Test Mountain</th></tr>
<tr><td>Elevation</td><td>8,849 m</td></tr><tr><td>Country</td><td>Nepal</td></tr><tr><td>First ascent</td><td>1953</td></tr></table>
<p>Some article text that is not part of the infobox.</p></body></html>"""
ROBOTS = "User-agent: *\nDisallow: /private\n"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        routes = {"/wiki/Mountain": (200, PAGE), "/wiki/NoInfobox": (200, "<html><body><p>plain page with no tables at all, only a paragraph of text.</p></body></html>"),
                  "/private/page": (200, PAGE), "/robots.txt": (200, ROBOTS), "/wiki/Gone": (404, "gone"), "/wiki/Elsewhere": (302, "")}
        code, body = routes.get(self.path, (404, "not found"))
        self.send_response(code)
        if self.path == "/wiki/Elsewhere":
            self.send_header("Location", "https://example.org/x")
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def site():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


LOCAL = dict(hosts=("127.0.0.1",), https_only=False)


def test_only_https_pages_on_the_allowlist_are_allowed():
    assert wc.host_allowed("https://en.wikipedia.org/wiki/Nile") and wc.host_allowed("https://www.nasa.gov/x") and wc.host_allowed("https://commons.wikimedia.org/wiki/File:A.jpg")
    for bad in ("http://en.wikipedia.org/wiki/Nile", "https://evil.example/wiki", "https://wikipedia.org.evil.example/x", "https://notwikipedia.org/x", "file:///etc/passwd", "javascript:alert(1)", ""):
        assert not wc.host_allowed(bad), bad


def test_robots_txt_rules_decide(monkeypatch):
    monkeypatch.setattr(stock, "_open", lambda url, headers=None, limit=0: ROBOTS.encode())
    assert wc.robots_allows("https://en.wikipedia.org/wiki/Nile")[0] is True
    ok, why = wc.robots_allows("https://en.wikipedia.org/private/x")
    assert ok is False and "disallowed" in why

    def missing(url, headers=None, limit=0):
        raise stock.StockError("provider answered HTTP 404")
    monkeypatch.setattr(stock, "_open", missing)
    assert wc.robots_allows("https://en.wikipedia.org/wiki/Nile") == (True, "no robots.txt")

    def broken(url, headers=None, limit=0):
        raise stock.StockError("provider answered HTTP 500")
    monkeypatch.setattr(stock, "_open", broken)
    ok, why = wc.robots_allows("https://en.wikipedia.org/wiki/Nile")
    assert ok is False and "could not be read" in why                                          # a robots.txt that cannot be read is not permission


def test_wikipedia_results_become_page_candidates_with_the_page_licence(monkeypatch):
    data = {"query": {"search": [{"title": "Mount Everest", "pageid": 9653, "snippet": "x"}, {"title": "No id"}, {"title": "Lhotse", "pageid": 7}]}}
    monkeypatch.setattr(stock, "_open", lambda url, headers=None, limit=0: json.dumps(data).encode())
    found = wc.search_pages("Mount Everest")
    assert [c.id for c in found] == ["wikipedia-page:9653", "wikipedia-page:7"]                # the malformed item is skipped
    c = found[0]
    assert c.media_type == "page" and c.source_page_url == "https://en.wikipedia.org/wiki/Mount_Everest" and c.download_url == c.source_page_url
    assert "CC BY-SA 4.0" in c.license_name and "own licences" in c.license_name and c.commercial_use_known is None and c.attribution_text.startswith("Mount Everest, Wikipedia contributors")


def test_a_real_browser_captures_only_the_infobox(site, tmp_path):
    dest = tmp_path / "out" / "box.png"
    try:
        cap = wc.capture(site + "/wiki/Mountain", dest, "infobox", **LOCAL)
    except wc.CaptureError as e:
        if "could not capture" in str(e):
            pytest.skip(f"no usable browser here: {e}")
        raise
    assert dest.is_file() and 480 <= cap["width"] <= 560 and cap["height"] < 400                      # the 520 px wide table, not the 1600 px page
    assert cap["title"] == "Test Mountain" and cap["selector"] == ".infobox" and cap["final_url"].endswith("/wiki/Mountain") and "8,849 m" in cap["text_excerpt"] and "article text" not in cap["text_excerpt"]
    assert len(cap["text_sha256"]) == 64 and cap["region"]["width"] > 400 and cap["captured_at"]
    top = wc.capture(site + "/wiki/Mountain", tmp_path / "top.png", "top", **LOCAL)
    assert top["width"] == wc.VIEWPORT[0] and top["selector"] is None


def test_a_capture_that_is_not_allowed_or_not_possible_says_why(site, tmp_path):
    with pytest.raises(wc.CaptureError, match="limited to https"):
        wc.capture(site + "/wiki/Mountain", tmp_path / "a.png")                                       # default allowlist: not this host
    with pytest.raises(wc.CaptureError, match="disallowed by robots.txt"):
        wc.capture(site + "/private/page", tmp_path / "b.png", **LOCAL)
    for path, text in (("/wiki/Gone", "HTTP 404"), ("/wiki/NoInfobox", "no 'infobox' section"), ("/wiki/Elsewhere", "not allowed")):
        with pytest.raises(wc.CaptureError, match=text):
            wc.capture(site + path, tmp_path / "c.png", **LOCAL)
    assert not (tmp_path / "a.png").exists() and not (tmp_path / "b.png").exists()
