#!/usr/bin/env python3
"""Full-text index over everything the collectors saved (SQLite FTS5, no server).

  python3 corpus_index.py build                 # (re)index corpus/**/*.md
  python3 corpus_index.py search "clan castle"  # ranked hits with snippets
  python3 corpus_index.py search "stone AND (combine OR fusion)" --source wiki
  python3 corpus_index.py stats

Queries use FTS5 syntax: AND / OR / NOT, "exact phrase", prefix*.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

from common import DEFAULT_OUT

FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def parse_md(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    meta, body = {}, raw
    m = FRONT.match(raw)
    if m:
        body = raw[m.end():]
        for line in m.group(1).splitlines():
            k, _, v = line.partition(": ")
            meta[k.strip()] = v.strip().strip('"')
    return {"source": meta.get("source", path.parts[-3] if len(path.parts) > 2 else ""),
            "title": meta.get("title", path.stem), "url": meta.get("url", ""),
            "date": meta.get("created") or meta.get("last_edit") or meta.get("published") or meta.get("fetched") or "",
            "path": str(path), "body": body}


def connect(db: Path) -> sqlite3.Connection:
    con = sqlite3.connect(db)
    con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5("
                "title, body, source UNINDEXED, url UNINDEXED, date UNINDEXED, path UNINDEXED, "
                "tokenize='unicode61 remove_diacritics 2')")
    return con


def build(corpus: Path, db: Path) -> None:
    con = connect(db)
    con.execute("DELETE FROM docs")
    n = 0
    for path in sorted(corpus.rglob("*.md")):
        if path.name in ("ATTRIBUTION.md",):
            continue
        d = parse_md(path)
        con.execute("INSERT INTO docs(title, body, source, url, date, path) VALUES (?,?,?,?,?,?)",
                    (d["title"], d["body"], d["source"], d["url"], d["date"], d["path"]))
        n += 1
    con.commit()
    print(f"indexed {n} documents into {db}")


def search(db: Path, query: str, source: str | None, limit: int) -> None:
    con = connect(db)
    sql = ("SELECT title, source, date, url, snippet(docs, 1, '[', ']', ' … ', 18) "
           "FROM docs WHERE docs MATCH ?" + (" AND source = ?" if source else "") + " ORDER BY bm25(docs, 5.0, 1.0) LIMIT ?")
    params = [query] + ([source] if source else []) + [limit]
    try:
        rows = con.execute(sql, params).fetchall()
    except sqlite3.OperationalError as e:
        raise SystemExit(f"bad query: {e} (quote phrases, e.g. '\"clan castle\"')")
    for title, src, date, url, snip in rows:
        print(f"\n[{src}] {title}  {date}\n  {url}\n  {snip.replace(chr(10), ' ')}")
    print(f"\n{len(rows)} hit(s)")


def stats(db: Path) -> None:
    con = connect(db)
    for src, n, chars in con.execute("SELECT source, count(*), sum(length(body)) FROM docs GROUP BY source ORDER BY 2 DESC"):
        print(f"{src:10} {n:6} docs {chars or 0:>12,} chars")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["build", "search", "stats"])
    ap.add_argument("query", nargs="?")
    ap.add_argument("--source", choices=["fandom", "reddit", "web", "play", "appstore", "review", "youtube"], help="limit search to one collector")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--corpus", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    db = args.corpus / "corpus.db"
    args.corpus.mkdir(parents=True, exist_ok=True)
    if args.command == "build":
        build(args.corpus, db)
    elif args.command == "stats":
        stats(db)
    else:
        if not args.query:
            ap.error("search needs a query")
        search(db, args.query, args.source, args.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
