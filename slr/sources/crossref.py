"""
Crossref adapter.

ROLE IN THE REVIEW
    Crossref is the DOI registration agency, so it has the broadest coverage of
    formally published work — including conference proceedings that OpenAlex
    sometimes indexes thinly. It is used as a coverage CHECK on OpenAlex rather
    than as a primary source.

    Its weakness is the mirror image of OpenAlex's: abstracts are optional at
    deposit time and many publishers (notably IEEE) do not supply them. A record
    with no abstract is still emitted — the pipeline records `abstract_missing`
    so the Threats sheet can report how much of the corpus was screened on title
    alone rather than pretending it was full title+abstract screening.

API: https://api.crossref.org/swagger-ui/index.html
"""
from typing import Iterator, Optional

from .base import CONTACT_EMAIL, Record, classify_venue, fetch, strip_jats

BASE = "https://api.crossref.org/works"

# Excluded at retrieval because none can satisfy IC3 (peer-reviewed venue) and
# they otherwise flood the results — Crossref registers DOIs for these too.
SKIP_TYPES = {"dataset", "component", "grant", "peer-review", "standard",
              "report-component", "journal-issue", "journal-volume"}


def _year(item: dict) -> Optional[int]:
    for key in ("issued", "published-print", "published-online", "created"):
        parts = (item.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            return int(parts[0][0])
    return None


def _to_record(item: dict, url: str) -> Record:
    title = (item.get("title") or [""])[0]
    venue = (item.get("container-title") or [""])[0]
    ctype = item.get("type") or ""

    pdf = ""
    for link in item.get("link") or []:
        if link.get("content-type") == "application/pdf":
            pdf = link.get("URL", "")
            break

    return Record(
        source="crossref",
        source_id=item.get("DOI", ""),
        title=strip_jats(title),
        abstract=strip_jats(item.get("abstract") or ""),
        year=_year(item),
        doi=item.get("DOI", ""),
        authors=[" ".join(x for x in (a.get("given"), a.get("family")) if x)
                 for a in (item.get("author") or [])],
        venue=venue,
        venue_type=classify_venue(venue, ctype),
        language=item.get("language") or "",
        # Crossref does not report OA status; left blank rather than guessed, so
        # that "" means "unknown" everywhere and is never mistaken for "closed".
        oa_status="",
        pdf_url=pdf,
        cited_by_count=item.get("is-referenced-by-count") or 0,
        is_preprint=(ctype == "posted-content"),
        raw_url=url,
    )


def search(query: str, year_from: int, year_to: int, *,
           max_records: int = 1000, use_cache: bool = True) -> Iterator[Record]:
    cursor, seen = "*", 0
    while cursor and seen < max_records:
        params = {
            "query.bibliographic": query,
            "filter": f"from-pub-date:{year_from}-01-01,until-pub-date:{year_to}-12-31",
            "rows": min(100, max_records - seen),   # Crossref caps rows at 100
            "cursor": cursor,
            "mailto": CONTACT_EMAIL,
            # `language` is NOT a selectable Crossref field — including it makes
            # the whole request 400. Verified by bisecting the field list against
            # the live API. Consequence: Crossref records arrive with no language,
            # so they are flagged `language_unreported` rather than screened on
            # it, and pick up a language only if they merge with an OpenAlex or
            # PubMed record. That limitation is reported, not hidden.
            "select": ("DOI,title,abstract,issued,published-print,published-online,"
                       "author,container-title,type,is-referenced-by-count,link"),
        }
        url = f"{BASE}?query.bibliographic={query}&cursor={cursor}"
        msg = (fetch(BASE, params, use_cache=use_cache) or {}).get("message") or {}
        items = msg.get("items") or []
        if not items:
            return
        for item in items:
            seen += 1
            if (item.get("type") or "") in SKIP_TYPES:
                continue
            yield _to_record(item, url)
        nxt = msg.get("next-cursor")
        if nxt == cursor:      # Crossref repeats the cursor at the end of results
            return
        cursor = nxt


def count(query: str, year_from: int, year_to: int, *, use_cache: bool = True) -> int:
    msg = (fetch(BASE, {
        "query.bibliographic": query,
        "filter": f"from-pub-date:{year_from}-01-01,until-pub-date:{year_to}-12-31",
        "rows": 0,
        "mailto": CONTACT_EMAIL,
    }, use_cache=use_cache) or {}).get("message") or {}
    return msg.get("total-results", 0)
