"""
arXiv adapter.

ROLE IN THE REVIEW
    arXiv catches the 12–24 month gap between a method appearing and its
    peer-reviewed version being indexed. For a fast-moving area like multimodal
    fusion that gap is where the most recent responders to a gap live, and
    missing them would make the gap analysis look staler than the field is.

    But arXiv preprints are NOT peer reviewed, so they fail IC3. They are
    retrieved deliberately and then handled one of two ways:
      - if a published version exists, dedupe merges them and keeps the
        published record (EC4);
      - if not, the record is flagged `preprint_only` and reaches the human
        screener as an explicit judgement call, never auto-included.

    arXiv has no wildcard support and no relevance ranking worth trusting, so
    results are pulled by submission date and filtered locally.

API: https://info.arxiv.org/help/api/user-manual.html
"""
import xml.etree.ElementTree as ET
from typing import Iterator, Optional

from .base import Record, fetch

BASE = "http://export.arxiv.org/api/query"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}
PAGE = 100          # arXiv recommends <= 2000 total, paged in slices of ~100


def _text(node, path) -> str:
    el = node.find(path, NS)
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def _to_record(entry, url: str) -> Optional[Record]:
    aid = _text(entry, "atom:id")
    if not aid:
        return None
    short = aid.rsplit("/", 1)[-1]              # e.g. 2301.12345v2

    published = _text(entry, "atom:published")  # 2023-01-30T18:00:00Z
    year = int(published[:4]) if published[:4].isdigit() else None

    pdf = ""
    for link in entry.findall("atom:link", NS):
        if link.get("title") == "pdf":
            pdf = link.get("href", "")
            break

    journal_ref = _text(entry, "arxiv:journal_ref")

    return Record(
        source="arxiv",
        source_id=short,
        title=_text(entry, "atom:title"),
        abstract=_text(entry, "atom:summary"),
        year=year,
        doi=_text(entry, "arxiv:doi"),
        authors=[" ".join("".join(a.itertext()).split())
                 for a in entry.findall("atom:author/atom:name", NS)],
        # journal_ref is arXiv's own record of where a preprint was published.
        # When present it is strong evidence the work IS peer reviewed, so it is
        # surfaced rather than discarded — the screener needs it for IC3.
        venue=journal_ref or "arXiv",
        venue_type="preprint" if not journal_ref else "",
        language="en",          # arXiv is English-only in practice
        oa_status="green",      # every arXiv record is freely readable
        pdf_url=pdf,
        cited_by_count=0,       # not reported by arXiv
        is_preprint=not journal_ref,
        raw_url=url,
    )


def search(query: str, year_from: int, year_to: int, *,
           max_records: int = 400, use_cache: bool = True) -> Iterator[Record]:
    """`query` must already be in arXiv search_query syntax (see booleanq.to_arxiv)."""
    dated = (f"({query}) AND submittedDate:"
             f"[{year_from}01010000 TO {year_to}12312359]")
    start = 0
    while start < max_records:
        url = f"{BASE}?search_query={dated}&start={start}"
        xml = fetch(BASE, {
            "search_query": dated,
            "start": start,
            "max_results": min(PAGE, max_records - start),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }, parse="text", use_cache=use_cache)
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return
        entries = root.findall("atom:entry", NS)
        if not entries:
            return
        for e in entries:
            rec = _to_record(e, url)
            if rec:
                yield rec
        start += len(entries)


def count(query: str, year_from: int, year_to: int, *, use_cache: bool = True) -> int:
    dated = (f"({query}) AND submittedDate:"
             f"[{year_from}01010000 TO {year_to}12312359]")
    xml = fetch(BASE, {"search_query": dated, "start": 0, "max_results": 1},
                parse="text", use_cache=use_cache)
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return 0
    el = root.find("opensearch:totalResults", NS)
    return int(el.text) if el is not None and (el.text or "").isdigit() else 0
