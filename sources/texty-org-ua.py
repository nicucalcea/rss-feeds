"""RSS source: texty.org.ua English articles."""

import urllib.request
from html.parser import HTMLParser

NAME = "texty-org-ua"
TITLE = "Texty.org.ua (English)"
LINK = "https://texty.org.ua/tag/eng/"
DESCRIPTION = "English-language articles from Texty.org.ua — Ukrainian data journalism and investigations."


def get_items():
    """Fetch the /tag/eng/ page and yield article items."""
    req = urllib.request.Request(
        LINK,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; rv:136.0) "
                "Gecko/20100101 Firefox/136.0"
            ),
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    parser = _TextyParser()
    parser.feed(html)

    for article in parser.articles:
        yield {
            "id": article["url"],
            "title": article["title"],
            "link": article["url"],
            "published": article["date"],
            "summary": article["summary"],
        }


# ── HTML parser ──────────────────────────────────────────────────────────


class _TextyParser(HTMLParser):
    """Parse texty.org.ua /tag/eng/ article listing pages."""

    def __init__(self):
        super().__init__()
        self.articles: list[dict] = []
        # Parsing state
        self._in_article = False
        self._article_depth = 0
        self._in_body = False
        self._body_depth = 0
        self._in_h3 = False
        self._in_lead = False
        self._lead_depth = 0
        self._cur = {}

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class", "").split()

        if tag == "article":
            self._in_article = True
            self._article_depth = 1
            self._cur = {"url": "", "title": "", "date": "", "summary": ""}
            return

        if not self._in_article:
            return

        self._article_depth += 1

        if tag == "a" and "article_body" in cls:
            self._in_body = True
            self._body_depth = self._article_depth
            href = dict(attrs).get("href", "")
            if href:
                self._cur["url"] = (
                    href if href.startswith("http") else "https://texty.org.ua" + href
                )

        if self._in_body:
            if tag == "h3":
                self._in_h3 = True
            elif tag == "div" and "lead" in cls:
                self._in_lead = True
                self._lead_depth = self._article_depth

        if tag == "time" and "published_at" in cls:
            dt = dict(attrs).get("datetime", "")
            if dt:
                self._cur["date"] = dt

    def handle_endtag(self, tag):
        if tag == "article":
            if self._cur.get("url"):
                self.articles.append(self._cur)
            self._in_article = False
            self._in_body = False
            self._in_h3 = False
            self._in_lead = False
            return

        if not self._in_article:
            return

        self._article_depth -= 1

        if tag == "h3":
            self._in_h3 = False

        if self._in_body and self._article_depth < self._body_depth:
            self._in_body = False
            self._in_h3 = False

        if self._in_lead and self._article_depth < self._lead_depth:
            self._in_lead = False

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return
        if self._in_h3:
            self._cur["title"] += text
        elif self._in_lead:
            prev = self._cur.get("summary", "")
            if prev and not prev.endswith((" ", "\n")):
                self._cur["summary"] += " "
            self._cur["summary"] += text
