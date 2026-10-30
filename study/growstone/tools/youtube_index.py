#!/usr/bin/env python3
"""Build an index of GrowStone videos: the best public source of current screens.

Two sources, combined in one index:

  --from-corpus  (no key) Every YouTube link already found in the wiki, Reddit,
                 Play and web output, resolved to title and channel through
                 YouTube's official oEmbed endpoint (the interface YouTube
                 provides for embedding; allowed by its robots.txt). It also
                 records where each link was found.

  search         (needs YOUTUBE_API_KEY) The official YouTube Data API v3: keyword
                 search plus date, length and view counts. Keys are free and
                 self-service: Google Cloud console -> enable "YouTube Data API
                 v3" -> Credentials -> API key. Each search page costs 100 of the
                 10,000 daily quota units.

Not used: yt-dlp, Invidious/Piped instances, or scraping search result pages.
YouTube's Terms of Service forbid automated access except by search engines
or with written permission, and its robots.txt disallows /results, /comment,
/feeds/videos.xml and /timedtext_video. Video files are never downloaded.

Examples:
  python3 youtube_index.py --from-corpus                # no key needed
  python3 youtube_index.py --from-corpus --search       # with YOUTUBE_API_KEY
  python3 youtube_index.py --search --query "growstone pvp" --pages 2
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from common import DEFAULT_OUT, PoliteSession, front_matter, log, read_json, write_json, write_text

API = "https://www.googleapis.com/youtube/v3"
OEMBED = "https://www.youtube.com/oembed"
DEFAULT_QUERIES = ["growstone online", "grow stone online gameplay", "그로우스톤", "돌키우기 온라인",
                   "growstone guide", "growstone update", "growstone raid", "growstone castle battle"]
VIDEO_ID = re.compile(r"(?:youtube\.com/(?:watch\?(?:[^\s\"'<>]*?&(?:amp;)?)?v=|embed/|shorts/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})")


def iso_duration(d: str) -> str:
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return d or ""
    h, mi, s = (int(x or 0) for x in m.groups())
    return f"{h}:{mi:02d}:{s:02d}" if h else f"{mi}:{s:02d}"


def corpus_video_ids(corpus: Path) -> dict[str, set[str]]:
    """video id -> set of corpus files (relative) that link to it."""
    found: dict[str, set[str]] = {}
    for f in corpus.rglob("*"):
        if f.suffix not in (".md", ".json", ".wikitext", ".html") or "youtube" in f.parts:
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for vid in VIDEO_ID.findall(text):
            found.setdefault(vid, set()).add(str(f.relative_to(corpus).with_suffix("")))
    return found


def oembed(s: PoliteSession, vid: str) -> dict:
    r = s.get(OEMBED, params={"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"})
    if r.status_code != 200:  # 401: embedding disabled or private; 404: removed
        return {"status": f"unavailable (HTTP {r.status_code})"}
    d = r.json()
    return {"status": "ok", "title": d.get("title"), "channel": d.get("author_name"), "channel_url": d.get("author_url"),
            "thumbnail": d.get("thumbnail_url")}


def api_details(s: PoliteSession, key: str, ids: list[str]) -> dict[str, dict]:
    out = {}
    for i in range(0, len(ids), 50):
        d = s.get(f"{API}/videos", params={"part": "snippet,contentDetails,statistics",
                                           "id": ",".join(ids[i:i + 50]), "key": key}).json()
        for v in d.get("items", []):
            sn, st = v["snippet"], v.get("statistics", {})
            out[v["id"]] = {"status": "ok", "title": sn["title"], "channel": sn["channelTitle"],
                            "published": sn["publishedAt"][:10],
                            "duration": iso_duration(v["contentDetails"].get("duration")),
                            "views": int(st.get("viewCount", 0)), "language": sn.get("defaultAudioLanguage"),
                            "description": sn.get("description", "")[:2000]}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-corpus", action="store_true", help="index videos linked from the collected corpus (no key)")
    ap.add_argument("--search", action="store_true", help="keyword search via the Data API (needs YOUTUBE_API_KEY)")
    ap.add_argument("--query", action="append")
    ap.add_argument("--pages", type=int, default=4, help="search result pages (50 videos each) per query")
    ap.add_argument("--refresh", action="store_true", help="re-resolve videos already in the index")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT / "youtube")
    args = ap.parse_args(argv)
    key = os.environ.get("YOUTUBE_API_KEY")
    if not (args.from_corpus or args.search):
        ap.error("choose --from-corpus (no key) and/or --search (needs YOUTUBE_API_KEY)")
    if args.search and not key:
        raise SystemExit("--search needs YOUTUBE_API_KEY (free, self-service). --from-corpus works without one.")

    s = PoliteSession(min_interval=1.0)
    videos: dict[str, dict] = read_json(args.out / "videos.json", {}) or {}

    if args.from_corpus:
        linked = corpus_video_ids(args.out.parent)
        log(f"{len(linked)} distinct videos linked from the corpus")
        for vid, files in sorted(linked.items()):
            v = videos.setdefault(vid, {})
            v["found_in"] = sorted(set(v.get("found_in", [])) | files)
            if v.get("status") and not args.refresh:
                continue
            v.update(oembed(s, vid))
            log(f"  {vid}: {v.get('title') or v['status']}")
        write_json(args.out / "videos.json", videos)

    if args.search:
        for q in args.query or DEFAULT_QUERIES:
            token = None
            for _ in range(args.pages):
                r = s.get(f"{API}/search", params={"part": "snippet", "q": q, "type": "video", "maxResults": 50,
                                                    "order": "relevance", "pageToken": token, "key": key})
                r.raise_for_status()
                data = r.json()
                for it in data.get("items", []):
                    videos.setdefault(it["id"]["videoId"], {}).setdefault("query", q)
                token = data.get("nextPageToken")
                if not token:
                    break
            log(f"'{q}': {len(videos)} videos so far")
    if key:  # fill in dates, lengths and views for everything known
        missing = [vid for vid, v in videos.items() if "published" not in v or args.refresh]
        for vid, details in api_details(s, key, missing).items():
            videos[vid].update(details)
    for vid, v in videos.items():
        v["url"] = f"https://www.youtube.com/watch?v={vid}"
    write_json(args.out / "videos.json", videos)

    rows = sorted(videos.values(), key=lambda v: (v.get("published") or "", v.get("title") or ""), reverse=True)
    lines = [front_matter({"source": "youtube", "title": "GrowStone video index", "url": ""}),
             "# GrowStone videos", "",
             "| Published | Length | Views | Channel | Title | Found in |", "|---|---|---|---|---|---|"]
    for v in rows:
        if v.get("status", "ok") != "ok":
            continue
        cell = lambda x: str(x or "").replace("|", "/")  # noqa: E731
        views = f"{v['views']:,}" if isinstance(v.get("views"), int) else ""
        found = ", ".join(v.get("found_in", [])[:3]) + (" …" if len(v.get("found_in", [])) > 3 else "")
        lines.append(f"| {cell(v.get('published'))} | {cell(v.get('duration'))} | {views} | {cell(v.get('channel'))} "
                     f"| [{cell(v.get('title'))}]({v['url']}) | {cell(found) or cell(v.get('query'))} |")
    gone = sum(1 for v in videos.values() if v.get("status", "ok") != "ok")
    lines += ["", f"{gone} linked videos are no longer available (removed, private or embedding disabled)."]
    write_text(args.out / "videos.md", "\n".join(lines) + "\n")
    log(f"done: {len(videos) - gone} available videos -> {args.out / 'videos.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
