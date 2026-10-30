#!/usr/bin/env python3
"""Collect GrowStone discussions from Reddit: the dedicated subreddits in full,
plus posts and comments that mention the game anywhere on Reddit.

Sources (no key needed for the default setup):

  Arctic Shift  (default for subreddit history and comment trees)
                https://github.com/ArthurHeitmann/arctic_shift
                The community archive built for researchers and moderators
                (the successor to Pushshift). Complete subreddit history and full
                comment trees. Text search must be scoped to one subreddit.
                Indexing lag of up to about two days.

  PullPush      (default for site-wide mention search, and fallback)
                https://pullpush.io  - a Pushshift-compatible archive API.
                Searches post titles, post text and comments across all of
                Reddit; also used when Arctic Shift lacks a subreddit or thread.
                Volunteer-run, roughly 30 requests/min, sometimes offline.

  Official API  (optional) Reddit's own Data API, OAuth app-only. Since November
                2025 keys are not self-service: apply through Reddit Developer
                Support (Responsible Builder Policy). With approved
                REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET it is used automatically
                and adds live data.

Not used: Reddit's own .json/.rss endpoints and HTML pages, directly or through
browser automation, TLS impersonation, rotating proxies or Redlib/Libreddit
mirrors. Reddit's robots.txt disallows all automated access ("Disallow: /")
and .json answers 403 without OAuth since May 2026; working around that is
evading an access control. Tools that do so are listed in the README.

"Growstone" is also a place in Hollow Knight: Silksong and a hydroponics
substrate brand, so mentions outside the dedicated subreddits must also show
game context (see is_game_mention) to be kept.

Reddit content belongs to its authors: keep it private, don't republish.

Examples:
  python3 reddit.py                       # r/GrowStone + r/GrowStone_Online + mentions
  python3 reddit.py --media               # also download images in posts
  python3 reddit.py --limit 25            # quick test
  python3 reddit.py --no-mentions         # dedicated subreddits only
  python3 reddit.py --backend official    # with approved OAuth credentials
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

RELEVANT = re.compile(r"grow\s*stone|돌\s*키우기", re.I)
DEDICATED_SUBS = ["GrowStone", "GrowStone_Online"]
NOISE_STREAK = 500  # stop a mention search after this many consecutive unrelated hits
MENTION_TERMS = ["growstone", "grow stone online"]
# Evidence that a "growstone" mention is about the game, not Silksong's Growstone or hydroponic growstones.
GAME_CONTEXT = re.compile(r"grow\s*stone\s*online|supercat|돌\s*키우기|mmorpg|pixel\s*(mmo|rpg)|idle\s*rpg|stone\s*token|"
                          r"rubies|clan\s*castle|\bpvp\b|google\s*play|play\s*store|bluestacks|solar\s*stone|phoenix\s*stone",
                          re.I)
GAME_SUBREDDIT = re.compile(r"gam(e|es|ing)|mmo|rpg|idle|incremental|android|mobile|ios", re.I)


def is_game_mention(text: str, subreddit: str) -> bool:
    if subreddit.lower() in {s.lower() for s in DEDICATED_SUBS}:
        return True
    if not RELEVANT.search(text or ""):
        return False
    return bool(GAME_CONTEXT.search(text) or GAME_SUBREDDIT.search(subreddit))
POST_FIELDS = ["id", "name", "subreddit", "title", "author", "created_utc", "score", "upvote_ratio",
               "num_comments", "link_flair_text", "permalink", "url", "domain", "is_self", "selftext",
               "over_18", "edited", "post_hint"]


class ArcticShift:
    name = "arctic"
    base = "https://arctic-shift.photon-reddit.com/api"
    supports_sitewide = False

    def __init__(self):
        self.s = PoliteSession(min_interval=1.0)

    def get(self, path: str, **params) -> list:
        params = {k: v for k, v in params.items() if v is not None}
        for wait in (20, 60, 180, None):
            r = self.s.get(self.base + path, params=params)
            try:
                data = r.json()
            except ValueError:
                r.raise_for_status()
                raise
            error = data.get("error")
            if error and "timeout" in error.lower() and wait:
                # Expensive full-text queries time out under load; the service asks callers to slow down.
                log(f"  Arctic Shift busy ({error}); waiting {wait}s")
                time.sleep(wait)
                continue
            if error:
                raise RuntimeError(f"Arctic Shift: {error}")
            r.raise_for_status()
            return data.get("data") or []
        raise RuntimeError("Arctic Shift: still timing out; try again later")

    def _paged(self, path: str, limit: int | None, after=None, before=None, **params):
        n = 0
        while True:
            batch = self.get(path, limit=100, sort="asc", after=after, before=before, **params)
            for item in batch:
                yield item
                n += 1
                if limit and n >= limit:
                    return
            if len(batch) < 100:
                return
            after = int(batch[-1]["created_utc"]) + 1  # strictly after the last item seen

    def subreddit_posts(self, sub: str, limit: int | None):
        yield from self._paged("/posts/search", limit, subreddit=sub)

    def thread(self, post: dict) -> tuple[dict, list[dict]]:
        children = self.get("/comments/tree", link_id=post["id"], limit=25000)
        comments: list[dict] = []
        pending: list[str] = []
        flatten(children, comments, pending)
        while pending:  # comments collapsed beyond the tree limit
            batch, pending = pending[:500], pending[500:]
            flatten([{"kind": "t1", "data": c} for c in self.get("/comments/ids", ids=",".join(batch))], comments, [])
        return post, comments

    def about(self, sub: str) -> dict:
        found = self.get("/subreddits/search", subreddit=sub, limit=1)
        return found[0] if found else {}


class PullPush:
    """Pushshift-compatible archive: site-wide search, plus a fallback for listings and threads."""
    name = "pullpush"
    base = "https://api.pullpush.io/reddit/search"
    supports_sitewide = True

    def __init__(self):
        self.s = PoliteSession(min_interval=4.0)  # well under its ~30 requests/min limit; it 429s bursts

    def get(self, kind: str, **params) -> list:
        params = {k: v for k, v in params.items() if v is not None}
        for wait in (30, 90, 300, None):
            r = self.s.get(f"{self.base}/{kind}/", params=params)
            if r.status_code == 429:
                # PoliteSession already backed off; an empty answer here would look like "no results".
                raise RuntimeError("PullPush is rate-limiting this IP (HTTP 429); re-run later, it is incremental")
            try:
                r.raise_for_status()
                return r.json().get("data") or []
            except ValueError:  # HTML maintenance or challenge page instead of JSON
                if not wait:
                    raise RuntimeError(f"PullPush unavailable (HTTP {r.status_code})")
                log(f"  PullPush unavailable (HTTP {r.status_code}); waiting {wait}s")
                time.sleep(wait)
        return []

    def _paged(self, kind: str, limit: int | None, **params):
        after, n = None, 0
        while True:
            batch = self.get(kind, size=100, sort="asc", sort_type="created_utc", after=after, **params)
            for item in batch:
                yield item
                n += 1
                if limit and n >= limit:
                    return
            if len(batch) < 100:
                return
            after = int(float(batch[-1]["created_utc"]))

    def subreddit_posts(self, sub: str, limit: int | None):
        yield from self._paged("submission", limit, subreddit=sub)

    def search_posts(self, sub: str | None, term: str, limit: int | None):
        seen = set()
        for field in ("title", "selftext"):  # field searches are precise; free-text q= is fuzzy
            for p in self._paged("submission", limit, subreddit=sub, **{field: term}):
                if p["id"] not in seen:
                    seen.add(p["id"])
                    yield p

    def search_comments(self, sub: str | None, term: str, limit: int | None):
        yield from self._paged("comment", limit, subreddit=sub, q=term)

    def thread(self, post: dict) -> tuple[dict, list[dict]]:
        comments = [{k: c.get(k) for k in ("id", "parent_id", "author", "body", "score", "created_utc", "depth", "edited")}
                    for c in self._paged("comment", None, link_id=post["id"])]
        return post, comments

    def about(self, sub: str) -> dict:
        return {}


class OfficialAPI:
    name = "official"
    base = "https://oauth.reddit.com"
    supports_sitewide = True
    SUB_LISTINGS = [("new", {}), ("hot", {}), ("top", {"t": "all"}), ("top", {"t": "year"}),
                    ("top", {"t": "month"}), ("controversial", {"t": "all"})]

    def __init__(self):
        self._cid, self._secret = os.environ.get("REDDIT_CLIENT_ID"), os.environ.get("REDDIT_CLIENT_SECRET")
        if not (self._cid and self._secret):
            raise SystemExit("official backend needs REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET (approved access)")
        self.s = PoliteSession(min_interval=0.7)  # Reddit allows 100 queries/min for OAuth clients
        self.token_expiry = 0.0

    def get(self, path: str, **params):
        if time.time() > self.token_expiry - 60:
            r = self.s.post("https://www.reddit.com/api/v1/access_token",
                            auth=(self._cid, self._secret), data={"grant_type": "client_credentials"})
            r.raise_for_status()
            tok = r.json()
            self.s.s.headers["Authorization"] = f"bearer {tok['access_token']}"
            self.token_expiry = time.time() + tok.get("expires_in", 3600)
        params.setdefault("raw_json", 1)
        r = self.s.get(self.base + path, params=params)
        remaining, reset = r.headers.get("X-Ratelimit-Remaining"), r.headers.get("X-Ratelimit-Reset")
        if remaining and reset and float(remaining) < 2:
            time.sleep(float(reset) + 1)
        r.raise_for_status()
        return r.json()

    def _listing(self, path: str, limit: int | None, **params):
        after, n = None, 0
        while True:
            data = self.get(path, limit=100, after=after, **params)["data"]
            for child in data["children"]:
                if child["kind"] in ("t3", "t1"):
                    yield child["data"]
                    n += 1
                    if limit and n >= limit:
                        return
            after = data.get("after")
            if not after:
                return

    def subreddit_posts(self, sub: str, limit: int | None):
        # A listing stops at ~1,000 items, so merge several orderings.
        for kind, params in self.SUB_LISTINGS:
            yield from self._listing(f"/r/{sub}/{kind}", limit, **params)

    def search_posts(self, sub: str | None, term: str, limit: int | None):
        path = f"/r/{sub}/search" if sub else "/search"
        for sort in ("new", "top", "relevance", "comments"):
            yield from self._listing(path, limit, q=term, restrict_sr=1 if sub else 0, sort=sort, t="all", type="link")

    def search_comments(self, sub: str, term: str, limit: int | None):
        return iter(())  # the official API has no comment search

    def thread(self, post: dict) -> tuple[dict, list[dict]]:
        post_listing, comment_listing = self.get(f"/comments/{post['id']}", limit=500, depth=50, sort="top")
        fresh = post_listing["data"]["children"][0]["data"]
        comments: list[dict] = []
        pending: list[str] = []
        flatten(comment_listing["data"]["children"], comments, pending)
        while pending:
            batch, pending = pending[:100], pending[100:]
            data = self.get("/api/morechildren", link_id=f"t3_{post['id']}", children=",".join(batch),
                            api_type="json", sort="top")
            flatten(data.get("json", {}).get("data", {}).get("things", []), comments, pending)
        return fresh, comments

    def about(self, sub: str) -> dict:
        return self.get(f"/r/{sub}/about")["data"]


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
        urls.append(re.sub(r"\.gifv$", ".mp4", post["url"]))  # imgur .gifv is a player page; the clip is .mp4
    return urls


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", choices=["auto", "arctic", "official"], default="auto",
                    help="auto = official if REDDIT_CLIENT_ID is set, else arctic")
    ap.add_argument("--subreddit", action="append", help=f"dedicated subreddit(s) to mirror fully (default: {', '.join(DEDICATED_SUBS)})")
    ap.add_argument("--no-mentions", action="store_true", help="skip the site-wide mention search")
    ap.add_argument("--media", action="store_true", help="download images and galleries attached to posts")
    ap.add_argument("--limit", type=int, help="max posts per query, for a quick test")
    ap.add_argument("--refresh", action="store_true", help="re-fetch every thread even if unchanged")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT / "reddit")
    args = ap.parse_args(argv)

    use_official = args.backend == "official" or (args.backend == "auto" and os.environ.get("REDDIT_CLIENT_ID"))
    rd = OfficialAPI() if use_official else ArcticShift()
    log(f"Reddit backend: {rd.name}")
    pp = PullPush()
    subs = args.subreddit or DEDICATED_SUBS
    found: dict[str, dict] = {}

    for sub in subs:
        try:
            write_json(args.out / f"about_{sub}.json", rd.about(sub))
        except Exception as e:  # noqa: BLE001
            log(f"r/{sub}: about failed ({e})")
        before = len(found)
        for p in rd.subreddit_posts(sub, args.limit):
            found[p["id"]] = p
        if len(found) == before and rd.name == "arctic":
            log(f"r/{sub}: not in Arctic Shift; trying PullPush")
            try:
                for p in pp.subreddit_posts(sub, args.limit):
                    found[p["id"]] = p
            except Exception as e:  # noqa: BLE001 - archive outage: keep going, re-run later
                log(f"r/{sub}: PullPush failed ({e})")
        log(f"r/{sub}: {len(found) - before} posts")

    mentions: dict[str, dict] = read_json(args.out / "mentions.json", {}) or {}
    if not args.no_mentions:
        finder = rd if rd.name == "official" else pp
        dedicated = {s.lower() for s in subs}
        for term in MENTION_TERMS:
            try:
                before, hits, dropped = len(found), 0, 0
                streak = 0  # unrelated hits since the last kept one
                for p in finder.search_posts(None, term, args.limit):
                    if is_game_mention(p.get("title", "") + " " + (p.get("selftext") or ""), p["subreddit"]):
                        found[p["id"]] = p
                        streak = 0
                    else:
                        dropped += 1
                        streak += 1
                        if streak >= NOISE_STREAK:
                            break  # the rest of this search is someone else's "growstone"
                streak = 0
                for c in finder.search_comments(None, term, args.limit):
                    if c["subreddit"].lower() not in dedicated and is_game_mention(c.get("body") or "", c["subreddit"]):
                        mentions[c["id"]] = {k: c.get(k) for k in ("id", "subreddit", "author", "body", "score",
                                                                   "link_id", "permalink")}
                        mentions[c["id"]]["created_utc"] = int(float(c.get("created_utc") or 0))
                        hits += 1
                        streak = 0
                    else:
                        dropped += 1
                        streak += 1
                        if streak >= NOISE_STREAK:
                            break
                log(f"site-wide '{term}' via {finder.name}: +{len(found) - before} posts, {hits} comments "
                    f"({dropped} unrelated hits dropped: Silksong, hydroponics, ...)")
            except Exception as e:  # noqa: BLE001 - an archive outage should not stop the run
                log(f"site-wide '{term}': failed ({e})")
        write_json(args.out / "mentions.json", mentions)
        if mentions:
            lines = [front_matter({"source": "reddit", "title": "GrowStone mentions in other subreddits (comments)", "url": ""}),
                     "# GrowStone mentions in comments", ""]
            for c in sorted(mentions.values(), key=lambda c: float(c.get("created_utc") or 0), reverse=True):
                link = f"https://www.reddit.com{c['permalink']}" if c.get("permalink") else ""
                lines += [f"## r/{c['subreddit']} · u/{c['author']} · {utc(c['created_utc'])} · score {c['score']}", link, "",
                          (c.get("body") or "").strip(), ""]
            write_text(args.out / "mentions.md", "\n".join(lines))

    index = read_json(args.out / "index.json", {})
    for i, (pid, p) in enumerate(sorted(found.items(), key=lambda kv: kv[1]["created_utc"])):
        prev = index.get(pid)
        if prev and not args.refresh and prev.get("num_comments") == p.get("num_comments"):
            continue
        post, comments, source = *rd.thread(p), rd.name
        if not comments and p.get("num_comments") and rd.name == "arctic":
            post, comments, source = *pp.thread(p), pp.name  # thread missing from Arctic Shift
        record = {k: post.get(k) for k in POST_FIELDS}
        record["comments"] = comments
        record["backend"] = source
        write_json(args.out / "posts" / f"{pid}.json", record)
        write_text(args.out / "posts" / f"{pid}.md", render_markdown(post, comments))
        if args.media:
            for n, url in enumerate(media_urls(post)):
                try:
                    r = rd.s.get(url)
                except Exception as e:  # noqa: BLE001 - old image hosts die; the thread text still counts
                    log(f"  media skipped ({url}: {e.__class__.__name__})")
                    continue
                if r.status_code == 200:
                    ext = re.search(r"\.(\w{3,4})(?:\?|$)", url)
                    path = args.out / "media" / f"{pid}_{n}.{ext.group(1) if ext else 'jpg'}"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(r.content)
        index[pid] = {"title": post["title"], "subreddit": post["subreddit"], "created": utc(post["created_utc"]),
                      "num_comments": p.get("num_comments"), "fetched_comments": len(comments), "url": post.get("url")}
        write_json(args.out / "index.json", index)
        log(f"  [{i + 1}/{len(found)}] r/{post['subreddit']}: {post['title'][:70]} ({len(comments)} comments)")
    log(f"done: {len(index)} threads, {len(mentions)} comment mentions in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
