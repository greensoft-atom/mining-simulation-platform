#!/usr/bin/env python3
"""Fetch public web pages about GrowStone (reviews, blogs, guides, forum threads).

Sources:
  * sources.txt next to this script: curated seed URLs (edit freely);
  * --url: extra URLs on the command line;
  * --from-corpus: every outbound link already found in the wiki and Reddit
    output (a cheap discovery step that needs no search engine).

Every URL is checked against robots.txt first. Sites whose terms forbid
scraping, or that need a login, are skipped (see DENY below). With --depth 1
the script also follows same-site links whose URL or anchor text mentions the
game. A page is kept only if its text mentions GrowStone, unless --keep-all.

Examples:
  python3 web_pages.py
  python3 web_pages.py --from-corpus --depth 1
  python3 web_pages.py --url https://example.com/growstone-guide
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.parse
from pathlib import Path

from common import DEFAULT_OUT, TOOLS_DIR, PoliteSession, Robots, front_matter, html_to_text, log, read_json, slug, write_json, write_text

# The game's own names (English, Korean "돌키우기"). The developer name alone is not enough.
RELEVANT = re.compile(r"grow\s*stone|돌\s*키우기", re.I)
# Covered by a dedicated collector, against the site's terms to scrape, or login-only.
DENY = re.compile(r"(^|\.)(fandom\.com|wikia\.com|reddit\.com|redd\.it|play\.google\.com|facebook\.com|fb\.com|instagram\.com|"
                  r"youtube\.com|youtu\.be|twitter\.com|x\.com|discord\.(gg|com)|tiktok\.com|apps\.apple\.com|"
                  r"accounts\.google\.com|line\.me)$", re.I)
SKIP_EXT = re.compile(r"\.(jpe?g|png|gif|webp|svg|mp4|webm|pdf|zip|apk|exe|css|js)(\?|$)", re.I)
HREF = re.compile(r"""<a\s[^>]*href=["']([^"'#]+)["'][^>]*>(.*?)</a>""", re.I | re.S)


def seed_urls() -> list[str]:
    path = TOOLS_DIR / "sources.txt"
    if not path.exists():
        return []
    return [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]


def corpus_links(corpus: Path) -> list[str]:
    links: set[str] = set()
    for f in corpus.glob("wiki/*/pages/*.json"):
        links.update((read_json(f, {}) or {}).get("external_links", []))
    url_re = re.compile(r"https?://[^\s)\]>\"']+")
    for f in corpus.glob("reddit/posts/*.json"):
        post = read_json(f, {}) or {}
        if post.get("url"):
            links.add(post["url"])
        for text in [post.get("selftext") or ""] + [c.get("body") or "" for c in post.get("comments", [])]:
            links.update(url_re.findall(text))
    return sorted(links)


def allowed_host(url: str) -> bool:
    host = urllib.parse.urlsplit(url).hostname or ""
    return url.startswith(("http://", "https://")) and not DENY.search(host) and not SKIP_EXT.search(url)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", action="append", default=[])
    ap.add_argument("--from-corpus", action="store_true", help="also fetch links found in the wiki/Reddit output")
    ap.add_argument("--depth", type=int, default=0, help="follow relevant same-site links this many levels (0-2)")
    ap.add_argument("--keep-all", action="store_true", help="keep pages even if they never mention the game")
    ap.add_argument("--refresh", action="store_true", help="re-fetch pages already saved")
    ap.add_argument("--delay", type=float, default=3.0, help="seconds between requests to the same site")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT / "web")
    args = ap.parse_args(argv)

    session = PoliteSession(min_interval=args.delay)
    robots = Robots(session)
    index = read_json(args.out / "index.json", {})
    queue = [(u, 0) for u in seed_urls() + args.url]
    if args.from_corpus:
        queue += [(u, 0) for u in corpus_links(args.out.parent)]
    seen: set[str] = set()

    while queue:
        url, depth = queue.pop(0)
        url = url.split("#")[0]
        if url in seen:
            continue
        seen.add(url)
        if not allowed_host(url):
            index.setdefault(url, {"status": "skipped: denied site or file type"})
            continue
        if not args.refresh and index.get(url, {}).get("status") == "saved":
            continue
        if not robots.allowed(url):
            index[url] = {"status": "skipped: robots.txt"}
            log(f"robots.txt disallows {url}")
            continue
        try:
            r = session.get(url)
        except Exception as e:  # noqa: BLE001
            index[url] = {"status": f"error: {e.__class__.__name__}"}
            continue
        if r.status_code != 200 or "html" not in r.headers.get("Content-Type", ""):
            index[url] = {"status": f"http {r.status_code} {r.headers.get('Content-Type', '')}"}
            log(f"HTTP {r.status_code} {url}")
            continue
        html = r.text
        title, text = html_to_text(html)
        if not args.keep_all and not RELEVANT.search(title + " " + text):
            index[url] = {"status": "skipped: no mention of the game", "title": title}
            continue
        final = r.url.split("#")[0]
        dup = next((k for k, v in index.items() if v.get("status") == "saved" and v.get("final_url") == final and k != url), None)
        if dup:
            index[url] = {"status": f"duplicate of {dup}"}
            continue
        parts = urllib.parse.urlsplit(r.url)
        name = slug(parts.netloc + parts.path + ("?" + parts.query if parts.query else ""))
        meta = {"source": "web", "site": parts.netloc, "title": title, "url": r.url,
                "fetched": r.headers.get("Date"), "last_modified": r.headers.get("Last-Modified")}
        write_text(args.out / "pages" / f"{name}.html", html)
        write_text(args.out / "pages" / f"{name}.md", front_matter(meta) + f"# {title}\n\n{text}\n")
        index[url] = {"status": "saved", "file": name, "title": title, "final_url": final}
        log(f"saved {url}  ({len(text)} chars)")
        if depth < min(args.depth, 2):
            for href, anchor in HREF.findall(html):
                nxt = urllib.parse.urljoin(r.url, href)
                if urllib.parse.urlsplit(nxt).netloc == parts.netloc and RELEVANT.search(nxt + " " + anchor):
                    queue.append((nxt, depth + 1))
        write_json(args.out / "index.json", index)

    write_json(args.out / "index.json", index)
    saved = sum(1 for v in index.values() if v.get("status") == "saved")
    log(f"done: {saved} pages saved; see {args.out / 'index.json'} for skips and errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
