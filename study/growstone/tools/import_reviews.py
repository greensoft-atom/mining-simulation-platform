#!/usr/bin/env python3
"""Load app reviews you collected yourself into the corpus.

Use this for reviews that can't be scraped (the full Google Play feed): paste
the useful ones into a file while reading the store, or export them from a
licensed review-data service (AppFollow, AppTweak, Appbot, data.ai) and import
the export unchanged.

Accepted inputs:
  * .csv / .tsv   any column names; common ones are detected automatically
  * .json / .jsonl  a list of objects, or one object per line
  * .txt          reviews separated by a line '---'; optional header lines
                  'rating: 4', 'date: 2026-05-01', 'lang: ko', 'author: x'

Examples:
  python3 import_reviews.py my_notes.txt --source manual
  python3 import_reviews.py appfollow_export.csv --source appfollow
  python3 import_reviews.py export.csv --map text=Review_Body --map rating=Stars
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

from common import DEFAULT_OUT, front_matter, log, write_text

FIELDS = {
    "text": ["text", "content", "review", "body", "comment", "review text", "review_text", "message"],
    "rating": ["rating", "score", "stars", "star", "star rating"],
    "date": ["date", "at", "created", "created_at", "review date", "timestamp", "time", "updated"],
    "author": ["author", "user", "username", "user name", "username", "reviewer", "name"],
    "lang": ["lang", "language", "locale", "reviewer language"],
    "country": ["country", "region", "store"],
    "version": ["version", "app version", "reviewcreatedversion", "app_version"],
    "helpful": ["thumbsupcount", "thumbs up", "helpful", "likes", "upvotes"],
    "reply": ["reply", "replycontent", "developer reply", "developer_reply", "response", "answer"],
    "reply_date": ["repliedat", "reply date", "developer reply date", "replied_at"],
    "title": ["title", "subject"],
}


def detect(columns: list[str], overrides: dict[str, str]) -> dict[str, str]:
    norm = {c.lower().strip().replace("-", " "): c for c in columns}
    mapping = {}
    for field, names in FIELDS.items():
        if field in overrides:
            mapping[field] = overrides[field]
            continue
        for n in names:
            if n in norm:
                mapping[field] = norm[n]
                break
    if "text" not in mapping:
        raise SystemExit(f"no review-text column found in {columns}; use --map text=<column>")
    return mapping


def rows_from(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    if path.suffix.lower() in (".csv", ".tsv"):
        dialect = csv.Sniffer().sniff(raw[:4096], delimiters=",\t;") if path.suffix.lower() == ".csv" else csv.excel_tab
        return list(csv.DictReader(raw.splitlines(), dialect=dialect))
    if path.suffix.lower() == ".jsonl":
        return [json.loads(l) for l in raw.splitlines() if l.strip()]
    if path.suffix.lower() == ".json":
        data = json.loads(raw)
        return data if isinstance(data, list) else data.get("reviews", [])
    rows = []
    for block in re.split(r"^\s*---\s*$", raw, flags=re.M):
        meta, body = {}, []
        for line in block.strip().splitlines():
            m = re.match(r"^(rating|date|lang|author|country|version|reply)\s*:\s*(.*)$", line, re.I)
            if m and not body:
                meta[m.group(1).lower()] = m.group(2).strip()
            else:
                body.append(line)
        if "".join(body).strip():
            rows.append({**meta, "text": "\n".join(body).strip()})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--source", default="manual", help="label for where these reviews came from")
    ap.add_argument("--map", action="append", default=[], help="field=column override, e.g. text=Body")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT / "reviews")
    args = ap.parse_args(argv)
    overrides = dict(m.split("=", 1) for m in args.map)

    out = args.out / args.source
    out.mkdir(parents=True, exist_ok=True)
    jsonl = out / "reviews.jsonl"
    known = {json.loads(l)["id"] for l in jsonl.read_text(encoding="utf-8").splitlines() if l.strip()} if jsonl.exists() else set()
    stars, years, langs = collections.Counter(), collections.Counter(), collections.Counter()
    n = 0
    with jsonl.open("a", encoding="utf-8") as jl:
        for f in args.files:
            rows = rows_from(f)
            if not rows:
                log(f"{f}: no reviews found")
                continue
            mapping = detect(list(rows[0].keys()), overrides)
            for row in rows:
                rec = {field: (str(row.get(col)).strip() if row.get(col) not in (None, "") else None)
                       for field, col in mapping.items()}
                if not rec.get("text"):
                    continue
                rid = hashlib.sha1(f"{rec.get('author')}|{rec.get('date')}|{rec['text']}".encode()).hexdigest()[:12]
                if rid in known:
                    continue
                known.add(rid)
                meta ={"source": "review", "origin": args.source, "title": (rec.get("title") or rec["text"][:60]),
                        "url": "", "created": rec.get("date"), "rating": rec.get("rating"),
                        "lang": rec.get("lang"), "country": rec.get("country"), "version": rec.get("version"),
                        "author": rec.get("author")}
                md = [front_matter(meta), rec["text"], ""]
                if rec.get("reply"):
                    md += [f"> **Developer reply ({rec.get('reply_date') or ''}):** {rec['reply']}", ""]
                write_text(out / f"{rid}.md", "\n".join(md))
                jl.write(json.dumps({"id": rid, **rec}, ensure_ascii=False) + "\n")
                stars[rec.get("rating") or "?"] += 1
                years[(re.search(r"(19|20)\d\d", rec.get("date") or "") or [None])[0] or "?"] += 1
                langs[rec.get("lang") or "?"] += 1
                n += 1
            log(f"{f}: {len(rows)} rows, mapped {mapping}")
    log(f"imported {n} reviews into {out}")
    log("by rating: " + ", ".join(f"{k}: {v}" for k, v in sorted(stars.items())))
    log("by year:   " + ", ".join(f"{k}: {v}" for k, v in sorted(years.items())))
    log("by lang:   " + ", ".join(f"{k}: {v}" for k, v in langs.most_common(10)))
    log("Run 'python3 corpus_index.py build' to make them searchable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
