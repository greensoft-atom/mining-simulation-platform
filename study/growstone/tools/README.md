# GrowStone research collectors

Scripts that gather public information about GrowStone Online into a local, searchable corpus for game-design study. Only Python 3.10+ and `requests` are needed.

| Script | Collects | Access method | Needs |
|---|---|---|---|
| `fandom_wiki.py` | Both GrowStone Fandom wikis: every page (wikitext, HTML, Markdown, links, categories), optionally all images | Official MediaWiki API, 1 request/s | — |
| `reddit.py` | r/GrowStone (all listings, keyword searches) and site-wide mentions; full comment threads; optional post images | Official Reddit Data API (OAuth app-only), ≤ 85 requests/min | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` |
| `play_store.py` | The public Google Play listing in 15 languages: rating, downloads, update date, what's new, description, and the ~3 reviews shown per language (with developer replies), dated for history | Public store page only (allowed by Play's robots.txt), 1 request/5 s | — |
| `import_reviews.py` | Reviews you collect by hand or export from a licensed review-data service (CSV, JSON, or pasted text) | Local files | — |
| `web_pages.py` | Reviews, blogs, guides and tracker pages from `sources.txt`, plus links discovered in the wiki and Reddit output | Plain HTTP with robots.txt checks, 1 request/3 s per site | — |
| `youtube_index.py` | An index of gameplay videos (title, channel, date, length, views, link) | Official YouTube Data API v3 | `YOUTUBE_API_KEY` |
| `corpus_index.py` | Full-text search over everything above | SQLite FTS5, local | — |

Output goes to `study/growstone/corpus/`, which is **gitignored**: it stays on your machine.

## Quick start

```bash
cd study/growstone/tools
export GS_RESEARCH_UA="growstone-research/0.1 (contact: you@example.com)"   # identify yourself

python3 fandom_wiki.py --images                 # about 10 minutes
python3 play_store.py                           # about 2 minutes
python3 web_pages.py --from-corpus --depth 1    # uses links found in the wiki
export REDDIT_CLIENT_ID=... REDDIT_CLIENT_SECRET=...
python3 reddit.py --media                       # r/GrowStone + site-wide
export YOUTUBE_API_KEY=...
python3 youtube_index.py                        # writes corpus/youtube/videos.md

python3 corpus_index.py build
python3 corpus_index.py search '"stone token" OR "돌의 징표"'
python3 corpus_index.py search 'grind* AND pvp' --source play
python3 corpus_index.py stats
```

Every collector is **resumable** and **incremental**. Re-running skips wiki pages whose revision is unchanged, Reddit threads whose comment count is unchanged, and web pages already saved. Use `--limit N` on the wiki and Reddit scripts for a quick trial. Run the offline tests with `python3 -m unittest test_tools -v`.

### Getting the API keys
- **Reddit:** log in, open https://www.reddit.com/prefs/apps, and choose *create another app…* → type **script** → redirect URI `http://localhost:8080`. The client ID is the string under the app name; the secret is labelled *secret*. Set `GS_RESEARCH_UA` to include your Reddit username, as Reddit's API rules require.
- **YouTube:** Google Cloud console → enable *YouTube Data API v3* → *Credentials* → *API key*. The free quota (10,000 units/day) covers about 100 search pages.

## Output layout

```
corpus/
  wiki/<wiki>/pages/<Title>.{md,wikitext,html,json}   index.json  siteinfo.json  images/  ATTRIBUTION.md
  reddit/posts/<id>.{md,json}   media/   index.json   about_GrowStone.json
  play/<date>_<locale>.{md,json}   html/   <date>_summary.json
  reviews/<source>/<id>.md   reviews.jsonl
  web/pages/<site_path>.{md,html}   index.json        (index.json also records skips and errors)
  youtube/videos.{json,md}
  corpus.db                                           (search index)
```

Every `.md` starts with a small header (`source`, `title`, `url`, dates), so each note can be traced back to where it came from.

## What is deliberately not collected, and why

| Source | Why not | What to do instead |
|---|---|---|
| The full Google Play review feed | Play's robots.txt disallows the endpoints that serve it (`/_`, `/store/getreviews`), and Google's terms only allow automated access that robots.txt permits. Bulk scrapers such as `google-play-scraper` use exactly those endpoints | Read reviews in the store (sort by *Newest* and filter by star rating) and paste useful ones into a `.txt` for `import_reviews.py`, or export them from a licensed provider (AppFollow, AppTweak, Appbot, data.ai), whose terms cover this |
| Facebook page and groups | Login required; Meta's terms forbid automated collection | Read manually; save notable posts as text |
| YouTube video files | YouTube's terms forbid downloading | Use `youtube_index.py`, watch, and take your own notes and screenshots |
| Discord, LINE, in-game chat | Private communities | Ask members directly, with permission |
| Anything behind a login, paywall or bot wall (e.g. chrome-stats returns 403) | Access controls | Visit in a browser |

## Using what you collect

- **Wiki text is CC BY-SA 3.0.** If you quote it in our docs, credit the wiki and link the page.
- **Reddit posts, reviews and blog articles belong to their authors.** Use them to learn and summarize. Don't republish them, and don't commit the corpus.
- **Learn the mechanics, then design our own.** Don't carry over GrowStone's names, item lists, numbers, art or UI.
