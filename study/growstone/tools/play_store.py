#!/usr/bin/env python3
"""Snapshot the public Google Play listing of GrowStone in several languages.

What it collects, per language/country: title, rating, review count, downloads,
last update, description, tags, and the reviews Google Play shows on the page
(about 3 per language, with developer replies), parsed into records. Each run
is saved under a date, so repeated runs build a rating and review history.

What it does NOT do: download the full review feed. Play's robots.txt
disallows the endpoints that serve it (/_ and /store/getreviews), and Google's
terms only allow automated access that robots.txt permits. For bulk reviews,
read them in the store and paste the useful ones into a CSV, or export them
from a licensed review-data service (AppFollow, AppTweak, Appbot, data.ai),
then load them with import_reviews.py.

Examples:
  python3 play_store.py                        # all default locales
  python3 play_store.py --locale ko-KR --locale en-US
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

from common import DEFAULT_OUT, PoliteSession, Robots, front_matter, html_to_text, log, write_json, write_text

APP_ID = "net.supercat.stone"
# GrowStone's biggest audiences by review language, plus our own target market.
DEFAULT_LOCALES = ["en-US", "ko-KR", "zh-TW", "ja-JP", "id-ID", "vi-VN", "th-TH", "pt-BR", "es-ES",
                   "de-DE", "fr-FR", "ru-RU", "tr-TR", "it-IT", "pl-PL"]
RATING_LINE = re.compile(r"^\[[^\]]*\d[^\]]*\]$")


def star_value(label: str) -> int | None:
    digits = [int(d) for d in re.findall(r"\d+(?:[.,]\d+)?", label) if "." not in d and "," not in d]
    if not digits:
        return None
    # Korean puts the scale first ("별표 5개 만점에 4개"); other languages put the rating first.
    return digits[1] if "만점" in label and len(digits) > 1 else digits[0]


def parse_reviews(text: str, developer: str = "SUPERCAT") -> tuple[list[dict], str | None]:
    """Language-independent parse of the reviews Google Play shows on the page.

    Each review is: author, one or more '- <menu>' lines (flag / review history),
    a '[<star label>]' line, a date, the text, a short 'N found this helpful'
    line, and optionally a developer reply (developer name, date, text).
    Returns (reviews, whats_new).
    """
    lines = [l.strip() for l in text.splitlines()]
    nonempty = [i for i, l in enumerate(lines) if l]
    pos = {i: k for k, i in enumerate(nonempty)}
    anchors = []  # (author_idx, rating_idx)
    for i in nonempty:
        if not RATING_LINE.match(lines[i]):
            continue
        k = pos[i] - 1
        menus = 0
        while k >= 0 and lines[nonempty[k]].startswith("- "):
            menus += 1
            k -= 1
        if menus and k >= 0:
            anchors.append((nonempty[k], i))
    reviews = []
    for n, (author_idx, rating_idx) in enumerate(anchors):
        stop = anchors[n + 1][0] if n + 1 < len(anchors) else len(lines)
        heading = next((j for j in range(rating_idx, stop) if lines[j].startswith("## ")), None)
        if heading is not None:
            stop = heading
        content = [lines[j] for j in range(rating_idx + 1, stop) if lines[j]]
        date, rest = (content[0], content[1:]) if content else ("", [])
        dev = next((j for j, l in enumerate(rest) if l == developer), None)
        body, reply = (rest[:dev], rest[dev + 1:]) if dev is not None else (rest, [])
        helpful = None
        if body and re.search(r"\d", body[-1]) and len(body[-1]) < 80 and len(body) > 1:
            helpful = body.pop()
        reviews.append({
            "author": lines[author_idx], "date": date, "rating": star_value(lines[rating_idx]),
            "text": "\n".join(body), "helpful": helpful,
            "developer_reply_date": reply[0] if reply else None,
            "developer_reply": "\n".join(reply[1:]) or None,
        })
    whats_new = None
    if anchors:
        last = anchors[-1][1]
        h = next((j for j in range(last, len(lines)) if lines[j].startswith("## ")), None)
        if h is not None:
            nxt = next((j for j in range(h + 1, len(lines)) if lines[j].startswith(("## ", "flag"))), len(lines))
            whats_new = "\n".join(l for l in lines[h + 1:nxt] if l) or None
    return reviews, whats_new


def field(text: str, pattern: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1).strip() if m else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", default=APP_ID)
    ap.add_argument("--locale", action="append", help=f"hl-GL pairs (default: {len(DEFAULT_LOCALES)} locales)")
    ap.add_argument("--developer", default="SUPERCAT", help="developer name as shown above its replies")
    ap.add_argument("--delay", type=float, default=5.0)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT / "play")
    args = ap.parse_args(argv)

    s = PoliteSession(min_interval=args.delay)
    robots = Robots(s)
    today = dt.date.today().isoformat()
    summary = []
    for loc in args.locale or DEFAULT_LOCALES:
        hl, _, gl = loc.partition("-")
        url = f"https://play.google.com/store/apps/details?id={args.app}&hl={hl}&gl={gl or 'US'}"
        if not robots.allowed(url):
            log(f"robots.txt disallows {url}; stopping")
            return 1
        r = s.get(url)
        if r.status_code != 200:
            log(f"{loc}: HTTP {r.status_code}")
            continue
        title, text = html_to_text(r.text, keep={"header"})
        reviews, whats_new = parse_reviews(text, args.developer)
        info = {
            "locale": loc, "url": url, "snapshot": today, "title": title,
            "rating": field(text, r"\n(\d[.,]\d)\s*\n?star"),
            "reviews_count": field(text, r"\n([\d.,]+\s*[KMB万만천]?)\s*(?:reviews|則評論|件のレビュー|리뷰|ulasan|đánh giá)"),
            # Needs a magnitude (1M+, 100만+, 500K+) so the age rating ("3+") never matches.
            "downloads": field(text, r"\n(\d[\d.,]*\s*(?:[KMB万만천]|000)\+)\s*\n"),
            "updated": field(text, r"(?:Updated on|업데이트 날짜|更新日期|更新日)\s*\n+\s*([^\n]+)"),
            "whats_new": whats_new,
            "featured_reviews": reviews,
        }
        stem = f"{today}_{loc}"
        write_text(args.out / "html" / f"{stem}.html", r.text)
        write_json(args.out / f"{stem}.json", info)
        md = [front_matter({"source": "play", "title": f"Google Play listing ({loc})", "url": url,
                            "published": today, "locale": loc}),
              f"# Google Play listing, {loc}, {today}", "",
              f"Rating {info['rating']} · {info['reviews_count']} reviews · {info['downloads']} downloads · updated {info['updated']}", "",
              "## What's new", "", whats_new or "(not found)", "",
              "## Featured reviews", ""]
        for rv in reviews:
            md += [f"### {rv['author']} · {rv['date']} · {rv['rating'] or '?'}★", "", rv["text"], ""]
            if rv["helpful"]:
                md += [f"*{rv['helpful']}*", ""]
            if rv["developer_reply"]:
                md += [f"> **Developer reply ({rv['developer_reply_date']}):** " + rv["developer_reply"].replace("\n", "\n> "), ""]
        md += ["## Full page text", "", text]
        write_text(args.out / f"{stem}.md", "\n".join(md) + "\n")
        summary.append({k: info[k] for k in ("locale", "rating", "reviews_count", "downloads", "updated")} | {"featured": len(reviews)})
        log(f"{loc}: rating {info['rating']}, {info['reviews_count']} reviews, {len(reviews)} featured reviews parsed")
    write_json(args.out / f"{today}_summary.json", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
