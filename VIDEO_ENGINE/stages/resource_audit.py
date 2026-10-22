"""Resource discovery, audit and import (docs/resources.md). The ONLY module of the resource system that uses the network, and only when the user starts it.
Standard library only (like stock.py), https to api.github.com and raw.githubusercontent.com only, bounded sizes, nothing from GitHub is ever executed:
  discover  -> metadata of a few repositories (search API); a candidate is not a decision.
  audit     -> pins ref -> commit sha, reads the licence text, the package scripts and the selected files; computes the hard gates, a score and a decision.
  import    -> only an audit that passed every gate, only `selected_files` (SVG / font files) at the pinned commit; fetched to a temp folder, checked, moved in, then ONE registry write.
            A failed import puts back the previous registry and files. Import never installs a package and never runs a script (those are reported, not run).
The frontend sends a recipe name or a repository + file names; it never sends a command, a URL to download or a path to write."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import struct
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import config, resource_library as rl

UA = "audio-to-video/1.0 (resource audit)"
TIMEOUT = 20
MAX_FILE = 2 * 1024 * 1024                    # one file
MAX_IMPORT = 12 * 1024 * 1024                 # one import
MAX_FILES = 80
HOSTS = ("api.github.com", "raw.githubusercontent.com")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]{1,60}/[A-Za-z0-9_.-]{1,100}$")
REF_RE = re.compile(r"^[A-Za-z0-9_./-]{1,100}$")
INSTALL_SCRIPTS = ("preinstall", "install", "postinstall", "prepare", "prepublish", "prepack")
AUDITS = config.PROJECT_ROOT / "reports" / "RESOURCE_MANAGER" / "audits"
KNOWN = {                                    # the candidates the plan names, per category (a starting list, always re-audited)
    "icon": ["tabler/tabler-icons", "lucide-icons/lucide"], "font": ["google/fonts"], "chart": ["d3/d3", "apache/echarts"], "diagram": ["xyflow/xyflow"],
    "animated_icon": ["airbnb/lottie-web"], "3d_component": ["pmndrs/react-three-fiber"], "template": ["remotion-dev/remotion"]}
# recipes: what the backend itself knows how to import; the user picks a name, the backend owns repository, paths and licence file
RECIPES = {
    "tabler-icons": {"repository": "tabler/tabler-icons", "ref": "v3.49.0", "category": "icon", "path": "icons/outline/{name}.svg", "license_file": "LICENSE", "group": "tabler",
                     "display": "Tabler outline", "default_names": ["rocket", "satellite", "planet", "telescope", "antenna", "broadcast", "ufo", "meteor", "alien", "radar-2", "world", "map-pin", "compass",
                                                                       "route", "target", "flag", "bulb", "clock", "atom", "flask", "microscope", "chart-bar", "chart-line", "chart-pie", "building-community",
                                                                       "building-bank", "school", "books", "trophy", "award", "sun", "moon", "droplet", "flame", "bolt", "leaf", "mountain", "coin", "currency-rupee"]},
    "hind-guntur": {"repository": "google/fonts", "ref": "main", "category": "font", "dir": "ofl/hindguntur", "license_file": "ofl/hindguntur/OFL.txt", "metadata_file": "ofl/hindguntur/METADATA.pb",
                    "files": ["HindGuntur-Regular.ttf", "HindGuntur-Bold.ttf"], "family": "Hind Guntur", "group": "hind-guntur", "scripts": ["telugu", "latin"]},
}


class AuditError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _get(url: str, limit: int = MAX_FILE) -> bytes:
    """The only network call (tests replace it). https, an allow-listed host, a size cap; 403/429 on the API means the rate limit: said plainly, never hammered."""
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or u.hostname not in HOSTS:
        raise AuditError("host_not_allowed", f"{u.hostname or url} is not an allowed host")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"}), timeout=TIMEOUT) as r:
            data = r.read(limit + 1)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise AuditError("rate_limited", "GitHub refused the request (rate limit); try again later") from e
        raise AuditError("not_found" if e.code == 404 else "http_error", f"{u.hostname}{u.path[:80]}: HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise AuditError("network", f"{u.hostname}: {e}") from e
    if len(data) > limit:
        raise AuditError("too_large", f"{u.path[-60:]} is larger than {limit // 1024} KB")
    return data


def _api(path: str) -> dict | list:
    return json.loads(_get("https://api.github.com" + path, 4 * 1024 * 1024))


def _raw(repo: str, sha: str, path: str, limit: int = MAX_FILE) -> bytes:
    return _get(f"https://raw.githubusercontent.com/{repo}/{sha}/{urllib.parse.quote(path)}", limit)


def _check_repo(repo: str, ref: str) -> None:
    if not REPO_RE.match(repo or "") or not REF_RE.match(ref or "") or ".." in ref:
        raise AuditError("invalid_request", "repository must be owner/name and ref a tag, branch or commit")


# ---------------------------------------------------------------- discover
def discover(category: str, query: str = "", limit: int = 5) -> dict:
    """Metadata of a few repositories: the plan's known candidates for the category plus one bounded search. Nothing is downloaded or executed."""
    if category not in rl.CATEGORIES:
        raise AuditError("invalid_request", f"unknown category {category!r}")
    limit = max(1, min(int(limit), 5))
    names = list(KNOWN.get(category, []))
    found: list[str] = []
    err = None
    if query.strip():
        q = urllib.parse.quote(f"{query.strip()[:80]} in:name,description,topics")
        try:
            found = [r["full_name"] for r in _api(f"/search/repositories?q={q}&sort=stars&per_page={limit}")["items"]]
        except AuditError as e:
            err = e.message
    out = []
    for full in list(dict.fromkeys(names + found)):
        try:
            r = _api(f"/repos/{full}")
            out.append({"repository": full, "url": r["html_url"], "description": (r.get("description") or "")[:160], "license": (r.get("license") or {}).get("spdx_id"), "stars": r["stargazers_count"],
                        "pushed_at": r["pushed_at"], "archived": r["archived"], "size_kb": r["size"], "known_candidate": full in names})
        except AuditError as e:
            out.append({"repository": full, "error": e.message})
    return {"category": category, "query": query, "at": rl.now(), "candidates": out, "search_error": err}


# ---------------------------------------------------------------- licence detection (text heuristics; the verdict is only as good as the text)
def detect_license(text: str) -> str | None:
    t = re.sub(r"\s+", " ", text)
    if re.search(r"GNU (AFFERO )?GENERAL PUBLIC LICENSE|GNU LESSER", t, re.I):
        return "GPL-family"
    if "SIL OPEN FONT LICENSE Version 1.1" in t:
        return "OFL-1.1"
    if "Apache License" in t and "Version 2.0" in t:
        return "Apache-2.0"
    if "Permission is hereby granted, free of charge" in t and "THE SOFTWARE IS PROVIDED" in t:
        return "MIT"
    if "Permission to use, copy, modify, and/or distribute this software for any purpose" in t:
        return "ISC"
    if "Redistribution and use in source and binary forms" in t:
        return "BSD-3-Clause" if "Neither the name" in t else "BSD-2-Clause"
    return None


# ---------------------------------------------------------------- font facts (a tiny TrueType reader: cmap and GSUB script tags)
def _tables(b: bytes) -> dict[str, tuple[int, int]]:
    if b[:4] not in (b"\x00\x01\x00\x00", b"true", b"OTTO"):
        raise AuditError("font_invalid", "not a TrueType/OpenType file (a .woff or an HTML page?)")
    n = struct.unpack(">H", b[4:6])[0]
    return {b[12 + i * 16:16 + i * 16].decode("latin1"): struct.unpack(">II", b[20 + i * 16:28 + i * 16]) for i in range(n)}


def font_facts(b: bytes) -> dict:
    """Code points in the font's cmap (formats 4 and 12) and the script tags its GSUB shapes (telu / tel2 = Telugu shaping rules)."""
    tb = _tables(b)
    cps: set[int] = set()
    off = tb["cmap"][0]
    for i in range(struct.unpack(">H", b[off + 2:off + 4])[0]):
        pid, eid, so = struct.unpack(">HHI", b[off + 4 + i * 8:off + 12 + i * 8])
        if (pid, eid) not in ((3, 1), (3, 10), (0, 3), (0, 4)):
            continue
        s = off + so
        fmt = struct.unpack(">H", b[s:s + 2])[0]
        if fmt == 4:
            segx2 = struct.unpack(">H", b[s + 6:s + 8])[0]
            seg = segx2 // 2
            ends = struct.unpack(f">{seg}H", b[s + 14:s + 14 + segx2])
            starts = struct.unpack(f">{seg}H", b[s + 16 + segx2:s + 16 + 2 * segx2])
            for a, z in zip(starts, ends):
                cps.update(range(a, z + 1) if z != 0xFFFF else range(a, z))
        elif fmt == 12:
            ng = struct.unpack(">I", b[s + 12:s + 16])[0]
            for g in range(ng):
                a, z, _ = struct.unpack(">III", b[s + 16 + g * 12:s + 28 + g * 12])
                cps.update(range(a, z + 1))
    scripts: list[str] = []
    if "GSUB" in tb:
        g = tb["GSUB"][0]
        sl = g + struct.unpack(">H", b[g + 4:g + 6])[0]
        for i in range(struct.unpack(">H", b[sl:sl + 2])[0]):
            scripts.append(b[sl + 2 + i * 6:sl + 6 + i * 6].decode("latin1"))
    name = ""
    if "name" in tb:
        o = tb["name"][0]
        cnt, so = struct.unpack(">HH", b[o + 2:o + 6])
        for i in range(cnt):
            pid, eid, lid, nid, ln, ofs = struct.unpack(">6H", b[o + 6 + i * 12:o + 18 + i * 12])
            if nid == 4 and pid == 3:
                name = b[o + so + ofs:o + so + ofs + ln].decode("utf-16-be", "replace")
                break
    return {"codepoints": cps, "gsub_scripts": scripts, "full_name": name}


TELUGU_REQUIRED = [*range(0x0C01, 0x0C04), *range(0x0C05, 0x0C0D), *range(0x0C0E, 0x0C11), *range(0x0C12, 0x0C29), *range(0x0C2A, 0x0C3A), *range(0x0C3E, 0x0C45), *range(0x0C46, 0x0C49),
                   *range(0x0C4A, 0x0C4E)]                                  # letters, vowel signs, virama: what every Telugu word needs
TELUGU_OPTIONAL = list(range(0x0C66, 0x0C70))                               # native Telugu digits: modern Telugu text and this project use ASCII digits; a gap is DISCLOSED (not hidden) and the font stack's next font draws them
LATIN_REQUIRED = [*range(0x20, 0x7F), 0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2026]


def font_coverage(b: bytes) -> dict:
    f = font_facts(b)
    return {"telugu_missing": [f"U+{c:04X}" for c in TELUGU_REQUIRED if c not in f["codepoints"]], "latin_missing": [f"U+{c:04X}" for c in LATIN_REQUIRED if c not in f["codepoints"]],
            "telugu_optional_missing": [f"U+{c:04X}" for c in TELUGU_OPTIONAL if c not in f["codepoints"]],
            "telugu_shaping": any(s in f["gsub_scripts"] for s in ("tel2", "telu")), "glyphs_checked": len(TELUGU_REQUIRED) + len(LATIN_REQUIRED), "full_name": f["full_name"]}


# ---------------------------------------------------------------- audit
def _score(a: dict, fit: bool) -> float:
    """The plan's weights: compatibility 25, licence 20, fit 15, deterministic 10, footprint 10, maintenance 10, docs 5, searchability 5 (each part 0-100)."""
    age = a["metadata"].get("age_days")
    d = a["license"]["detected"]
    parts = {"compat": (100 if a["gates"]["selected_files_only"] else 50, 25), "license": (100 if d in ("MIT", "ISC", "BSD-3-Clause", "BSD-2-Clause", "Apache-2.0") else 90 if d == "OFL-1.1" else 0, 20),
             "fit": (100 if fit else 0, 15), "deterministic": (100, 10), "footprint": (max(0, 100 - a["selected_bytes"] // 20_000), 10),
             "maintenance": (0 if age is None else 100 if age < 365 else 60 if age < 730 else 20, 10), "docs": (100, 5), "search": (100 if a["files_with_tags"] else 30, 5)}
    return round(sum(v * w for v, w in parts.values()) / 100, 1)


def audit(spec: dict, progress=None) -> dict:
    """Static audit of a pinned ref (never executes anything). spec = {recipe, names?} or {repository, ref, category, files, license_file?}. Written to reports/RESOURCE_MANAGER/audits/."""
    say = progress or (lambda m: None)
    rec = RECIPES.get(spec.get("recipe")) if spec.get("recipe") else None
    if spec.get("recipe") and not rec:
        raise AuditError("invalid_request", f"unknown recipe {spec.get('recipe')!r}")
    repo, ref = (rec["repository"], rec["ref"]) if rec else (spec.get("repository", ""), spec.get("ref") or "")
    category = rec["category"] if rec else spec.get("category", "")
    _check_repo(repo, ref or "HEAD")
    if category not in ("icon", "font"):
        raise AuditError("unsupported_category", "only icon and font files can be imported as selected files; other categories are audited by hand (see the discovery report)")
    say(f"{repo}: repository metadata")
    meta = _api(f"/repos/{repo}")
    ref = ref or meta["default_branch"]
    say(f"{repo}: pinning {ref} to a commit")
    sha = _api(f"/repos/{repo}/commits/{urllib.parse.quote(ref, safe='')}")["sha"]
    pushed = meta.get("pushed_at")
    age = int((time.time() - time.mktime(time.strptime(pushed, "%Y-%m-%dT%H:%M:%SZ"))) / 86400) if pushed else None

    if rec and category == "icon":
        names = spec.get("names") or rec["default_names"]
        if any(not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,60}", n) for n in names):
            raise AuditError("invalid_request", "icon names are lower-case letters, digits and dashes")
        files = [rec["path"].format(name=n) for n in names]
    elif rec:
        files = [f"{rec['dir']}/{n}" for n in rec["files"]]
    else:
        files = list(spec.get("files") or [])
    if not files or len(files) > MAX_FILES:
        raise AuditError("invalid_request", f"select between 1 and {MAX_FILES} files")
    ext = (".svg",) if category == "icon" else (".ttf", ".otf")
    for f in files:
        try:
            rl.safe_rel(f)
        except ValueError as e:
            raise AuditError("unsafe_path", str(e)) from e
        if not f.lower().endswith(ext):
            raise AuditError("file_type", f"{f}: only {', '.join(ext)} files are accepted for {category}")

    lic_path = rec["license_file"] if rec else spec.get("license_file") or "LICENSE"
    rl.safe_rel(lic_path)
    say(f"{repo}: licence text ({lic_path})")
    lic_text, lic_err = "", None
    try:
        lic_text = _raw(repo, sha, lic_path, 200_000).decode("utf-8", "replace")
    except AuditError as e:
        lic_err = e.message
    detected = detect_license(lic_text) if lic_text else None
    api_spdx = (meta.get("license") or {}).get("spdx_id")
    reserved = bool(re.search(r"Reserved Font Name", lic_text.split("PREAMBLE")[0]))

    scripts: dict = {"install_time": [], "all": []}                              # reported, never executed: selected files are copied, no package is installed
    try:
        pkg = json.loads(_raw(repo, sha, "package.json", 400_000))
        scripts = {"all": sorted((pkg.get("scripts") or {}).keys()), "install_time": [s for s in INSTALL_SCRIPTS if s in (pkg.get("scripts") or {})], "package_license": pkg.get("license")}
    except (AuditError, json.JSONDecodeError):
        scripts["package_json"] = "none or unreadable"

    rows, total, with_tags, problems, coverage = [], 0, 0, [], None
    want_scripts = (rec or {}).get("scripts", [])
    for i, f in enumerate(files):
        say(f"{repo}: file {i + 1}/{len(files)} {Path(f).name}")
        try:
            b = _raw(repo, sha, f)
        except AuditError as e:
            problems.append(f"{f}: {e.message}")
            rows.append({"path": f, "ok": False, "error": e.message})
            continue
        total += len(b)
        row = {"path": f, "size": len(b), "sha256": hashlib.sha256(b).hexdigest(), "ok": True}
        try:
            if category == "icon":
                svg = rl.parse_svg(b.decode("utf-8"))
                row["tags"] = svg["tags"]
                with_tags += bool(svg["tags"])
            else:
                cov = coverage = font_coverage(b)
                row["coverage"] = {k: cov[k] for k in ("telugu_missing", "latin_missing", "telugu_optional_missing", "telugu_shaping")}
                for why, bad in (("Telugu glyphs", "telugu" in want_scripts and cov["telugu_missing"]), ("Latin glyphs", "latin" in want_scripts and cov["latin_missing"]),
                                 ("Telugu shaping rules (GSUB telu/tel2): conjuncts would not form", "telugu" in want_scripts and not cov["telugu_shaping"])):
                    if bad:
                        problems.append(f"{f}: missing {why}" + (f" {bad[:6]}" if isinstance(bad, list) else ""))
                        row["ok"] = False
        except (rl.ResourceError, AuditError, UnicodeDecodeError, struct.error, KeyError) as e:
            problems.append(f"{f}: {getattr(e, 'message', e)}")
            row["ok"], row["error"] = False, str(getattr(e, "message", e))[:160]
        rows.append(row)
    if total > MAX_IMPORT:
        problems.append(f"the selected files are {total // 1024} KB: more than the {MAX_IMPORT // 1024} KB limit")

    gates = {"license_known_and_allowed": detected in rl.ALLOWED_LICENSES, "license_text_kept": bool(lic_text), "license_matches_api_or_font_metadata": category == "font" or api_spdx in (detected, None, "NOASSERTION"),
             "ref_pinned_to_commit": bool(re.fullmatch(r"[0-9a-f]{40}", sha)), "not_archived": not meta.get("archived", False), "selected_files_only": True,
             "no_install_script_executed": True, "files_safe_and_valid": not problems and all(r["ok"] for r in rows), "within_size_limits": total <= MAX_IMPORT}
    out = {"audit_id": time.strftime("%Y%m%d-%H%M%S") + "-" + hashlib.sha1(f"{repo}{sha}{category}{files}".encode()).hexdigest()[:6], "created_at": rl.now(), "recipe": spec.get("recipe"), "repository": repo, "ref": ref,
           "commit_sha": sha, "category": category, "url": meta["html_url"], "files": rows, "selected_bytes": total, "files_with_tags": with_tags, "problems": problems,
           "metadata": {"stars": meta["stargazers_count"], "pushed_at": pushed, "age_days": age, "archived": meta["archived"], "size_kb": meta["size"], "language": meta.get("language"), "default_branch": meta["default_branch"]},
           "license": {"api_spdx": api_spdx, "detected": detected, "file": lic_path, "file_found": bool(lic_text), "error": lic_err, "reserved_font_name": reserved, "text_sha256": hashlib.sha256(lic_text.encode()).hexdigest() if lic_text else None},
           "scripts": scripts, "font_coverage": coverage, "gates": gates,
           "limitations": ([f"native Telugu digits {coverage['telugu_optional_missing'][0]}-{coverage['telugu_optional_missing'][-1]} are not in this font ({len(coverage['telugu_optional_missing'])} missing): ASCII digits are used in this project, and the font stack falls back to Noto Sans Telugu"]
                           if coverage and coverage["telugu_optional_missing"] else []),
           "notes": ["Bundled demo or sample assets elsewhere in the repository are NOT covered by this audit: only the selected files and the licence text above were read.",
                     "The licence verdict is a text check of the licence file, not legal advice."]}
    out["score"] = _score(out, fit=bool(rec or spec.get("fit")))
    ok = all(gates.values())
    out["decision"] = "import" if ok else "skip"
    out["rationale"] = (f"every hard gate passed; score {out['score']}" if ok else "skipped: " + ", ".join(k for k, v in gates.items() if not v) + ("; " + "; ".join(problems[:3]) if problems else ""))
    AUDITS.mkdir(parents=True, exist_ok=True)
    rl.atomic_write(AUDITS / f"{out['audit_id']}.json", json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    return out


def load_audit(audit_id: str) -> dict:
    if not re.fullmatch(r"[0-9]{8}-[0-9]{6}-[0-9a-f]{6}", audit_id or ""):
        raise AuditError("invalid_request", "bad audit id")
    p = AUDITS / f"{audit_id}.json"
    if not p.is_file():
        raise AuditError("audit_missing", f"no audit {audit_id}")
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- import
def import_audit(audit_id: str, progress=None) -> dict:
    """Import what an audit selected (only an audit with decision `import`): fetch at the pinned commit -> temp -> move in -> ONE registry write -> bundle. All or nothing."""
    say = progress or (lambda m: None)
    a = load_audit(audit_id)
    if a["decision"] != "import" or not all(a["gates"].values()):
        raise AuditError("gates_failed", "this audit did not pass every hard gate: " + a["rationale"])
    repo, sha, category = a["repository"], a["commit_sha"], a["category"]
    rec = RECIPES.get(a.get("recipe") or "", {})
    group = rec.get("group") or re.sub(r"[^a-z0-9-]", "-", repo.split("/")[-1].lower())
    base = config.PROJECT_ROOT
    tmp = Path(tempfile.mkdtemp(prefix="a2v_res_"))
    before: dict[Path, bytes | None] = {}                                       # every file this import writes, with what it held before (None = did not exist)
    prev_registry = rl.REGISTRY.read_text(encoding="utf-8") if rl.REGISTRY.exists() else None
    prev_bundle = rl.BUNDLE.read_text(encoding="utf-8") if rl.BUNDLE.exists() else None
    try:
        lic = _raw(repo, sha, a["license"]["file"], 200_000)
        if hashlib.sha256(lic.decode("utf-8", "replace").encode()).hexdigest() != a["license"]["text_sha256"]:
            raise AuditError("changed_since_audit", "the licence text differs from the audited one")
        lic_rel = f"resource-library/licenses/{group}/{Path(a['license']['file']).name}"
        staged: list[tuple[bytes, str]] = [(lic, lic_rel)]
        meta_rel = None
        if rec.get("metadata_file"):
            meta_rel = f"resource-library/licenses/{group}/{Path(rec['metadata_file']).name}"
            staged.append((_raw(repo, sha, rec["metadata_file"], 100_000), meta_rel))
        sub = "icons" if category == "icon" else "fonts"
        asset_rels: list[tuple[dict, str]] = []
        for i, row in enumerate(a["files"]):
            say(f"fetching {i + 1}/{len(a['files'])} {Path(row['path']).name}")
            b = _raw(repo, sha, row["path"])
            if hashlib.sha256(b).hexdigest() != row["sha256"]:
                raise AuditError("changed_since_audit", f"{row['path']} differs from the audited file")
            rel = f"resource-library/assets/{sub}/{group}/{Path(row['path']).name}"
            staged.append((b, rel))
            asset_rels.append((row, rel))
        for i, (b, rel) in enumerate(staged):                                   # through the temp folder first: a write error here changes nothing in the project
            (tmp / f"s{i}").write_bytes(b)
        say("moving the files in")
        for i, (b, rel) in enumerate(staged):
            dst = base / rl.safe_rel(rel)
            before.setdefault(dst, dst.read_bytes() if dst.exists() else None)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(tmp / f"s{i}", dst)
        entries: list[rl.Entry] = []
        if category == "icon":
            for row, rel in asset_rels:
                svg = rl.parse_svg((base / rel).read_text(encoding="utf-8"))
                entries.append(_icon_entry(a, rec, group, Path(rel).stem, rel, row["sha256"], svg["tags"], lic_rel))
        else:
            files = [{"file": rel, "sha256": row["sha256"], "weight": 700 if "Bold" in rel else 400} for row, rel in asset_rels]
            entries.append(_font_entry(a, rec, group, files, lic_rel, meta_rel))
        say("writing the registry")
        rl.upsert(entries)
        bundle = rl.build_bundle()
        fonts = rl.stage_fonts()
        return {"audit_id": audit_id, "imported": [e.resource_id for e in entries], "status": "imported", "bundle_resources": len(bundle["resources"]), "staged_fonts": fonts,
                "note": "imported, NOT verified: run Verify to render them"}
    except BaseException:
        for dst, old in before.items():                                         # put back what was there; remove what this import created
            if old is None:
                dst.unlink(missing_ok=True)
            else:
                dst.write_bytes(old)
        if prev_registry is not None:
            rl.atomic_write(rl.REGISTRY, prev_registry)
        else:
            rl.REGISTRY.unlink(missing_ok=True)
        if prev_bundle is not None:
            rl.atomic_write(rl.BUNDLE, prev_bundle)
        else:
            rl.BUNDLE.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _common(a: dict, lic_rel: str, note: str) -> dict:
    spdx = a["license"]["detected"]
    return {"source": rl.Source(kind="selected_file", url=a["url"], repository=a["repository"], ref=a["ref"], commit_sha=a["commit_sha"], release=a["ref"] if re.match(r"^v?\d", a["ref"]) else None, audit_date=a["created_at"][:10]),
            "license": rl.License(spdx_id=spdx, verified=True, license_url=f"{a['url']}/blob/{a['commit_sha']}/{a['license']['file']}", notices_path=lic_rel, asset_license_notes=note,
                                  obligations=["keep the copyright and licence notice with the files", *(["the font files are not modified; do not sell them on their own"] if spdx == "OFL-1.1" else [])]),
            "decision": rl.Decision(score=a["score"], decision="import", rationale=a["rationale"], alternatives_considered=[x for x in KNOWN.get(a["category"], []) if x != a["repository"]], hard_gate_results=a["gates"])}


def _icon_entry(a, rec, group, name, rel, upstream_sha, tags, lic_rel) -> rl.Entry:
    return rl.Entry(resource_id=f"icon.{group}.{name}", display_name=f"{rec.get('display', group)} · {name}", category="icon", tags=sorted({name, *tags}), status="imported",
                    integrity=rl.Integrity(sha256=rl.combined_sha([rel]), pinned=True, source_files=[rel]), compatibility=rl.Compatibility(react=True, remotion=True, node=True, aspect_ratios=["16:9", "9:16"]),
                    adapter=rl.Adapter(adapter_id="svg-icon", entrypoint="VIDEO_ENGINE/remotion/src/components/IconPop.tsx", props_schema_ref="icon-props-v1", animation_presets=["pop", "fade", "slide-up"], bounds_supported=True),
                    usage=rl.Usage(import_mode="selected_files", offline_required=True, used_by_pipeline_stages=["motion_planning", "motion_generation", "validation", "timeline", "approval", "render", "qc"]),
                    data={"upstream_file_sha256": upstream_sha, "group": group, "style": "outline"},
                    **_common(a, lic_rel, "Only this SVG file was imported; the repository's other material is not covered."))


def _font_entry(a, rec, group, files, lic_rel, meta_rel) -> rl.Entry:
    rels = [f["file"] for f in files] + ([meta_rel] if meta_rel else [])
    cov = a.get("font_coverage") or {}
    return rl.Entry(resource_id=f"font.{group}", display_name=f"{rec.get('family', group)} (Telugu + Latin)", category="font", tags=["telugu", "latin", "sans-serif", "ofl"], status="imported",
                    integrity=rl.Integrity(sha256=rl.combined_sha(rels), pinned=True, source_files=rels), compatibility=rl.Compatibility(react=True, remotion=True, node=True, aspect_ratios=["16:9", "9:16"]),
                    adapter=rl.Adapter(adapter_id="font-face", entrypoint="VIDEO_ENGINE/remotion/src/library/resources.ts", props_schema_ref="font-id-v1", animation_presets=[], bounds_supported=False),
                    usage=rl.Usage(import_mode="selected_files", offline_required=True, used_by_pipeline_stages=["motion_generation", "validation", "render", "qc"]),
                    data={"family": rec.get("family", group), "scripts": rec.get("scripts", []), "files": [{"weight": f["weight"], "style": "normal", "file": f["file"], "sha256": f["sha256"]} for f in files],
                          "coverage": {k: cov.get(k) for k in ("telugu_missing", "latin_missing", "telugu_optional_missing", "telugu_shaping")}, "limitations": a.get("limitations", [])},
                    **_common(a, lic_rel, "OFL-1.1 for the family (OFL.txt kept next to the files); the font files were not modified."))
