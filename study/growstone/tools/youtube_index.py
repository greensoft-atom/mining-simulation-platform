#!/usr/bin/env python3
"""Build an index of GrowStone gameplay videos with the official YouTube Data API.

Videos are the best public source of current screens, UI flows and pacing.
This script lists them with title, channel, date, length, views and link, so
you can watch the relevant ones and take your own notes and screenshots. It
does not download video (YouTube's terms forbid that).

Needs a free API key (Google Cloud console -> YouTube Data API v3):
  export YOUTUBE_API_KEY=...
Each search page costs 100 quota units of the default 10,000 per day.

Examples:
  python3 youtube_index.py
  python3 youtube_index.py --query "growstone pvp" --pages 2
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from common import DEFAULT_OUT, PoliteSession, log, read_json, write_json, write_text

API = "https://www.googleapis.com/youtube/v3"
DEFAULT_QUERIES = ["growstone online", "grow stone online gameplay", "그로우스톤", "growstone guide",
                   "growstone update", "growstone raid", "growstone castle battle"]


def iso_duration(d: str) -> str:
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return d or ""
    h, mi, s = (int(x or 0) for x in m.groups())
    return f"{h}:{mi:02d}:{s:02d}" if h else f"{mi}:{s:02d}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--query", action="append")
    ap.add_argument("--pages", type=int, default=4, help="result pages (50 videos each) per query")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT / "youtube")
    args = ap.parse_args(argv)
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        raise SystemExit("Set YOUTUBE_API_KEY (YouTube Data API v3).")

    s = PoliteSession(min_interval=0.5)
    videos = read_json(args.out / "videos.json", {})
    for q in args.query or DEFAULT_QUERIES:
        token = None
        for _ in range(args.pages):
            r = s.get(f"{API}/search", params={"part": "snippet", "q": q, "type": "video", "maxResults": 50,
                                                "order": "relevance", "pageToken": token, "key": key})
            r.raise_for_status()
            data = r.json()
            ids = [it["id"]["videoId"] for it in data.get("items", [])]
            if ids:
                d = s.get(f"{API}/videos", params={"part": "snippet,contentDetails,statistics",
                                                   "id": ",".join(ids), "key": key}).json()
                for v in d.get("items", []):
                    sn, st = v["snippet"], v.get("statistics", {})
                    videos[v["id"]] = {
                        "title": sn["title"], "channel": sn["channelTitle"], "published": sn["publishedAt"][:10],
                        "duration": iso_duration(v["contentDetails"].get("duration")),
                        "views": int(st.get("viewCount", 0)), "language": sn.get("defaultAudioLanguage"),
                        "description": sn.get("description", "")[:2000],
                        "url": f"https://www.youtube.com/watch?v={v['id']}", "query": q,
                    }
            log(f"'{q}': {len(videos)} videos so far")
            token = data.get("nextPageToken")
            if not token:
                break
        write_json(args.out / "videos.json", videos)

    rows = sorted(videos.values(), key=lambda v: v["published"], reverse=True)
    lines = ["# GrowStone videos (newest first)", "", "| Published | Length | Views | Channel | Title |", "|---|---|---|---|---|"]
    for v in rows:
        title = v["title"].replace("|", "/")
        lines.append(f"| {v['published']} | {v['duration']} | {v['views']:,} | {v['channel'].replace('|', '/')} | [{title}]({v['url']}) |")
    write_text(args.out / "videos.md", "\n".join(lines) + "\n")
    log(f"done: {len(videos)} videos -> {args.out / 'videos.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
