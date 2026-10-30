#!/usr/bin/env python3
"""Collect GrowStone discussions from Reddit: r/GrowStone plus site-wide mentions.

Uses the official Reddit Data API (OAuth, app-only, read-only). Create a free
"script" app at https://www.reddit.com/prefs/apps and export:

  export REDDIT_CLIENT_ID=...        # the id under the app name
  export REDDIT_CLIENT_SECRET=...
  export GS_RESEARCH_UA="growstone-research/0.1 (by /u/<your_reddit_name>)"

Without credentials it falls back to the public .json endpoints at one request
per 6.5 s. Reddit often answers those with 403 from cloud machines, so OAuth is
the reliable path.

A listing returns at most ~1,000 posts, so the script merges many listings
(new, hot, top by period, controversial, and searches with several sorts) and
de-duplicates. Comment threads are fetched in full, expanding "load more"
stubs (OAuth only). Re-runs only re-fetch threads whose comment count changed.

Reddit content belongs to its authors: keep it private, don't republish.

Examples:
  python3 reddit.py                                 # r/GrowStone + site-wide search
  python3 reddit.py --media                         # also download images in posts
  python3 reddit.py --limit 25 --no-sitewide        # quick test
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
import time
from pathlib import Path

from common import DEFAULT_OUT, PoliteSession, front_matter, log, read_json, write_json, write_text

DEFAULT_QUERIES = ["growstone", "\"grow stone online\"", "\"grow stone\" supercat"]
RELEVANT = re.compile(r"grow\s*stone|supercat", re.I)
SUB_LISTINGS = [("new", {}), ("hot", {}), ("rising", {}),
                ("top", {"t": "all"}), ("top", {"t": "year"}), ("top", {"t": "month"}), ("top", {"t": "week"}),
                ("controversial", {"t": "all"})]
SEARCH_SORTS = ["new", "top", "relevance", "comments"]
POST_FIELDS = ["id", "name", "subreddit", "title", "author", "created_utc", "score", "upvote_ratio",
               "num_comments", "link_flair_text", "permalink", "url", "domain", "is_self", "selftext",
               "over_18", "edited", "post_hint"]


class Reddit:
    def __init__(self):
        cid, secret = os.environ.get("REDDIT_CLIENT_ID"), os.environ.get("REDDIT_CLIENT_SECRET")
        self.oauth = bool(cid and secret)
        self.s = PoliteSession(min_interval=0.7 if self.oauth else 6.5)
        self.token_expiry = 0.0
        self._cid, self._secret = cid, secret
        self.base = "https://oauth.reddit.com" if self.oauth else "https://www.reddit.com"
        log(f"Reddit mode: {'OAuth (official API)' if self.oauth else 'public JSON fallback (slow; may be blocked)'}")

    def _auth(self) -> None:
        if not self.oauth or time.time() < self.token_expiry - 60:
            return
        r = self.s.post("https://www.reddit.com/api/v1/access_token",
                        auth=(self._cid, self._secret), data={"grant_type": "client_credentials"})
        r.raise_for_status()
        tok = r.json()
        self.s.s.headers["Authorization"] = f"bearer {tok['access_token']}"
        self.token_expiry = time.time() + tok.get("expires_in", 3600)

    def get(self, path: str, **params) -> dict | list:
        self._auth()
        url = self.base + path + ("" if self.oauth else ".json")
        params.setdefault("raw_json", 1)
        r = self.s.get(url, params=params)
        # Honour the documented rate-limit headers (100 queries per minute for OAuth clients).
        remaining, reset = r.headers.get("X-Ratelimit-Remaining"), r.headers.get("X-Ratelimit-Reset")
        if remaining and reset and float(remaining) < 2:
            log(f"  rate limit nearly used; sleeping {reset}s")
            time.sleep(float(reset) + 1)
        if r.status_code == 403 and not self.oauth:
            raise SystemExit("Reddit refused the public endpoint (403). Set REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET.")
        r.raise_for_status()
        return r.json()

    def listing(self, path: str, limit: int | None, **params):
        after, n = None, 0
        while True:
            data = self.get(path, limit=100, after=after, **params)["data"]
            for child in data["children"]:
                if child["kind"] == "t3":
                    yield child["data"]
                    n += 1
                    if limit and n >= limit:
                        return
            after = data.get("after")
            if not after:
                return

    def thread(self, post_id: str) -> tuple[dict, list[dict]]:
        post_listing, comment_listing = self.get(f"/comments/{post_id}", limit=500, depth=50, sort="top")
        post = post_listing["data"]["children"][0]["data"]
        comments: list[dict] = []
        pending: list[str] = []
        flatten(comment_listing["data"]["children"], comments, pending)
        # Expand "load more comments" stubs, 100 ids per call (an OAuth-only endpoint).
        while pending and self.oauth:
            batch, pending = pending[:100], pending[100:]
            data = self.get("/api/morechildren", link_id=f"t3_{post_id}", children=",".join(batch),
                            api_type="json", sort="top")
            things = data.get("json", {}).get("data", {}).get("things", [])
            flatten(things, comments, pending)
        return post, comments


def flatten(children: list, out: list[dict], pending: list[str]) -> None:
    for c in children:
        if c["kind"] == "more":
            pending.extend(c["data"].get("children", []))
            continue
        if c["kind"] != "t1":
            continue
        d = c["data"]
        out.append({k: d.get(k) for k in ("id", "parent_id", "author", "body", "score", "created_utc", "depth", "edited")})
        replies = d.get("replies")
        if isinstance(replies, dict):
            flatten(replies["data"]["children"], out, pending)


def utc(ts) -> str:
    return dt.datetime.fromtimestamp(float(ts or 0), dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def render_markdown(post: dict, comments: list[dict]) -> str:
    meta = {"source": "reddit", "subreddit": post["subreddit"], "title": post["title"],
            "url": "https://www.reddit.com" + post["permalink"], "author": post.get("author"),
            "created": utc(post["created_utc"]), "score": post.get("score"),
            "num_comments": post.get("num_comments"), "link": None if post.get("is_self") else post.get("url")}
    lines = [front_matter(meta), f"# {post['title']}", "",
             f"*r/{post['subreddit']} · u/{post.get('author')} · {utc(post['created_utc'])} · score {post.get('score')}*", ""]
    if post.get("selftext"):
        lines += [post["selftext"], ""]
    elif post.get("url"):
        lines += [f"Link: {post['url']}", ""]
    lines += [f"## Comments ({len(comments)})", ""]
    by_parent: dict[str, list[dict]] = {}
    for c in comments:
        by_parent.setdefault(c["parent_id"], []).append(c)

    def walk(parent: str, depth: int) -> None:
        for c in by_parent.get(parent, []):
            quote = "> " * depth
            body = (c.get("body") or "").replace("\n", "\n" + quote + "  ")
            lines.append(f"{quote}- **u/{c.get('author')}** ({c.get('score')} · {utc(c.get('created_utc'))}): {body}")
            walk(f"t1_{c['id']}", depth + 1)

    walk(f"t3_{post['id']}", 0)
    return "\n".join(lines) + "\n"


def media_urls(post: dict) -> list[str]:
    urls = []
    if post.get("media_metadata"):  # galleries
        for m in post["media_metadata"].values():
            src = (m.get("s") or {}).get("u") or (m.get("s") or {}).get("gif")
            if src:
                urls.append(src)
    elif re.search(r"\.(jpe?g|png|gif|webp)$", post.get("url", ""), re.I) or post.get("domain") in ("i.redd.it", "i.imgur.com"):
        urls.append(post["url"])
    return urls


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subreddit", action="append", help="default: GrowStone")
    ap.add_argument("--query", action="append", help=f"site-wide search terms (default: {DEFAULT_QUERIES})")
    ap.add_argument("--no-sitewide", action="store_true", help="only the subreddit(s)")
    ap.add_argument("--media", action="store_true", help="download images and galleries attached to posts")
    ap.add_argument("--limit", type=int, help="max posts per listing, for a quick test")
    ap.add_argument("--refresh", action="store_true", help="re-fetch every thread even if unchanged")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT / "reddit")
    args = ap.parse_args(argv)

    rd = Reddit()
    subs = args.subreddit or ["GrowStone"]
    queries = args.query or DEFAULT_QUERIES
    found: dict[str, dict] = {}

    for sub in subs:
        try:
            write_json(args.out / f"about_{sub}.json", rd.get(f"/r/{sub}/about")["data"])
        except Exception as e:  # noqa: BLE001
            log(f"r/{sub}: about failed ({e})")
        for kind, params in SUB_LISTINGS:
            before = len(found)
            for p in rd.listing(f"/r/{sub}/{kind}", args.limit, **params):
                found[p["id"]] = p
            log(f"r/{sub} {kind} {params.get('t', '')}: +{len(found) - before} (total {len(found)})")
        for q in ["stone", "pet", "clan", "pvp", "craft", "fishing", "trade", "guide", "update", "event"]:
            for sort in ("relevance", "new"):
                before = len(found)
                for p in rd.listing(f"/r/{sub}/search", args.limit, q=q, restrict_sr=1, sort=sort, t="all"):
                    found[p["id"]] = p
                if len(found) > before:
                    log(f"r/{sub} search '{q}' ({sort}): +{len(found) - before}")

    if not args.no_sitewide:
        for q in queries:
            for sort in SEARCH_SORTS:
                before = len(found)
                for p in rd.listing("/search", args.limit, q=q, sort=sort, t="all", type="link"):
                    if p["subreddit"].lower() in {s.lower() for s in subs} or RELEVANT.search(p["title"] + " " + p.get("selftext", "")):
                        found[p["id"]] = p
                log(f"site-wide '{q}' ({sort}): +{len(found) - before} (total {len(found)})")

    index = read_json(args.out / "index.json", {})
    for i, (pid, p) in enumerate(sorted(found.items(), key=lambda kv: kv[1]["created_utc"])):
        prev = index.get(pid)
        if prev and not args.refresh and prev.get("num_comments") == p.get("num_comments"):
            continue
        post, comments = rd.thread(pid)
        record = {k: post.get(k) for k in POST_FIELDS}
        record["comments"] = comments
        write_json(args.out / "posts" / f"{pid}.json", record)
        write_text(args.out / "posts" / f"{pid}.md", render_markdown(post, comments))
        if args.media:
            for n, url in enumerate(media_urls(post)):
                r = rd.s.get(url)
                if r.status_code == 200:
                    ext = re.search(r"\.(\w{3,4})(?:\?|$)", url)
                    path = args.out / "media" / f"{pid}_{n}.{ext.group(1) if ext else 'jpg'}"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(r.content)
        index[pid] = {"title": post["title"], "subreddit": post["subreddit"], "created": utc(post["created_utc"]),
                      "num_comments": p.get("num_comments"), "fetched_comments": len(comments), "url": post.get("url")}
        write_json(args.out / "index.json", index)
        log(f"  [{i + 1}/{len(found)}] {post['subreddit']}: {post['title'][:70]} ({len(comments)} comments)")
    log(f"done: {len(index)} threads in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
