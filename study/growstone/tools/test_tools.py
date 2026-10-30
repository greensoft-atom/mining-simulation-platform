#!/usr/bin/env python3
"""Offline tests for the collectors' parsing logic (no network, no credentials).

  python3 -m unittest test_tools -v
"""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import corpus_index
import import_reviews
import play_store
import reddit
import web_pages
from common import html_to_text


class HtmlToText(unittest.TestCase):
    def test_collapses_source_newlines_and_keeps_structure(self):
        title, text = html_to_text("<title>T</title><nav>menu</nav><p>Bid Time: Every\nThursday</p>"
                                   "<ul><li>a</li><li>b</li></ul><h2>Head</h2><script>x()</script>")
        self.assertEqual(title, "T")
        self.assertIn("Bid Time: Every Thursday", text)
        self.assertIn("- a\n- b", text)
        self.assertIn("## Head", text)
        self.assertNotIn("menu", text)
        self.assertNotIn("x()", text)

    def test_keep_header_and_aria_ratings(self):
        _, text = html_to_text('<header>Jane</header><div role="img" aria-label="Rated 4 stars out of five stars"></div>',
                               keep={"header"})
        self.assertIn("Jane", text)
        self.assertIn("[Rated 4 stars out of five stars]", text)


PLAY_EN = """## Ratings and reviews
4.0
90.6K reviews
Ragged Vagabond
- Flag inappropriate
[Rated 1 stars out of five stars]
May 18, 2021
The menus are overcomplicated.
72 people found this review helpful
SUPERCAT
June 7, 2021
Greetings, this is Grow Stone team.
A Google user
- Flag inappropriate
- Show review history
[Rated 2 stars out of five stars]
October 9, 2018
I died and couldn't do anything.
22 people found this review helpful
## What's new
■ Revamped Field and Clan Raids
■ Bug fixes
flag Flag as inappropriate
"""

PLAY_KO = """Google 사용자
- 부적절한 리뷰로 신고
[별표 5개 만점에 4개를 받았습니다.]
2019년 5월 4일
'돌의 징표'를 얻기까지가 시간이 너무걸리며
사용자 23명이 이 리뷰가 유용하다고 평가함
## 새로운 기능
■ 버그 수정
"""


class PlayParser(unittest.TestCase):
    def test_english_reviews_replies_and_whats_new(self):
        reviews, whats_new = play_store.parse_reviews(PLAY_EN)
        self.assertEqual(len(reviews), 2)
        first, second = reviews
        self.assertEqual((first["author"], first["date"], first["rating"]), ("Ragged Vagabond", "May 18, 2021", 1))
        self.assertEqual(first["text"], "The menus are overcomplicated.")
        self.assertEqual(first["helpful"], "72 people found this review helpful")
        self.assertEqual(first["developer_reply_date"], "June 7, 2021")
        self.assertEqual(first["developer_reply"], "Greetings, this is Grow Stone team.")
        self.assertEqual((second["author"], second["rating"], second["developer_reply"]), ("A Google user", 2, None))
        self.assertEqual(whats_new, "■ Revamped Field and Clan Raids\n■ Bug fixes")

    def test_korean_star_label_puts_scale_first(self):
        reviews, whats_new = play_store.parse_reviews(PLAY_KO)
        self.assertEqual(reviews[0]["rating"], 4)
        self.assertIn("돌의 징표", reviews[0]["text"])
        self.assertEqual(whats_new, "■ 버그 수정")


THREAD = [
    {"data": {"children": [{"kind": "t3", "data": {"id": "p1", "subreddit": "GrowStone", "title": "Best stone?",
                                                    "author": "op", "created_utc": 1700000000, "score": 5,
                                                    "num_comments": 3, "permalink": "/r/GrowStone/comments/p1/x/",
                                                    "is_self": True, "selftext": "Which stone first?"}}]}},
    {"data": {"children": [
        {"kind": "t1", "data": {"id": "c1", "parent_id": "t3_p1", "author": "a", "body": "Phoenix", "score": 3,
                                "created_utc": 1700000100, "depth": 0,
                                "replies": {"data": {"children": [
                                    {"kind": "t1", "data": {"id": "c2", "parent_id": "t1_c1", "author": "b",
                                                            "body": "Agreed", "score": 1, "created_utc": 1700000200,
                                                            "depth": 1, "replies": ""}},
                                    {"kind": "more", "data": {"children": ["c3", "c4"]}}]}}}},
    ]}},
]


class RedditParser(unittest.TestCase):
    def test_flatten_collects_comments_and_more_stubs(self):
        out, pending = [], []
        reddit.flatten(THREAD[1]["data"]["children"], out, pending)
        self.assertEqual([c["id"] for c in out], ["c1", "c2"])
        self.assertEqual(pending, ["c3", "c4"])

    def test_markdown_nests_replies(self):
        out, pending = [], []
        reddit.flatten(THREAD[1]["data"]["children"], out, pending)
        md = reddit.render_markdown(THREAD[0]["data"]["children"][0]["data"], out)
        self.assertIn("# Best stone?", md)
        self.assertIn("- **u/a** (3", md)
        self.assertIn("> - **u/b** (1", md)

    def test_media_urls(self):
        self.assertEqual(reddit.media_urls({"url": "https://i.redd.it/x.png", "domain": "i.redd.it"}), ["https://i.redd.it/x.png"])
        self.assertEqual(reddit.media_urls({"url": "https://example.com/page", "domain": "example.com"}), [])


class WebFilter(unittest.TestCase):
    def test_denied_sites_and_files(self):
        self.assertFalse(web_pages.allowed_host("https://play.google.com/store/apps/details?id=x"))
        self.assertFalse(web_pages.allowed_host("https://www.facebook.com/GrowStoneGlob/"))
        self.assertFalse(web_pages.allowed_host("https://growstoneonline.fandom.com/wiki/X"))
        self.assertFalse(web_pages.allowed_host("https://example.com/a.png"))
        self.assertTrue(web_pages.allowed_host("https://mmohuts.com/review/grow-stone-online"))


class ImportAndIndex(unittest.TestCase):
    def test_import_txt_and_csv_then_search(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "notes.txt").write_text("rating: 2\ndate: 2026-05-01\nlang: en\nToo much grind after level 80.\n---\n"
                                         "rating: 5\nLove the stone fusion.\n", encoding="utf-8")
            (d / "export.csv").write_text("Review Text,Stars,Date\n\"Market has no buyers\",1,2026-06-02\n", encoding="utf-8")
            corpus = d / "corpus"
            with contextlib.redirect_stdout(io.StringIO()):
                import_reviews.main([str(d / "notes.txt"), str(d / "export.csv"), "--source", "t", "--out", str(corpus / "reviews")])
                import_reviews.main([str(d / "notes.txt"), "--source", "t", "--out", str(corpus / "reviews")])  # re-run: no dupes
            lines = (corpus / "reviews" / "t" / "reviews.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 3)
            self.assertEqual(json.loads(lines[2])["rating"], "1")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                corpus_index.main(["build", "--corpus", str(corpus)])
                corpus_index.main(["search", "grind", "--corpus", str(corpus)])
            self.assertIn("Too much [grind]", buf.getvalue())
            self.assertIn("1 hit(s)", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
