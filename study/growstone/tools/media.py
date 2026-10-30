#!/usr/bin/env python3
"""Download GrowStone screens and clips from sources that allow it, and build a gallery.

  store    Official store screenshots at full size: Google Play in every locale
           play_store.py saved (missing ones are fetched), and the App Store in
           16 countries through Apple's documented iTunes Search API (lookup),
           iPhone and iPad. App Store text goes to corpus/appstore/ for the index.
  history  Play listings the Wayback Machine archived since 2018, one per
           month: their screenshots (Google's live copy, else the archive's)
           and their text (description, what's new) as Markdown. This shows how
           the game's screens and pitch changed over the years.
  linked   Images and clips linked from Reddit posts and comments: i.redd.it,
           preview.redd.it, imgur (gifv as mp4; albums: the cover only, or every
           image with a free IMGUR_CLIENT_ID) and Reddit-hosted video (v.redd.it;
           video and audio tracks come as separate files).
  thumbs   YouTube thumbnails, from the oEmbed index built by youtube_index.py.
  gallery  Only rebuild corpus/media/gallery.html (every command above ends
           with this): all of the above plus wiki images, Reddit post images and
           your own captures (capture.py), grouped and captioned.
  all      store, history, linked and thumbs.

Every host is checked against robots.txt and paced. Not done, on purpose:
YouTube video files (YouTube's terms forbid downloading), App Store web pages
(Apple's site terms forbid page scraping, so only the lookup API is used),
TapTap (its robots.txt bars AI agents) and anything inside the game's APK.

Examples:
  python3 media.py all
  python3 media.py store --max-px 1600   # smaller files (longest side); default 0 = original
  python3 media.py linked --refresh      # retry links that failed before
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path

import requests

from common import DEFAULT_OUT, PoliteSession, Robots, front_matter, html_to_text, log, read_json, write_json, write_text
from play_store import APP_ID, DEFAULT_LOCALES

APPSTORE_ID = 1238025108
APPSTORE_COUNTRIES = ["kr", "us", "tw", "hk", "jp", "th", "vn", "id", "br", "es", "de", "fr", "ru", "tr", "it", "pl"]
WAYBACK = "https://web.archive.org"
EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif",
       "video/mp4": "mp4", "video/webm": "webm", "audio/mp4": "m4a"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXT = {".mp4", ".webm", ".mov", ".mkv"}
SECTIONS = {"own": "Your captures", "play": "Google Play, current listing", "appstore": "App Store, current listing",
            "history": "Google Play over time (Wayback Machine)", "reddit": "Reddit", "wiki": "Wiki images",
            "youtube": "YouTube thumbnails"}

IMG_TAG = re.compile(r"<img\b[^>]*>", re.I)
PLAY_IMG = re.compile(r"https://((?:play-lh|lh\d)\.googleusercontent\.com)/([\w-]+)")
MEDIA_LINK = re.compile(
    r"https?://(?:i\.redd\.it/[\w-]+\.\w{3,4}"
    r"|preview\.redd\.it/[\w-]+\.\w{3,4}(?:\?[^\s)\]\"'<>]*)?"
    r"|(?:i\.|m\.|www\.)?imgur\.com/(?:a/|gallery/)?[A-Za-z0-9]{5,8}(?:\.\w{3,4})?\b"
    r"|v\.redd\.it/\w+)", re.I)
IMGUR_RESERVED = {"gallery", "upload", "account", "signin", "search", "topic", "user"}


class Store:
    """Downloads into corpus/media/ and keeps index.json, one entry per (group, file)."""

    def __init__(self, out: Path, max_px: int = 0):
        self.out = out
        self.max_px = max_px
        self.s = PoliteSession(min_interval=1.0, timeout=90)     # image CDNs
        self.slow = PoliteSession(min_interval=4.0, timeout=90)  # store pages, Apple's API, the Wayback Machine
        self.robots = Robots(self.s)
        self.index: dict[str, dict] = read_json(out / "index.json", {}) or {}

    def fetch(self, url: str, stem: str, session: PoliteSession | None = None) -> str | None:
        """Save url as <stem>.<ext> unless it is already there; return the path relative to out."""
        target = self.out / stem
        existing = sorted(p for p in target.parent.glob(target.name + ".*") if not p.name.endswith(".tmp"))
        if existing:
            return existing[0].relative_to(self.out).as_posix()
        if not self.robots.allowed(url):
            log(f"  robots.txt disallows {url}")
            return None
        try:
            r = (session or self.s).get(url)
        except requests.RequestException as e:
            log(f"  failed ({e.__class__.__name__}): {url}")
            return None
        ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
        if r.url.endswith("/removed.png"):
            log(f"  deleted from imgur: {url}")
            return None
        if r.status_code != 200 or ctype not in EXT:
            log(f"  unavailable (HTTP {r.status_code}, {ctype or 'no type'}): {url}")
            return None
        path = self.out / f"{stem}.{EXT[ctype]}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
        return path.relative_to(self.out).as_posix()

    def add(self, section: str, group: str, file: str, order: int = 0, **meta) -> None:
        self.index[f"{group}|{file}"] = {"section": section, "group": group, "file": file, "order": order, **meta}

    def save(self) -> None:
        write_json(self.out / "index.json", self.index)


def utc_date(ts) -> str:
    return dt.datetime.fromtimestamp(float(ts or 0), dt.timezone.utc).date().isoformat()


# --- Store listings ---------------------------------------------------------

def play_screenshots(page: str) -> list[tuple[str, str]]:
    """(host, image id) of each screenshot in page order, for every Play layout since 2018.

    Current pages mark screenshots with data-screenshot-index. Older ones only
    give them itemprop="image", like the app icon, but the icon is square
    (=s180) and screenshots are not (=w720-h310)."""
    tags = IMG_TAG.findall(page)
    shots = [t for t in tags if "data-screenshot-index" in t]
    if not shots:
        shots = [t for t in tags if 'itemprop="image"' in t and re.search(r"=w\d+-h\d+", t)]
    out: list[tuple[str, str]] = []
    for t in shots:
        m = PLAY_IMG.search(t)
        if m and m.groups() not in out:  # carousels repeat their first slides
            out.append(m.groups())
    return out


def play_image(st: Store, host: str, img: str) -> str | None:
    return st.fetch(f"https://{host}/{img}=s{st.max_px}", f"play/{img[:24]}")  # =s0 is the original upload


def collect_play(st: Store, corpus: Path, fresh: bool) -> None:
    saved = {f.stem.split("_", 1)[1]: f for f in sorted((corpus / "play" / "html").glob("*_*.html"))}  # latest wins
    for loc in DEFAULT_LOCALES:
        hl, _, gl = loc.partition("-")
        link = f"https://play.google.com/store/apps/details?id={APP_ID}&hl={hl}&gl={gl}"
        if loc in saved and not fresh:
            page, date = saved[loc].read_text(encoding="utf-8"), saved[loc].stem.split("_")[0]
        else:
            if not st.robots.allowed(link):
                log(f"robots.txt disallows {link}")
                continue
            r = st.slow.get(link)
            if r.status_code != 200:
                log(f"Play {loc}: HTTP {r.status_code}")
                continue
            page, date = r.text, dt.date.today().isoformat()
        shots = play_screenshots(page)
        for n, (host, img) in enumerate(shots):
            if file := play_image(st, host, img):
                st.add("play", f"Google Play · {loc}", file, n, date=date, link=link)
        log(f"Play {loc}: {len(shots)} screenshots")
    st.save()


def appstore_full(url: str, max_px: int) -> str:
    """mzstatic URLs end in a size such as /392x696bb.jpg; asking for 9999 returns the original."""
    n = max_px or 9999
    return re.sub(r"/[^/]+$", f"/{n}x{n}bb.jpg", url)


def collect_appstore(st: Store, corpus: Path) -> None:
    today = dt.date.today().isoformat()
    for c in APPSTORE_COUNTRIES:
        url = f"https://itunes.apple.com/lookup?id={APPSTORE_ID}&country={c}"
        if not st.robots.allowed(url):
            log(f"robots.txt disallows {url}")
            continue
        r = st.slow.get(url)
        try:
            app = (r.json().get("results") or [None])[0] if r.ok else None
        except json.JSONDecodeError:
            app = None
        if not app:
            log(f"App Store {c}: not listed (HTTP {r.status_code})")
            continue
        write_json(corpus / "appstore" / f"{today}_{c}.json", app)
        md = [front_matter({"source": "appstore", "title": f"{app.get('trackName')} (App Store {c.upper()})",
                            "url": app.get("trackViewUrl"), "published": today, "locale": c}),
              f"# {app.get('trackName')}, App Store {c.upper()}, {today}", "",
              f"Version {app.get('version')} ({(app.get('currentVersionReleaseDate') or '')[:10]}) · first released "
              f"{(app.get('releaseDate') or '')[:10]} · rating {app.get('averageUserRating')} from "
              f"{app.get('userRatingCount')} ratings · {app.get('formattedPrice')} · {app.get('contentAdvisoryRating')}", "",
              "## What's new", "", app.get("releaseNotes") or "(none)", "",
              "## Description", "", app.get("description") or ""]
        write_text(corpus / "appstore" / f"{today}_{c}.md", "\n".join(md) + "\n")
        counts = []
        for device, key in (("iPhone", "screenshotUrls"), ("iPad", "ipadScreenshotUrls")):
            urls = app.get(key) or []
            for n, u in enumerate(urls):
                stem = "appstore/" + hashlib.sha1(u.rsplit("/", 1)[0].encode()).hexdigest()[:16]
                if file := st.fetch(appstore_full(u, st.max_px), stem):
                    st.add("appstore", f"App Store · {device} · {c.upper()}", file, n, date=today,
                           link=app.get("trackViewUrl"), caption=app.get("trackName"))
            counts.append(f"{len(urls)} {device}")
        log(f"App Store {c}: {app.get('trackName')}: {', '.join(counts)} screenshots")
        st.save()


def collect_history(st: Store, corpus: Path, refresh: bool) -> None:
    done = read_json(st.out / "history.json", {}) or {}
    r = st.slow.get(f"{WAYBACK}/cdx/search/cdx", params={
        "url": f"play.google.com/store/apps/details?id={APP_ID}", "matchType": "prefix", "output": "json",
        "filter": ["statuscode:200", "mimetype:text/html"], "collapse": "timestamp:6", "fl": "timestamp,original"})
    try:
        rows = r.json()[1:] if r.ok and r.text.strip() else []
    except json.JSONDecodeError:
        rows = []
    # matchType=prefix also matches longer package names; keep this app only.
    rows = [(ts, orig) for ts, orig in rows
            if urllib.parse.parse_qs(urllib.parse.urlsplit(orig).query).get("id") == [APP_ID]]
    log(f"Wayback Machine: {len(rows)} monthly snapshots of the Play listing")
    for ts, orig in rows:
        if ts in done and not refresh:
            continue
        r = st.slow.get(f"{WAYBACK}/web/{ts}id_/{orig}")  # id_ = the page as captured, no archive toolbar
        if r.status_code != 200:
            log(f"  {ts}: HTTP {r.status_code}")
            continue
        page = r.text
        lang = (re.search(r'<html[^>]*\blang="([^"]+)"', page) or [None, "unknown"])[1]
        date = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
        archived = f"{WAYBACK}/web/{ts}/{orig}"
        _, text = html_to_text(page, keep={"header"})
        write_text(corpus / "play" / "history" / f"{ts[:8]}_{lang}.md",
                   front_matter({"source": "play", "title": f"Google Play listing, archived {date} ({lang})",
                                 "url": archived, "published": date, "locale": lang})
                   + f"# Google Play listing as archived on {date} ({lang})\n\n{text}\n")
        shots = play_screenshots(page)
        for n, (host, img) in enumerate(shots):
            file = play_image(st, host, img)
            if not file:  # Google dropped the original; the archive may hold the size the page showed
                src = re.search(rf"https://{re.escape(host)}/{re.escape(img)}[^\"'\s]*", page)
                if src:
                    file = st.fetch(f"{WAYBACK}/web/{ts}im_/{src.group(0)}", f"play/{img[:24]}", st.slow)
            if file:
                st.add("history", f"Play listing · {date[:7]} · {lang}", file, n, date=date, link=archived)
        done[ts] = {"lang": lang, "screenshots": len(shots)}
        write_json(st.out / "history.json", done)
        st.save()
        log(f"  {date} ({lang}): {len(shots)} screenshots")


# --- Links in the Reddit corpus ----------------------------------------------

def reddit_links(post: dict) -> list[tuple[str, str]]:
    """(where, url) for each media link in a saved thread: the post's own link, its text, its comments."""
    texts = [("post", post.get("url") or ""), ("post", post.get("selftext") or "")]
    texts += [(f"comment by u/{c.get('author')}", c.get("body") or "") for c in post.get("comments") or []]
    found: list[tuple[str, str]] = []
    for where, text in texts:
        for m in MEDIA_LINK.finditer(html.unescape(text)):
            url = m.group(0)
            if all(url != u for _, u in found):
                found.append((where, url))
    return found


def plan_link(url: str) -> tuple[str, str] | None:
    """(kind, target) for a media link: image or video (target = file URL), album (imgur id), vreddit (base URL)."""
    parts = urllib.parse.urlsplit(url)
    host, path = parts.netloc.lower(), parts.path
    if host == "v.redd.it":
        return "vreddit", f"https://v.redd.it{path.rstrip('/')}"
    if host in ("i.redd.it", "preview.redd.it"):
        return "image", url
    m = re.fullmatch(r"/(a/|gallery/)?([A-Za-z0-9]{5,8})(\.\w{3,4})?", path)
    if not host.endswith("imgur.com") or not m or m.group(2).lower() in IMGUR_RESERVED:
        return None
    if m.group(1):
        return "album", m.group(2)
    ext = (m.group(3) or ".jpg").lower()
    if ext == ".gifv":  # an HTML player page; the clip itself is the .mp4
        return "video", f"https://i.imgur.com/{m.group(2)}.mp4"
    return "image", f"https://i.imgur.com/{m.group(2)}{ext}"


def parse_mpd(mpd: str) -> tuple[str | None, str | None]:
    """Highest-bandwidth video and audio file names in a v.redd.it DASH manifest."""
    best = {"video": (-1, None), "audio": (-1, None)}
    for attrs, body in re.findall(r"<Representation\b([^>]*)>(.*?)</Representation>", mpd, re.S):
        base = re.search(r"<BaseURL>\s*([^<\s]+)\s*</BaseURL>", body)
        if not base:
            continue
        bw = int((re.search(r'bandwidth="(\d+)"', attrs) or [None, 0])[1])
        kind = "audio" if "audio" in (attrs + base.group(1)).lower() else "video"
        if bw > best[kind][0]:
            best[kind] = (bw, base.group(1))
    return best["video"][1], best["audio"][1]


def album_images(st: Store, album: str) -> tuple[list[str], bool]:
    """Image URLs of an imgur album or gallery post, and whether the list is complete."""
    key = os.environ.get("IMGUR_CLIENT_ID")
    if key:  # official API, free key: https://api.imgur.com/oauth2/addclient
        for endpoint in (f"album/{album}/images", f"gallery/album/{album}/images", f"image/{album}"):
            r = st.s.get(f"https://api.imgur.com/3/{endpoint}", headers={"Authorization": f"Client-ID {key}"})
            if r.ok:
                data = r.json().get("data")
                data = data if isinstance(data, list) else [data]
                return [d.get("mp4") or d["link"] for d in data if d and d.get("link")], True
    page = f"https://imgur.com/a/{album}"
    if not st.robots.allowed(page):
        return [], False
    r = st.s.get(page)
    m = re.search(r'<meta property="og:image"[^>]*content="([^"?]+)', r.text) if r.ok else None
    return ([m.group(1)] if m else []), False


def collect_linked(st: Store, corpus: Path, refresh: bool) -> None:
    done: dict[str, list[str]] = read_json(st.out / "linked.json", {}) or {}
    attached = {f.name.split("_")[0] for f in (corpus / "reddit" / "media").glob("*_*.*")}  # reddit.py --media
    partial = 0
    for f in sorted((corpus / "reddit" / "posts").glob("*.json")):
        post = read_json(f, {}) or {}
        pid = post.get("id") or f.stem
        for where, url in reddit_links(post):
            plan = plan_link(url)
            if not plan or (url in done and (done[url] or not refresh)):
                continue
            kind, target = plan
            if kind == "image" and url == post.get("url") and pid in attached:
                continue
            stem = f"linked/{pid}_{hashlib.sha1(url.encode()).hexdigest()[:8]}"
            files: list[str | None] = []
            if kind in ("image", "video"):
                file = st.fetch(target, stem)
                if not file and "preview.redd.it" in target:  # expired signature; the original often survives
                    file = st.fetch("https://i.redd.it" + urllib.parse.urlsplit(target).path, stem)
                files = [file]
            elif kind == "vreddit":
                mpd = st.s.get(target + "/DASHPlaylist.mpd") if st.robots.allowed(target + "/") else None
                video, audio = parse_mpd(mpd.text) if mpd is not None and mpd.ok else (None, None)
                files = [st.fetch(f"{target}/{video}", stem) if video else None]
                if audio and files[0]:
                    st.fetch(f"{target}/{audio}", stem + "_audio")  # kept beside the video; merge with ffmpeg if wanted
            else:
                urls, complete = album_images(st, target)
                partial += not complete
                files = [st.fetch(plan_link(u)[1] if plan_link(u) else u, f"{stem}_{i:02d}") for i, u in enumerate(urls)]
            done[url] = [x for x in files if x]
            for file in done[url]:
                st.add("reddit", "Reddit · images and clips linked in posts and comments", file,
                       int(float(post.get("created_utc") or 0)), date=utc_date(post.get("created_utc")),
                       caption=f"{post.get('title', pid)} ({where})", link=f"https://www.reddit.com{post.get('permalink', '')}")
            log(f"  {pid} {kind}: {len(done[url])} file(s) from {url}")
            write_json(st.out / "linked.json", done)
    st.save()
    got = sum(len(v) for v in done.values())
    log(f"Reddit links: {got} files from {sum(1 for v in done.values() if v)} of {len(done)} links"
        + (f"; {partial} imgur albums gave only their cover (set IMGUR_CLIENT_ID for all images)" if partial else ""))


def collect_thumbs(st: Store, corpus: Path) -> None:
    videos = read_json(corpus / "youtube" / "videos.json", {}) or {}
    got = 0
    for vid, v in sorted(videos.items()):
        if v.get("status", "ok") != "ok" or not v.get("thumbnail"):
            continue
        if file := st.fetch(v["thumbnail"], f"youtube/{vid}"):
            st.add("youtube", "YouTube · thumbnails", file, 0, date=v.get("published"),
                   caption=f"{v.get('title')} · {v.get('channel')}", link=v.get("url"))
            got += 1
    st.save()
    log(f"YouTube: {got} thumbnails")


# --- Gallery -------------------------------------------------------------------

def gallery_items(out: Path, corpus: Path) -> list[dict]:
    """Everything to show: media.py's index plus files other collectors and capture.py saved."""
    items = [dict(e) for e in (read_json(out / "index.json", {}) or {}).values() if (out / e["file"]).exists()]
    rel = lambda p: Path(os.path.relpath(p, out)).as_posix()  # noqa: E731
    shown = IMAGE_EXT | VIDEO_EXT
    for d in sorted((corpus / "wiki").glob("*/images")):
        for f in sorted(d.iterdir()):
            if f.suffix.lower() in shown:
                items.append({"section": "wiki", "group": f"Wiki · {d.parent.name}", "file": rel(f),
                              "caption": f.stem.replace("_", " "),
                              "link": f"https://{d.parent.name}.fandom.com/wiki/File:{urllib.parse.quote(f.name)}"})
    for f in sorted((corpus / "reddit" / "media").glob("*_*.*")):
        if f.suffix.lower() not in shown:
            continue
        post = read_json(corpus / "reddit" / "posts" / f"{f.name.split('_')[0]}.json", {}) or {}
        items.append({"section": "reddit", "group": "Reddit · images attached to posts", "file": rel(f),
                      "order": int(float(post.get("created_utc") or 0)), "date": utc_date(post.get("created_utc")),
                      "caption": post.get("title", f.stem), "link": f"https://www.reddit.com{post.get('permalink', '')}"})
    own_index = out / "own" / "index.jsonl"
    labels = {}
    if own_index.exists():
        for line in own_index.read_text(encoding="utf-8").splitlines():
            if line.strip():
                e = json.loads(line)
                labels[e["file"]] = e.get("label")
    for f in sorted((out / "own").rglob("*")):
        if f.suffix.lower() in shown:
            items.append({"section": "own", "group": f"Your captures · {f.parent.name}", "file": rel(f),
                          "caption": labels.get(rel(f)) or f.stem})
    return items


def merge_groups(items: list[dict]) -> list[tuple[str, str, list[dict]]]:
    """(section, title, entries) per group, in section order; groups showing the same files are merged."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for e in items:
        groups.setdefault((e["section"], e["group"]), []).append(e)
    merged: dict[tuple, list] = {}
    for (section, name), entries in sorted(groups.items()):
        entries.sort(key=lambda e: (e.get("order") or 0, e["file"]))
        sig = (section, tuple(e["file"] for e in entries))
        merged.setdefault(sig, [section, [], entries])[1].append(name)
    out = []
    for section, names, entries in merged.values():
        split = [n.split(" · ") for n in names]
        common = 0
        while all(len(p) > common + 1 and p[common] == split[0][common] for p in split):
            common += 1
        title = " · ".join(split[0][:common] + [", ".join(" · ".join(p[common:]) for p in split)]) if common else "; ".join(names)
        out.append((section, title, entries))
    order = list(SECTIONS)
    return sorted(out, key=lambda g: order.index(g[0]) if g[0] in order else len(order))


PAGE_HEAD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>GrowStone screens</title>
<style>
:root{--bg:#fafaf9;--fg:#1c1917;--muted:#6b6560;--card:#fff;--line:#e7e5e4}
@media (prefers-color-scheme:dark){:root{--bg:#1c1917;--fg:#f5f5f4;--muted:#a8a29e;--card:#292524;--line:#44403c}}
body{margin:0;padding:16px clamp(16px,3vw,32px);background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif}
h1{font-size:22px;margin:4px 0} p.lede{color:var(--muted);margin:0 0 12px}
nav{columns:3 240px;font-size:13px;margin-bottom:8px} nav a{display:block;color:inherit;text-decoration:none} nav a:hover{text-decoration:underline}
h2{margin:36px 0 4px;font-size:19px} h3{margin:20px 0 8px;font-size:15px;border-bottom:1px solid var(--line);padding-bottom:4px}
small{color:var(--muted);font-weight:400}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px}
figure{margin:0;background:var(--card);border:1px solid var(--line);border-radius:6px;overflow:hidden}
figure img,figure video{display:block;width:100%;height:260px;object-fit:contain;background:rgba(127,127,127,.12)}
figcaption{padding:6px 8px;font-size:12px;color:var(--muted);overflow-wrap:anywhere} figcaption a{color:inherit}
</style></head><body>
"""


def write_gallery(out: Path, corpus: Path) -> Path:
    groups = merge_groups(gallery_items(out, corpus))
    esc = html.escape
    total = sum(len(g[2]) for g in groups)
    body = [PAGE_HEAD, "<h1>GrowStone screens</h1>",
            f'<p class="lede">{total} files in {len(groups)} groups, built {dt.date.today().isoformat()} by media.py. '
            "For study only: these belong to SUPERCAT and the people who posted them.</p><nav>"]
    body += [f'<a href="#g{i}">{esc(SECTIONS.get(s, s))}: {esc(t)} <small>{len(e)}</small></a>' for i, (s, t, e) in enumerate(groups)]
    body.append("</nav>")
    section = None
    for i, (sec, title, entries) in enumerate(groups):
        if sec != section:
            section = sec
            body.append(f"<h2>{esc(SECTIONS.get(sec, sec))}</h2>")
        body.append(f'<h3 id="g{i}">{esc(title)} <small>{len(entries)}</small></h3><div class="grid">')
        for e in entries:
            src = esc(urllib.parse.quote(e["file"]))
            cap = esc(e.get("caption") or Path(e["file"]).stem)
            if Path(e["file"]).suffix.lower() in VIDEO_EXT:
                media = f'<video src="{src}" controls preload="metadata"></video>'
            else:
                media = f'<a href="{src}"><img src="{src}" loading="lazy" alt="{cap}"></a>'
            meta = " · ".join(x for x in (esc(e.get("date") or ""),
                                          f'<a href="{esc(e["link"])}">source</a>' if e.get("link") else "") if x)
            body.append(f"<figure>{media}<figcaption>{cap}{'<br>' + meta if meta else ''}</figcaption></figure>")
        body.append("</div>")
    body.append("</body></html>\n")
    path = out / "gallery.html"
    write_text(path, "\n".join(body))
    log(f"gallery: {total} files in {len(groups)} groups -> {path}")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["store", "history", "linked", "thumbs", "gallery", "all"])
    ap.add_argument("--max-px", type=int, default=0,
                    help="longest side for store screenshots; 0 = original upload (default). Files already saved are kept")
    ap.add_argument("--fresh", action="store_true", help="fetch the Play pages again instead of using play_store.py's copies")
    ap.add_argument("--refresh", action="store_true", help="redo archived snapshots and retry links that failed before")
    ap.add_argument("--corpus", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    out = args.corpus / "media"
    st = Store(out, args.max_px)
    try:
        if args.what in ("store", "all"):
            collect_play(st, args.corpus, args.fresh)
            collect_appstore(st, args.corpus)
        if args.what in ("history", "all"):
            collect_history(st, args.corpus, args.refresh)
        if args.what in ("linked", "all"):
            collect_linked(st, args.corpus, args.refresh)
        if args.what in ("thumbs", "all"):
            collect_thumbs(st, args.corpus)
    finally:
        st.save()
        write_gallery(out, args.corpus)
    return 0


if __name__ == "__main__":
    sys.exit(main())
