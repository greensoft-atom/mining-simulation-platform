"""Shared helpers for the GrowStone research collectors.

Everything here is deliberately polite: one shared User-Agent that says who we
are, a minimum delay between requests per host, Retry-After / 429 handling,
robots.txt checks for ordinary web pages, and resumable on-disk output.
Only `requests` is needed beyond the standard library.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.robotparser
from html.parser import HTMLParser
from pathlib import Path

import requests

TOOLS_DIR = Path(__file__).resolve().parent
DEFAULT_OUT = TOOLS_DIR.parent / "corpus"

# Reddit and Fandom both ask for a descriptive User-Agent with a contact.
# Override with GS_RESEARCH_UA="<app>/<ver> (contact: you@example.com)".
USER_AGENT = os.environ.get(
    "GS_RESEARCH_UA",
    "deepforge-growstone-research/0.1 (personal game-design study; set GS_RESEARCH_UA to add a contact)",
)


class PoliteSession:
    """requests.Session with a per-host minimum interval and retry/backoff."""

    def __init__(self, min_interval: float = 1.0, timeout: float = 30.0, max_retries: int = 5):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT
        self.min_interval = min_interval
        self.timeout = timeout
        self.max_retries = max_retries
        self._last: dict[str, float] = {}

    def _wait(self, url: str) -> None:
        host = urllib.parse.urlsplit(url).netloc
        gap = time.monotonic() - self._last.get(host, 0.0)
        if gap < self.min_interval:
            time.sleep(self.min_interval - gap)
        self._last[host] = time.monotonic()

    def request(self, method: str, url: str, **kw) -> requests.Response:
        kw.setdefault("timeout", self.timeout)
        delay = 2.0
        for attempt in range(self.max_retries + 1):
            self._wait(url)
            try:
                r = self.s.request(method, url, **kw)
            except requests.RequestException as e:
                if attempt == self.max_retries:
                    raise
                log(f"  network error ({e.__class__.__name__}); retry in {delay:.0f}s")
                time.sleep(delay); delay *= 2
                continue
            if r.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                wait = float(r.headers.get("Retry-After") or delay)
                log(f"  HTTP {r.status_code}; retry in {wait:.0f}s")
                time.sleep(wait); delay *= 2
                continue
            return r
        return r  # unreachable

    def get(self, url: str, **kw) -> requests.Response:
        return self.request("GET", url, **kw)

    def post(self, url: str, **kw) -> requests.Response:
        return self.request("POST", url, **kw)


class Robots:
    """Caches robots.txt per host. Unreachable robots.txt means 'allowed', as the RFC says."""

    def __init__(self, session: PoliteSession):
        self.session = session
        self.cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def allowed(self, url: str) -> bool:
        parts = urllib.parse.urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self.cache:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.session.get(base + "/robots.txt")
                if r.status_code >= 400:
                    self.cache[base] = None
                else:
                    rp.parse(r.text.splitlines())
                    self.cache[base] = rp
            except requests.RequestException:
                self.cache[base] = None
        rp = self.cache[base]
        return True if rp is None else rp.can_fetch(USER_AGENT, url)


def log(msg: str) -> None:
    print(msg, flush=True)


def slug(text: str, max_len: int = 80) -> str:
    s = re.sub(r"[^\w\-]+", "_", text, flags=re.UNICODE).strip("_")
    if len(s) > max_len:
        s = s[:max_len] + "_" + hashlib.sha1(text.encode()).hexdigest()[:8]
    return s or hashlib.sha1(text.encode()).hexdigest()[:12]


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class _TextExtractor(HTMLParser):
    """Readable text from HTML without third-party parsers.

    Skips script/style/nav/header/footer/aside/form, keeps block structure,
    and turns headings into Markdown '#' lines and list items into '- '.
    """

    SKIP = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "iframe", "button"}
    BLOCK = {"p", "div", "section", "article", "main", "br", "tr", "table", "ul", "ol", "blockquote", "pre", "figure", "dd", "dt"}

    def __init__(self, skip: set[str] | None = None):
        super().__init__(convert_charrefs=True)
        self.SKIP = self.SKIP if skip is None else skip
        self.out: list[str] = []
        self.skip = 0
        self.title = ""
        self._in_title = False
        self._pre = 0

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            self._pre += 1
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "title":
            self._in_title = True
        elif not self.skip:
            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                self.out.append("\n\n" + "#" * int(tag[1]) + " ")
            elif tag == "li":
                self.out.append("\n- ")
            elif tag in ("td", "th"):
                self.out.append(" | ")
            elif tag in self.BLOCK:
                self.out.append("\n")
            elif tag == "img":
                alt = dict(attrs).get("alt")
                if alt:
                    self.out.append(f"[image: {alt}]")
            a = dict(attrs)
            if a.get("role") == "img" and a.get("aria-label"):
                self.out.append(f"[{a['aria-label']}]\n")  # e.g. star ratings drawn as icons

    def handle_endtag(self, tag):
        if tag == "pre":
            self._pre = max(0, self._pre - 1)
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag == "title":
            self._in_title = False
        elif not self.skip and (tag in self.BLOCK or tag.startswith("h")):
            self.out.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.skip:
            # HTML collapses source whitespace (including newlines) except inside <pre>.
            self.out.append(data if self._pre else re.sub(r"\s+", " ", data))


def html_to_text(html: str, keep: set[str] = frozenset()) -> tuple[str, str]:
    """Returns (title, text). `keep` re-enables tags skipped by default (e.g. {"header"})."""
    p = _TextExtractor(_TextExtractor.SKIP - set(keep))
    p.feed(html)
    text = "".join(p.out)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return p.title.strip(), text


def front_matter(meta: dict) -> str:
    """Small YAML-ish header so every saved .md says where it came from."""
    lines = ["---"]
    for k, v in meta.items():
        if v is None:
            continue
        v = str(v).replace("\n", " ")
        lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    lines.append("---\n")
    return "\n".join(lines)
