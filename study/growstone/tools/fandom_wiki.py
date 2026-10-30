#!/usr/bin/env python3
"""Mirror the GrowStone Fandom wikis through the official MediaWiki API.

For every page it saves the wikitext (source of truth), the rendered HTML, a
readable Markdown text, and metadata (revision, categories, links, images,
external links). Image files (screenshots, icons) are downloaded with --images.
Runs are resumable: a page is skipped when its saved revision is current.

Fandom text is licensed CC BY-SA 3.0. Keep the attribution file if you quote it.

Examples:
  python3 fandom_wiki.py                      # both known wikis, text only
  python3 fandom_wiki.py --images             # plus all image files
  python3 fandom_wiki.py --wiki growstoneonline --limit 20
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import DEFAULT_OUT, PoliteSession, front_matter, html_to_text, log, read_json, slug, write_json, write_text

KNOWN_WIKIS = ["growstoneonline", "thegrowstoneonline"]
# 0 = articles, 4 = project, 10 = templates (often hold stat tables), 14 = categories
NAMESPACES = [0, 4, 10, 14]


class Wiki:
    def __init__(self, name: str, session: PoliteSession):
        self.name = name
        self.base = f"https://{name}.fandom.com"
        self.api = f"{self.base}/api.php"
        self.s = session

    def call(self, **params) -> dict:
        params.update(format="json", formatversion="2")
        r = self.s.get(self.api, params=params)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"{self.name}: {data['error']}")
        return data

    def paged(self, key: str, **params):
        """Follows MediaWiki 'continue' tokens."""
        cont: dict = {}
        while True:
            data = self.call(action="query", **params, **cont)
            yield from data.get("query", {}).get(key, [])
            if "continue" not in data:
                return
            cont = data["continue"]

    def all_pages(self):
        for ns in NAMESPACES:
            yield from self.paged("allpages", list="allpages", apnamespace=ns, aplimit="max")

    def latest_revisions(self, titles: list[str]) -> dict[str, dict]:
        data = self.call(action="query", prop="revisions", titles="|".join(titles),
                         rvprop="ids|timestamp|user|content", rvslots="main")
        out = {}
        for p in data["query"]["pages"]:
            if p.get("missing"):
                continue
            rev = p["revisions"][0]
            out[p["title"]] = {
                "pageid": p["pageid"], "ns": p["ns"], "revid": rev["revid"],
                "timestamp": rev["timestamp"], "user": rev.get("user"),
                "wikitext": rev["slots"]["main"].get("content", ""),
            }
        return out

    def parse(self, title: str) -> dict:
        return self.call(action="parse", page=title, redirects=1,
                         prop="text|categories|links|images|externallinks|displaytitle")["parse"]


def mirror_text(wiki: Wiki, out: Path, limit: int | None) -> int:
    pages_dir = out / "pages"
    index = read_json(out / "index.json", {})
    titles = [p["title"] for p in wiki.all_pages()]
    log(f"[{wiki.name}] {len(titles)} pages in namespaces {NAMESPACES}")
    if limit:
        titles = titles[:limit]
    saved = 0
    for i in range(0, len(titles), 50):  # 50 titles per revisions query is the API maximum
        batch = titles[i:i + 50]
        revs = wiki.latest_revisions(batch)
        for title in batch:
            rev = revs.get(title)
            if not rev:
                continue
            name = slug(title)
            if index.get(title, {}).get("revid") == rev["revid"] and (pages_dir / f"{name}.md").exists():
                continue
            parsed = wiki.parse(title)
            html = parsed["text"]
            _, text = html_to_text(html)
            meta = {
                "source": "fandom", "wiki": wiki.name, "title": title,
                "url": f"{wiki.base}/wiki/{title.replace(' ', '_')}",
                "revid": rev["revid"], "last_edit": rev["timestamp"], "last_editor": rev["user"],
                "license": "CC BY-SA 3.0 (Fandom)",
            }
            write_text(pages_dir / f"{name}.wikitext", rev["wikitext"])
            write_text(pages_dir / f"{name}.html", html)
            write_text(pages_dir / f"{name}.md", front_matter(meta) + f"# {title}\n\n{text}\n")
            write_json(pages_dir / f"{name}.json", {
                **meta,
                "categories": [c["category"] for c in parsed.get("categories", [])],
                "links": [l["title"] for l in parsed.get("links", []) if l.get("exists")],
                "images": parsed.get("images", []),
                "external_links": parsed.get("externallinks", []),
            })
            index[title] = {"file": name, "revid": rev["revid"], "last_edit": rev["timestamp"]}
            saved += 1
            log(f"  [{wiki.name}] saved {title}")
        write_json(out / "index.json", index)
    return saved


def mirror_images(wiki: Wiki, out: Path, limit: int | None) -> int:
    img_dir = out / "images"
    manifest = read_json(out / "images.json", {})
    n = 0
    for img in wiki.paged("allimages", list="allimages", ailimit="max", aiprop="url|size|mime|timestamp|sha1"):
        if limit and n >= limit:
            break
        n += 1
        name = img["name"]
        if manifest.get(name, {}).get("sha1") == img.get("sha1") and (img_dir / name).exists():
            continue
        r = wiki.s.get(img["url"])
        if r.status_code != 200:
            log(f"  [{wiki.name}] image {name}: HTTP {r.status_code}")
            continue
        img_dir.mkdir(parents=True, exist_ok=True)
        (img_dir / name).write_bytes(r.content)
        manifest[name] = {k: img.get(k) for k in ("url", "size", "mime", "timestamp", "sha1", "width", "height")}
        write_json(out / "images.json", manifest)
        log(f"  [{wiki.name}] image {name} ({img.get('size', 0) // 1024} KB)")
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wiki", action="append", help=f"Fandom subdomain (default: {', '.join(KNOWN_WIKIS)})")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT / "wiki")
    ap.add_argument("--images", action="store_true", help="also download every image file")
    ap.add_argument("--limit", type=int, help="max pages (and images) per wiki, for a quick test")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests (default 1.0)")
    args = ap.parse_args(argv)

    session = PoliteSession(min_interval=args.delay)
    for name in args.wiki or KNOWN_WIKIS:
        wiki = Wiki(name, session)
        out = args.out / name
        try:
            info = wiki.call(action="query", meta="siteinfo", siprop="general|statistics")["query"]
        except Exception as e:  # noqa: BLE001 - report and continue with the next wiki
            log(f"[{name}] unreachable: {e}")
            continue
        write_json(out / "siteinfo.json", info)
        write_text(out / "ATTRIBUTION.md",
                   f"Content mirrored from {wiki.base} for private research.\n"
                   "Text is licensed CC BY-SA 3.0 by its Fandom contributors; "
                   "per-page authors are in each page's history on the site.\n")
        stats = info.get("statistics", {})
        log(f"[{name}] {info['general'].get('sitename')}: {stats.get('articles')} articles, {stats.get('images')} images")
        saved = mirror_text(wiki, out, args.limit)
        log(f"[{name}] text done: {saved} new or updated pages")
        if args.images:
            mirror_images(wiki, out, args.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
