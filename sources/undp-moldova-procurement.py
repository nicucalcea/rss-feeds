"""RSS source: UNDP procurement notices for Moldova."""

from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin
import urllib.request

NAME = "undp-moldova-procurement"
TITLE = "UNDP Procurement Notices — Moldova"
LINK = "https://procurement-notices.undp.org/index.cfm"
DESCRIPTION = "UNDP procurement notices whose UNDP Office/Country contains Moldova or MDA."


def get_items():
    """Fetch current notices and return only Moldova-related entries."""
    request = urllib.request.Request(
        LINK,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; rss-feeds/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")

    parser = _NoticeParser()
    parser.feed(html)
    for href, cells in parser.rows:
        if len(cells) < 6 or not any(term in cells[2].upper() for term in ("MOLDOVA", "MDA")):
            continue
        published = datetime.strptime(cells[5], "%d-%b-%y").date().isoformat()
        link = urljoin(LINK, href)
        yield {
            "id": link,
            "title": cells[0],
            "link": link,
            "published": published,
            "summary": f"Ref No: {cells[1]}<br>UNDP Office/Country: {cells[2]}<br>"
            f"Process: {cells[3]}<br>Deadline: {cells[4]}",
        }


class _NoticeParser(HTMLParser):
    """Extract the six cells from each notice row in the listing."""

    def __init__(self):
        super().__init__()
        self.rows = []
        self._href = None
        self._cells = []
        self._span_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self._span_depth:
            self._span_depth += 1
        elif self._href is not None and tag == "span":
            self._span_depth = 1
        if tag == "a" and "vacanciesTableLink" in attrs.get("class", "").split():
            self._href = attrs.get("href", "")
            self._cells = []
        elif self._href is not None and tag == "div" and "vacanciesTable__cell" in attrs.get("class", "").split():
            self._cells.append([])

    def handle_data(self, data):
        if self._span_depth and self._cells:
            self._cells[-1].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.rows.append((self._href, [" ".join(cell).strip() for cell in self._cells]))
            self._href = None
            self._cells = []
        if self._span_depth:
            self._span_depth -= 1


if __name__ == "__main__":
    parser = _NoticeParser()
    parser.feed('''<a href="view_negotiation.cfm?nego_id=1" class="vacanciesTableLink">
<div class="vacanciesTable__cell"><span>Notice</span></div><div class="vacanciesTable__cell"><span>UNDP-MDA-1</span></div>
<div class="vacanciesTable__cell"><span>UNDP-MDA/MOLDOVA</span></div><div class="vacanciesTable__cell"><span>RFQ</span></div>
<div class="vacanciesTable__cell"><span>20-Aug-26</span></div><div class="vacanciesTable__cell"><span>06-Aug-26</span></div></a>''')
    assert parser.rows == [("view_negotiation.cfm?nego_id=1", ["Notice", "UNDP-MDA-1", "UNDP-MDA/MOLDOVA", "RFQ", "20-Aug-26", "06-Aug-26"])]
