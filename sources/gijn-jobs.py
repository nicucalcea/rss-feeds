"""RSS source: GIJN Jobs Board."""

import xml.etree.ElementTree as ET
import urllib.request
from email.utils import parsedate_to_datetime

NAME = "gijn-jobs"
TITLE = "GIJN Jobs Board"
LINK = "https://gijn.org/jobs/"
DESCRIPTION = "International journalism jobs in investigative reporting, training, and teaching from the Global Investigative Journalism Network."

_FEED_URL = "https://gijn.org/?feed=rss2&cat=23037"


def get_items():
    """Fetch the native WordPress category feed and yield job items."""
    req = urllib.request.Request(
        _FEED_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/145.0.0.0 Safari/537.36"
            ),
            "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()

    root = ET.fromstring(raw)

    for item in root.findall("./channel/item"):
        link_el = item.find("link")
        guid_el = item.find("guid")
        title_el = item.find("title")
        pubdate_el = item.find("pubDate")
        desc_el = item.find("description")

        link = link_el.text.strip() if link_el is not None and link_el.text else ""
        guid = guid_el.text.strip() if guid_el is not None and guid_el.text else ""
        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        pubdate = pubdate_el.text.strip() if pubdate_el is not None and pubdate_el.text else ""
        desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""

        if not link:
            continue

        published_iso = ""
        if pubdate:
            try:
                published_iso = parsedate_to_datetime(pubdate).isoformat()
            except (ValueError, TypeError):
                published_iso = pubdate

        yield {
            "id": guid or link,
            "title": title,
            "link": link,
            "published": published_iso,
            "summary": desc,
        }
