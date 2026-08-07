# RSS Feeds

Generate RSS feeds from websites that don't provide one.

Created with standard library Python — zero dependencies. Each source is a
self-contained Python file under [`sources/`](sources/).

## Feeds

- [Texty.org.ua (English)](https://nicucalcea.github.io/rss-feeds/texty-org-ua.xml)
- [UNDP Procurement Notices — Moldova](https://nicucalcea.github.io/rss-feeds/undp-moldova-procurement.xml)

## Usage

Add a source by creating a new file in `sources/`.

Each source file must define:

```python
NAME = "my-source"                    # slug used for filenames
TITLE = "My Source"                   # feed title
LINK = "https://example.com"          # source URL
DESCRIPTION = "..."                   # optional feed description

def get_items():
    """Yield dicts with keys: id, title, link, published, summary"""
    ...
```

The `id` is the unique URL for each item (used as RSS guid). `published` is
an ISO-8601 datetime string. `summary` is optional HTML content.

Run locally:

```bash
uv run python runner.py
```

Feeds are written to `feeds/`. State (seen item IDs) is tracked in `state/`.

## How it works

A GitHub Actions workflow runs every 6 hours, executes all sources, and
deploys the generated feeds to GitHub Pages.
