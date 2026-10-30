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

import capture
import corpus_index
import import_reviews
import media
import play_store
import reddit
import web_pages
import youtube_index
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


class ArcticAndYoutube(unittest.TestCase):
    def test_game_mention_filter(self):
        self.assertTrue(reddit.is_game_mention("anything at all", "GrowStone_Online"))
        self.assertTrue(reddit.is_game_mention("Anyone still playing Growstone? The pvp is rough", "MobileGaming"))
        self.assertTrue(reddit.is_game_mention("growstone online by supercat", "Korea"))
        self.assertFalse(reddit.is_game_mention("Where is the Growstone bench in Silksong?", "Silksong"))
        self.assertFalse(reddit.is_game_mention("I switched my anthurium to growstones", "Anthurium"))
        self.assertFalse(reddit.is_game_mention("no mention here", "MMORPG"))

    def test_arctic_tree_is_reddit_shaped(self):
        # Arctic Shift's /comments/tree returns the same t1/replies structure as Reddit.
        out, pending = [], []
        reddit.flatten(THREAD[1]["data"]["children"], out, pending)
        self.assertEqual(len(out), 2)

    def test_video_id_extraction(self):
        text = ("see https://www.youtube.com/watch?v=dQw4w9WgXcQ and https://youtu.be/abcdefghijk, "
                "https://www.youtube.com/watch?feature=share&amp;v=ZZZZZZZZZZZ, https://www.youtube.com/embed/AAAAAAAAAAA, "
                "https://youtube.com/shorts/BBBBBBBBBBB but not https://www.youtube.com/channel/UCxxxxxxxxxxxx")
        self.assertEqual(youtube_index.VIDEO_ID.findall(text),
                         ["dQw4w9WgXcQ", "abcdefghijk", "ZZZZZZZZZZZ", "AAAAAAAAAAA", "BBBBBBBBBBB"])


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


PLAY_NOW = ('<img src="https://play-lh.googleusercontent.com/ICON=w240-h480" alt="Icon image" itemprop="image">'
            '<img src="https://play-lh.googleusercontent.com/AAA=w526-h296" alt="x" itemprop="image" data-screenshot-index="0">'
            '<img src="https://play-lh.googleusercontent.com/BBB=w526-h296" alt="x" itemprop="image" data-screenshot-index="1">'
            '<img src="https://play-lh.googleusercontent.com/AAA=w526-h296" alt="x" itemprop="image" data-screenshot-index="2">')
PLAY_2018 = ('<img src="https://lh3.googleusercontent.com/ICON=s180" alt="電影海報圖片" itemprop="image">'
             '<img src="https://lh3.googleusercontent.com/OLD1=w720-h310" alt="螢幕擷取畫面圖片" itemprop="image">'
             '<img src="https://lh3.googleusercontent.com/SIMILAR=s128" alt="">')
MPD = ('<MPD><Period><AdaptationSet><Representation bandwidth="590258" id="1"><BaseURL>DASH_600_K</BaseURL></Representation>'
       '<Representation bandwidth="4364918" id="2"><BaseURL>DASH_4_8_M</BaseURL></Representation></AdaptationSet>'
       '<AdaptationSet><Representation bandwidth="129820" id="5"><BaseURL>audio</BaseURL></Representation></AdaptationSet></Period></MPD>')


class Media(unittest.TestCase):
    def test_play_screenshots_current_and_2018_layouts(self):
        host = "play-lh.googleusercontent.com"
        self.assertEqual(media.play_screenshots(PLAY_NOW), [(host, "AAA"), (host, "BBB")])
        self.assertEqual(media.play_screenshots(PLAY_2018), [("lh3.googleusercontent.com", "OLD1")])

    def test_appstore_full_size(self):
        self.assertEqual(media.appstore_full("https://is1-ssl.mzstatic.com/image/thumb/a/pr_source.jpg/392x696bb.jpg", 0),
                         "https://is1-ssl.mzstatic.com/image/thumb/a/pr_source.jpg/9999x9999bb.jpg")

    def test_reddit_links_and_plans(self):
        post = {"url": "http://i.imgur.com/BkTrws0.gifv", "selftext": "album http://imgur.com/a/ax26X and "
                "https://preview.redd.it/abc.png?width=640&amp;s=sig", "comments": [
                    {"author": "a", "body": "clip https://v.redd.it/45kmn63l5ao11 and https://imgur.com/gallery not this"}]}
        links = media.reddit_links(post)
        self.assertEqual([u for _, u in links], ["http://i.imgur.com/BkTrws0.gifv", "http://imgur.com/a/ax26X",
                                                 "https://preview.redd.it/abc.png?width=640&s=sig",
                                                 "https://v.redd.it/45kmn63l5ao11", "https://imgur.com/gallery"])
        self.assertEqual(links[3][0], "comment by u/a")
        plans = [media.plan_link(u) for _, u in links]
        self.assertEqual(plans, [("video", "https://i.imgur.com/BkTrws0.mp4"), ("album", "ax26X"),
                                 ("image", "https://preview.redd.it/abc.png?width=640&s=sig"),
                                 ("vreddit", "https://v.redd.it/45kmn63l5ao11"), None])
        self.assertEqual(media.plan_link("https://imgur.com/nRad4da"), ("image", "https://i.imgur.com/nRad4da.jpg"))

    def test_parse_mpd_picks_best_video_and_audio(self):
        self.assertEqual(media.parse_mpd(MPD), ("DASH_4_8_M", "audio"))

    def test_gallery_merges_identical_groups_and_includes_captures(self):
        with tempfile.TemporaryDirectory() as d:
            corpus = Path(d)
            out = corpus / "media"
            for name in ("play/AAA.png", "play/BBB.png", "play/KO.png"):
                (out / name).parent.mkdir(parents=True, exist_ok=True)
                (out / name).write_bytes(b"x")
            index = {}
            for loc, files in (("en-US", ["AAA", "BBB"]), ("de-DE", ["AAA", "BBB"]), ("ko-KR", ["KO"])):
                for n, f in enumerate(files):
                    index[f"{loc}|{f}"] = {"section": "play", "group": f"Google Play · {loc}", "file": f"play/{f}.png", "order": n}
            (out / "index.json").write_text(json.dumps(index), encoding="utf-8")
            phone = corpus / "phone"
            phone.mkdir()
            (phone / "Screenshot_1.png").write_bytes(b"png1")
            (phone / "dupe.png").write_bytes(b"png1")
            with contextlib.redirect_stdout(io.StringIO()):
                added, skipped = capture.import_files(capture.Captures(out / "own"), phone, "Clan <castle>")
                page = media.write_gallery(out, corpus).read_text(encoding="utf-8")
            self.assertEqual((added, skipped), (1, 1))
            self.assertIn("Google Play · de-DE, en-US", page)
            self.assertIn("Google Play · ko-KR", page)
            self.assertIn("Clan &lt;castle&gt;", page)
            self.assertLess(page.index("Your captures"), page.index("Google Play, current listing"))


if __name__ == "__main__":
    unittest.main()
