# GrowStone research collectors

Scripts that gather public information about GrowStone Online into a local, searchable corpus for game-design study. Only Python 3.10+ and `requests` are needed.

| Script | Collects | Access method | Needs |
|---|---|---|---|
| `fandom_wiki.py` | All three GrowStone Fandom wikis (including *Legend Stone*): every page (wikitext, HTML, Markdown, links, categories), optionally all images | Official MediaWiki API, 1 request/s | — |
| `reddit.py` | Full history of r/GrowStone and r/GrowStone_Online with complete comment threads; posts and comments mentioning the game anywhere on Reddit (filtered for game context); optional post images | **No key:** Arctic Shift (subreddit history, comment trees) + PullPush (site-wide search, fallback), both Pushshift-successor archives, paced and with backoff. **Optional:** Reddit's official Data API (live data) | — (official API: approved `REDDIT_CLIENT_ID`/`SECRET`) |
| `play_store.py` | The public Google Play listing in 15 languages: rating, downloads, update date, what's new, description, and the ~3 reviews shown per language (with developer replies), dated for history | Public store page only (allowed by Play's robots.txt), 1 request/5 s | — |
| `import_reviews.py` | Reviews you collect by hand or export from a licensed review-data service (CSV, JSON, or pasted text) | Local files | — |
| `web_pages.py` | Reviews, blogs, guides and tracker pages from `sources.txt`, plus links discovered in the wiki and Reddit output | Plain HTTP with robots.txt checks, 1 request/3 s per site | — |
| `youtube_index.py` | An index of GrowStone videos: title, channel, and where each was linked; with a key also date, length, views and keyword search | **No key:** YouTube's official oEmbed endpoint for every video linked from the corpus. **With key:** YouTube Data API v3 search | — (search: `YOUTUBE_API_KEY`) |
| `media.py` | **Screens and clips:** full-size store screenshots (Play in 15 languages, App Store iPhone and iPad in 16 countries); every Play listing the Wayback Machine archived since 2018, with its screenshots and text; images and clips linked on Reddit (imgur, i.redd.it, v.redd.it); YouTube thumbnails. Builds `media/gallery.html` | Image CDNs with robots.txt checks; Apple's documented iTunes Search API (`/lookup`); Wayback CDX API; 1 request/s, 4 s for pages and APIs | — (whole imgur albums: free `IMGUR_CLIENT_ID`) |
| `capture.py` | **Your own screenshots and recordings** from a phone or emulator (adb), or imported from the phone's own screenshot and screen-record buttons | Local: `adb exec-out screencap`, `adb shell screenrecord`, or files you copy | Android platform-tools for adb |
| `corpus_index.py` | Full-text search over everything above | SQLite FTS5, local | — |

Output goes to `study/growstone/corpus/`, which is **gitignored**: it stays on your machine.

## Quick start

```bash
cd study/growstone/tools
export GS_RESEARCH_UA="growstone-research/0.1 (contact: you@example.com)"   # identify yourself

python3 fandom_wiki.py --images                 # about 10 minutes
python3 play_store.py                           # about 2 minutes
python3 web_pages.py --from-corpus --depth 1    # uses links found in the wiki
python3 reddit.py --media                       # both subreddits + site-wide mentions (no key), ~20 min
python3 youtube_index.py --from-corpus          # videos linked anywhere in the corpus (no key)
export YOUTUBE_API_KEY=...                      # optional, free and self-service
python3 youtube_index.py --from-corpus --search # adds keyword search, dates, lengths, views
python3 media.py all                            # screenshots, archived listings, linked clips, thumbnails, ~10 min
python3 capture.py session                      # your own captures while you play (adb), then:
python3 media.py gallery                        # open corpus/media/gallery.html in a browser

python3 corpus_index.py build
python3 corpus_index.py search '"stone token" OR "돌의 징표"'
python3 corpus_index.py search 'grind* AND pvp' --source play
python3 corpus_index.py stats
```

Every collector is **resumable** and **incremental**. Re-running skips wiki pages whose revision is unchanged, Reddit threads whose comment count is unchanged, and web pages already saved. Use `--limit N` on the wiki and Reddit scripts for a quick trial (`reddit.py --limit 5`). Run the offline tests with `python3 -m unittest test_tools -v`.

### Keys (optional)
Nothing above needs a key. Keys add coverage:
- **YouTube (recommended, 5 minutes):** Google Cloud console → enable *YouTube Data API v3* → *Credentials* → *API key*. This is still self-service and free. The 10,000 units/day quota covers about 100 search pages. It adds keyword search (videos nobody linked) and publish date, length and views.
- **Reddit (slow to get):** since November 2025, Reddit no longer issues API keys on request. Under its *Responsible Builder Policy* you apply through Reddit Developer Support, describe the use, and wait for manual approval. Once approved, set `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` and a `GS_RESEARCH_UA` containing your Reddit username; `reddit.py` then switches to the official API automatically. It adds site-wide search and posts from the last couple of days, which the archive may not have indexed yet.

### Reddit without a key: the options, tested on 2026-10-30

| Option | What it is | Status for us |
|---|---|---|
| **Arctic Shift API** ([docs](https://github.com/ArthurHeitmann/arctic_shift/tree/master/api)) | Volunteer archive for researchers and moderators; Pushshift successor | ✅ **Used.** Full r/GrowStone history (732 posts) and complete comment trees. Text search must name a subreddit; large-subreddit searches time out ("slow down"), so we don't use it for mentions |
| **PullPush API** ([pullpush.io](https://pullpush.io)) | Pushshift-compatible archive API, ~30 requests/min, occasional multi-week outages | ✅ **Used** for site-wide search (`title=` / `selftext=` are precise; free-text `q=` is fuzzy) and as a fallback: it has r/GrowStone_Online, which Arctic Shift lacks |
| **Arctic Shift download tool** ([web](https://arctic-shift.photon-reddit.com/download-tool)) | Point-and-click export of a user or small subreddit | ✅ Manual alternative; same data as the API |
| **Monthly and per-subreddit dumps** (Academic Torrents, via [Arctic Shift](https://github.com/ArthurHeitmann/arctic_shift/blob/master/download_links.md) and [Watchful1/PushshiftDumps](https://github.com/Watchful1/PushshiftDumps)) | All of Reddit 2005–2025 as `.zst` NDJSON; per-subreddit files for the top 40k subreddits | ⚠️ Works offline, but terabytes for the monthly files, and our subreddits are too small for the per-subreddit set. Only worth it for large-scale analysis |
| **Reddit for Researchers** (r/reddit4researchers) | Reddit's official research program | ⚠️ Official route, but for principal investigators; intake appears stalled since late 2025 |
| Tools on `.json` endpoints: [YARS](https://github.com/datavorous/yars), [ScrapiReddit](https://github.com/rodneykeilson/ScrapiReddit), most "no API key" scrapers | Append `.json` to Reddit URLs | ❌ 403 since May 2026, and robots.txt is `Disallow: /`. YARS itself advises rotating proxies to avoid IP bans |
| Tools that impersonate a browser: e.g. [toolzerhub/reddit-scraper](https://github.com/toolzerhub/reddit-scraper) (Chrome TLS fingerprint via curl_cffi on `/svc/shreddit/` fragments, "residential proxy works best"), Playwright scrapers | Disguise automated traffic as a person's browser | ❌ Not used: bypassing a site's bot blocking is evasion, and against Reddit's terms |
| RSS feeds (`/.rss`) | Feed-reader endpoint; still answers 200 | ❌ Covered by `Disallow: /`; Reddit has flagged it as the next surface to close |
| Redlib / Libreddit mirror instances | Privacy front-ends that proxy Reddit | ❌ They rely on borrowed app credentials and volunteers' bandwidth; scraping them shifts the load onto those volunteers |
| Hosted scrapers (Apify actors etc.) | Paid services that run the above for you | ❌ Same methods, plus cost |

**Treat the archives gently.** They are free and volunteer-run. The collector waits 1 s (Arctic Shift) and 2.5 s (PullPush) between calls and backs off when they report load. Their data lags Reddit by up to a couple of days. Authors can request removal ([Arctic Shift form](https://docs.google.com/forms/d/e/1FAIpQLSfzkmE8Bg6K_xii7aRm66ljzvo2tR59lTsdJ99acW4WX786Vw/viewform), [PullPush](https://removals.pullpush.io)), so don't republish what you collect.

**Mention filtering.** "Growstone" is also a place in *Hollow Knight: Silksong* and a hydroponic growing medium. Outside the dedicated subreddits, a hit is kept only with game context (e.g. "grow stone online", SUPERCAT, MMORPG, PvP, rubies, Play Store) or from a gaming subreddit. The log reports how many hits were dropped.

## Output layout

```
corpus/
  wiki/<wiki>/pages/<Title>.{md,wikitext,html,json}   index.json  siteinfo.json  images/  ATTRIBUTION.md
  reddit/posts/<id>.{md,json}   media/   index.json   about_<sub>.json   mentions.{json,md}   (comment mentions elsewhere)
  play/<date>_<locale>.{md,json}   html/   <date>_summary.json
  reviews/<source>/<id>.md   reviews.jsonl
  web/pages/<site_path>.{md,html}   index.json        (index.json also records skips and errors)
  play/history/<date>_<lang>.md                       (archived listings: description and what's new over time)
  appstore/<date>_<country>.{md,json}
  youtube/videos.{json,md}
  media/gallery.html                                  (open in a browser: every image and clip below, grouped)
  media/play/  appstore/  linked/  youtube/            index.json  history.json  linked.json
  media/own/<date>/<time>_<label>.{png,mp4}  index.jsonl   (capture.py)
  corpus.db                                           (search index)
```

## Screens and clips

`media.py` collects what the sources allow, at full size, and `gallery.html` shows it with captions and links back to each source. Same-image groups are merged, so "Google Play · de-DE, en-US, …" means those languages show identical screenshots.

| Source | What you get | Notes |
|---|---|---|
| Google Play listing | 6 screenshots per language, original resolution (`=s0`), from the pages `play_store.py` saved | The Japanese listing is a separate product, *Stone Strike Online* (idle RPG), with its own 11 screenshots |
| App Store | iPhone and iPad screenshots, original resolution, plus description and release notes in `corpus/appstore/` | Through Apple's documented iTunes Search API; the store's web pages are not scraped |
| Wayback Machine | One archived Play listing per month (2018 onward): its screenshots and its full text in `corpus/play/history/` | Shows how the game's screens, pitch and patch notes changed. Old images come from Google if still live, else from the archive |
| Reddit links | Images, imgur clips (`.gifv` saved as `.mp4`), Reddit-hosted video (video and audio as separate files; join with `ffmpeg -i x.mp4 -i x_audio.mp4 -c copy out.mp4`) | imgur albums give only their cover without a key; set `IMGUR_CLIENT_ID` (free, [register an app](https://api.imgur.com/oauth2/addclient)) for every image. Many 2017–2019 imgur links are deleted |
| YouTube | One thumbnail per indexed video | The `thumbnail_url` that oEmbed returns. The videos themselves are not downloaded (below) |
| Wikis | Every uploaded image (`fandom_wiki.py --images`), including the third wiki, *Legend Stone* | Many are item icons and game screenshots |
| **You** | Whatever you capture with `capture.py` | The only source that is complete, current and full resolution. `session` lets you label each shot as you go ("forge result", "clan raid lobby"); `record 120` takes video. If the game refuses to run with USB debugging on, use the phone's screenshot and screen-record buttons (or `scrcpy --record`, which keeps audio) and `capture.py import <folder>` |

**For video, recording your own play is the realistic route.** Almost all GrowStone video is on YouTube, which can't be downloaded (below). Watch it there, and use the video index (`youtube/videos.md`) to find the right clips.

Every `.md` starts with a small header (`source`, `title`, `url`, dates), so each note can be traced back to where it came from.

## What is deliberately not collected, and why

| Source | Why not | What to do instead |
|---|---|---|
| The full Google Play review feed | Play's robots.txt disallows the endpoints that serve it (`/_`, `/store/getreviews`), and Google's terms only allow automated access that robots.txt permits. Bulk scrapers such as `google-play-scraper` use exactly those endpoints | Read reviews in the store (sort by *Newest* and filter by star rating) and paste useful ones into a `.txt` for `import_reviews.py`, or export them from a licensed provider (AppFollow, AppTweak, Appbot, data.ai), whose terms cover this |
| Facebook page and groups | Login required; Meta's terms forbid automated collection | Read manually; save notable posts as text |
| Reddit's own `.json` / `.rss` endpoints and HTML pages, directly or via browser impersonation, proxies or mirrors | Reddit's robots.txt is `Disallow: /` for every bot, its Public Content Policy points researchers to the API and r/reddit4researchers, and `.json` returns 403 without OAuth since May 2026. Disguising traffic to get past that is evading an access control (details in the table above) | Arctic Shift + PullPush (default), or the official API once approved |
| YouTube without the API: `yt-dlp` metadata or comments, Invidious/Piped instances, scraping search pages or RSS feeds | YouTube's Terms of Service forbid automated access except by search engines following robots.txt or with written permission; robots.txt disallows `/results`, `/comment`, `/feeds/videos.xml` and `/timedtext_video` | oEmbed for linked videos (no key), the free Data API key for search |
| YouTube video files (yt-dlp and similar downloaders) | YouTube's terms forbid downloading except through YouTube's own features, even for Creative Commons videos | Watch on YouTube (Premium's in-app offline mode is the sanctioned way to keep a copy), ask the creator for the file, or record your own play with `capture.py` |
| App Store web pages (`apps.apple.com`), including App Preview videos | Apple's website terms forbid page scraping | `media.py` uses the documented iTunes Search API, which gives screenshots and text but not preview videos |
| TapTap | Its robots.txt bars AI agents by name | Visit in a browser |
| Images, UI, sounds or data from inside the game's APK, and the cracked iOS build on archive.org | SUPERCAT's copyrighted assets; the cracked build is pirated | The store screenshots, your own captures, and `apk-teardown.md` (structure only) |
| Discord, LINE, in-game chat | Private communities | Ask members directly, with permission |
| Anything behind a login, paywall or bot wall (e.g. chrome-stats returns 403) | Access controls | Visit in a browser |

## Using what you collect

- **Wiki text is CC BY-SA 3.0.** If you quote it in our docs, credit the wiki and link the page.
- **Reddit posts, reviews and blog articles belong to their authors.** Use them to learn and summarize. Don't republish them, and don't commit the corpus.
- **Learn the mechanics, then design our own.** Don't carry over GrowStone's names, item lists, numbers, art or UI.
