#!/usr/bin/env python3
"""Discover and run all RSS source scripts, update feed files.

Each source file in sources/ must define:
  - NAME       : str   — slug used for filenames (e.g. "texty-org-ua")
  - TITLE      : str   — human-readable feed title
  - LINK       : str   — URL of the source website
  - DESCRIPTION: str   — optional short description
  - get_items() -> iterable of dicts with keys:
      id        : str  — unique URL (used as RSS guid)
      title     : str
      link      : str
      published : str  — ISO-8601 datetime
      summary   : str  — HTML summary (optional)
"""

import copy
import importlib.util
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES_DIR = HERE / "sources"
FEEDS_DIR = HERE / "feeds"
STATE_DIR = HERE / "state"

# ── RSS helpers ──────────────────────────────────────────────────────────

ATOM_NS = "http://www.w3.org/2005/Atom"
ET.register_namespace("atom", ATOM_NS)


def _rfc2822(dt_str: str) -> str:
    """Parse ISO-8601 datetime string → RFC 2822 for RSS pubDate."""
    try:
        dt = datetime.fromisoformat(dt_str)
    except (ValueError, TypeError):
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def _iso_utc(dt_str: str) -> str:
    """Parse any reasonable datetime string → ISO 8601 UTC."""
    if not dt_str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    try:
        dt = datetime.fromisoformat(dt_str)
    except (ValueError, TypeError):
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def parse_existing_items(feed_path: Path) -> list[dict]:
    """Parse items from an existing RSS feed file."""
    if not feed_path.exists():
        return []
    try:
        tree = ET.parse(str(feed_path))
        root = tree.getroot()
        items = []
        for item in root.findall("./channel/item"):
            d = {
                "id": (item.findtext("guid") or "").strip(),
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "published": "",
                "summary": (item.findtext("description") or "").strip(),
            }
            pub = item.findtext("pubDate") or ""
            if pub:
                # RFC 2822 → ISO-8601
                try:
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(pub.strip())
                    d["published"] = dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
                except Exception:
                    d["published"] = ""
            items.append(d)
        return items
    except ET.ParseError:
        return []


def build_rss_xml(
    feed_title: str,
    feed_link: str,
    feed_desc: str,
    items: list[dict],
    source_name: str,
) -> str:
    """Build an RSS 2.0 XML string from the given items (newest first)."""
    # Sort by published date descending; items without date go last
    def _sort_key(itm: dict):
        pub = itm.get("published", "") or ""
        return pub if pub else "0"

    sorted_items = sorted(items, key=_sort_key, reverse=True)
    max_items = 200
    sorted_items = sorted_items[:max_items]

    rss = ET.Element("rss", attrib={"version": "2.0"})
    channel = ET.SubElement(rss, "channel")

    _text(channel, "title", feed_title)
    _text(channel, "link", feed_link)
    _text(channel, "description", feed_desc or feed_title)
    _text(channel, "language", "en")
    _text(channel, "generator", "rss-feeds runner")
    _text(channel, "lastBuildDate",
          datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z"))

    # Atom self-link so feed readers know the canonical URL
    atom_link = ET.SubElement(channel, f"{{{ATOM_NS}}}link")
    atom_link.set("href",
                  f"https://nicucalcea.github.io/rss-feeds/{source_name}.xml")
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    for itm in sorted_items:
        el = ET.SubElement(channel, "item")
        _text(el, "title", itm.get("title", ""))
        _text(el, "link", itm.get("link", itm.get("id", "")))
        _text(el, "guid", itm.get("id", ""),
              {"isPermaLink": "true"})
        pub = itm.get("published", "")
        if pub:
            _text(el, "pubDate", _rfc2822(pub))
        desc = itm.get("summary", "")
        if desc:
            _text(el, "description", desc)

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        rss, encoding="unicode"
    )


def _text(parent, tag: str, value: str, extra_attrib: dict | None = None):
    el = ET.SubElement(parent, tag)
    el.text = value
    if extra_attrib:
        el.attrib.update(extra_attrib)


# ── Source loading ───────────────────────────────────────────────────────


def load_source(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Main ─────────────────────────────────────────────────────────────────


def run_source(source_path: Path) -> bool:
    """Run a single source. Returns True if new items were added."""
    mod = load_source(source_path)
    name = mod.NAME
    title = mod.TITLE
    link = mod.LINK
    description = getattr(mod, "DESCRIPTION", "")

    print(f"\n── {name} ──")

    # Fetch current items from the source
    try:
        raw_items = list(mod.get_items())
    except Exception as e:
        print(f"  ERROR in get_items(): {e}")
        return False

    if not raw_items:
        print(f"  0 items returned, skipping")
        return False

    # Normalise published fields
    for it in raw_items:
        if it.get("published"):
            it["published"] = _iso_utc(it["published"])
        it["id"] = (it.get("id") or it.get("link") or "").strip()
        if not it["id"]:
            print(f"  WARNING: item without id/link, skipped: {it.get('title')}")
            continue

    # Remove items without id
    items = [it for it in raw_items if it.get("id")]

    # Load state (seen URLs)
    state_path = STATE_DIR / f"{name}.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        state = {"seen": {}}

    # Find new items
    seen = state.get("seen", {})
    new_items = [it for it in items if it["id"] not in seen]
    if not new_items:
        print(f"  0 new items (already seen all {len(items)})")
        return False

    print(f"  {len(new_items)} new item(s) out of {len(items)} total")

    # Update state with new items
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    for it in new_items:
        seen[it["id"]] = it.get("published") or now_iso

    # Load existing items from current feed file
    feed_path = FEEDS_DIR / f"{name}.xml"
    existing_items = parse_existing_items(feed_path)

    # Merge: existing items + new items, dedup by id
    seen_ids = {it["id"] for it in existing_items}
    for it in new_items:
        if it["id"] not in seen_ids:
            existing_items.append(it)
            seen_ids.add(it["id"])

    # Build and write RSS
    rss_xml = build_rss_xml(title, link, description, existing_items, name)
    FEEDS_DIR.mkdir(parents=True, exist_ok=True)
    feed_path.write_text(rss_xml, encoding="utf-8")
    print(f"  wrote {len(existing_items)} items to {feed_path}")

    # Write state
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False),
                          encoding="utf-8")
    print(f"  state written ({len(seen)} seen IDs)")

    return True


def main():
    os.makedirs(FEEDS_DIR, exist_ok=True)
    os.makedirs(STATE_DIR, exist_ok=True)

    source_files = sorted(SOURCES_DIR.glob("*.py"))
    sources = [p for p in source_files if not p.name.startswith("_")]

    if not sources:
        print("No source files found in sources/")
        sys.exit(1)

    any_new = False
    for path in sources:
        try:
            ok = run_source(path)
            if ok:
                any_new = True
        except Exception as e:
            print(f"  FAILED to load {path.name}: {e}")

    if not any_new:
        print("\nNo new items from any source.")

    # Write a timestamp for the workflow
    (HERE / "last-run.txt").write_text(
        datetime.now(timezone.utc).isoformat() + "\n"
    )


if __name__ == "__main__":
    main()
