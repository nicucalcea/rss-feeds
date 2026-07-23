# AGENTS.md — for AI agents adding RSS sources

Follow the project's development philosophy: lazy (efficient), stdlib-first,
no unnecessary code. Read `/home/nicu/.pi/agent/AGENTS.md` for the full
philosophy. This file covers the project-specific patterns.

## Source API contract

Create one file `sources/<name>.py`. It must define:

| Variable / Function | Required | Description |
|---|---|---|
| `NAME` | yes | Slug used for filenames. Hyphens OK, e.g. `"my-blog"` |
| `TITLE` | yes | Human-readable feed title, e.g. `"My Blog"` |
| `LINK` | yes | URL of the source website |
| `DESCRIPTION` | no | Feed description text |
| `get_items()` | yes | Yields item dicts (see below) |

Each item dict:

```python
{
    "id": "https://example.com/article-1",   # unique URL → RSS guid
    "title": "Article Title",
    "link": "https://example.com/article-1", # same as id for most HTML sources
    "published": "2026-07-23",               # ISO-8601 date or datetime
    "summary": "<p>HTML content or plain text</p>",  # optional
}
```

`id` is mandatory — it's used for deduplication. If `id` is missing, the
runner falls back to `link`.

`published` can be a date string (`"2026-07-23"`) or full datetime
(`"2026-07-23T15:21:00+03:00"`). The runner normalises it to ISO-8601 UTC.

## Before writing code

1. Check if the site already has an RSS feed (look for `<link type="application/rss+xml">` in the HTML, or `/feed`, `/rss`, `/atom.xml` endpoints).
2. If it already has a feed, ask the user before duplicating it.
3. If it doesn't, investigate the HTML structure with `web_fetch` or `curl` to find the article listing pattern before writing the parser.

## Patterns

### HTML scraping with stdlib

Use `urllib.request` + `html.parser.HTMLParser`. See `sources/texty-org-ua.py`
for a worked example. Key patterns:

- Set a realistic `User-Agent` header — some sites block the default Python one.
- Use a state-machine approach in the parser: track which container you're in
  (`_in_article`, `_in_body`, `_in_h3`, etc.) using depth counters.
- Clear state flags eagerly in `handle_endtag` to avoid bleed.
- Test with `uv run python -c "from sources.<name> import get_items; print(list(get_items()))"`.

Only add a dependency (beautifulsoup4, lxml, httpx, etc.) when `html.parser`
is genuinely too tedious — e.g. nested attribute-heavy tables, JavaScript-
rendered content that requires a headless browser. Start with stdlib and step
up only when blocked.

### JSON API sources

For sites that load content via an XHR/fetch JSON endpoint:

```python
import json
import urllib.request

req = urllib.request.Request("https://api.example.com/posts")
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())

for post in data["articles"]:
    yield {
        "id": post["url"],
        "title": post["title"],
        "link": post["url"],
        "published": post["date"],
        "summary": post.get("excerpt", ""),
    }
```

### Pagination

Don't implement pagination unless explicitly asked. The cron job runs every
6 hours — the latest page of items is usually enough. The runner merges new
items with the existing feed, so historical items persist across runs.

If a site only shows 5 items per page and the user wants more, *then*
implement pagination. For the first iteration, one page is fine.

## Testing locally

```bash
uv run python runner.py
```

This runs all sources in `sources/`, updates `feeds/` and `state/`. Check the
output RSS with:

```bash
uv run python -c "
import xml.etree.ElementTree as ET
tree = ET.parse('feeds/<name>.xml')
for item in tree.findall('.//item'):
    print(item.findtext('title'), '|', item.findtext('pubDate'))
"
```

To reset state for a source (e.g. during development), delete the
corresponding `state/<name>.json` file.

## What happens on push

1. GitHub Actions runs `runner.py` (via `uv run`).
2. The runner discovers `sources/*.py`, runs each `get_items()`, diffs against
   `state/*.json`, builds/updates `feeds/*.xml`.
3. State changes are committed back to `main` with `[skip ci]` to avoid
   re-triggering the workflow.
4. `feeds/` is deployed to GitHub Pages.

The feed URL is always:
`https://nicucalcea.github.io/rss-feeds/<NAME>.xml`

## Common pitfalls

- **Missing id**: If an item doesn't have a unique URL, the runner can't
  deduplicate and will add it every run. Always provide `id` (equals `link`
  for most HTML sources).
- **Date parsing**: The runner normalises dates with `datetime.fromisoformat`.
  If your source has a non-standard date format, convert it to ISO-8601 in
  `get_items()` before yielding. Python stdlib `email.utils.parsedate_to_datetime`
  handles RFC 2822 dates.
- **Empty feeds**: If `get_items()` returns nothing, check the parser. Fetch
  the page with the same `User-Agent` you're using in the source to reproduce
  locally.
- **Site blocks**: Some sites block the default Python `User-Agent`. Use a
  common browser UA string.
- **Encoding**: Always `.decode("utf-8", errors="replace")` when reading HTTP
  responses. Some sites serve windows-1252 or other encodings — if you see
  garbled text, check `resp.headers.get_content_charset()`.
- **Hyphens in filenames**: Python module names don't allow hyphens, but
  the runner uses `importlib.util.spec_from_file_location` which loads by
  file path directly — hyphens work fine. Don't rename files to use
  underscores in `sources/`.
