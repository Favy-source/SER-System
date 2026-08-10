"""
OpenAlex adapter — the spine of this review.

WHY THE SPINE
    OpenAlex is the only free source that provides all four of: abstracts,
    open-access status, forward citations, and backward references. The last two
    make method step 3 (citation traversal) possible at all, and OA status is
    critical for a review conducted without institutional subscriptions — a paper
    that cannot be read cannot be quality-appraised.

    Its known weakness is abstract coverage: some records, especially older
    conference papers, have no abstract_inverted_index. That is recorded as a
    threat to validity (Threats sheet) rather than hidden, because a missing
    abstract means the local Boolean predicate sees title only, which biases
    toward recall loss.

API: https://docs.openalex.org/api-entities/works
"""
import re
from typing import Dict, Iterator, List, Optional

from .base import Record, classify_venue, fetch

BASE = "https://api.openalex.org/works"

# Requested explicitly to keep payloads small; referenced_works alone can be
# hundreds of IDs per record, so it is only pulled when citations need it.
FIELDS = ",".join([
    "id", "doi", "title", "display_name", "publication_year", "language", "type",
    "cited_by_count", "authorships", "primary_location", "open_access",
    "abstract_inverted_index",
])
FIELDS_WITH_REFS = FIELDS + ",referenced_works"


def reconstruct_abstract(inv: Optional[Dict[str, List[int]]]) -> str:
    """OpenAlex stores abstracts as an inverted index for copyright reasons.

    {"emotion": [0, 12], "recognition": [1]} -> "emotion recognition ... emotion"
    Position gaps are possible; sorting by index and joining is the documented
    reconstruction and is lossy only in whitespace.
    """
    if not inv:
        return ""
    pos: Dict[int, str] = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def _to_record(w: dict, url: str) -> Record:
    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}
    oa = w.get("open_access") or {}
    doi = (w.get("doi") or "").replace("https://doi.org/", "")

    return Record(
        source="openalex",
        source_id=(w.get("id") or "").rsplit("/", 1)[-1],
        title=w.get("title") or w.get("display_name") or "",
        abstract=reconstruct_abstract(w.get("abstract_inverted_index")),
        year=w.get("publication_year"),
        doi=doi,
        authors=[(a.get("author") or {}).get("display_name", "")
                 for a in (w.get("authorships") or [])],
        venue=src.get("display_name") or "",
        venue_type=classify_venue(src.get("display_name") or "", w.get("type") or ""),
        language=w.get("language") or "",
        oa_status=oa.get("oa_status") or "",
        pdf_url=loc.get("pdf_url") or oa.get("oa_url") or "",
        cited_by_count=w.get("cited_by_count") or 0,
        referenced_works=[r.rsplit("/", 1)[-1] for r in (w.get("referenced_works") or [])],
        is_preprint=(w.get("type") == "preprint"
                     or "arxiv" in (src.get("display_name") or "").lower()),
        raw_url=url,
    )


def search(query: str, year_from: int, year_to: int, *,
           max_records: int = 1000, with_refs: bool = False,
           use_cache: bool = True) -> Iterator[Record]:
    """Cursor-paginated search. Yields Records lazily.

    `query` goes to OpenAlex's own relevance search, which is stemmed and fuzzy —
    deliberately broader than the protocol string. The exact Boolean predicate is
    applied afterwards by the pipeline.
    """
    cursor, seen = "*", 0
    while cursor and seen < max_records:
        params = {
            "search": query,
            "filter": (f"from_publication_date:{year_from}-01-01,"
                       f"to_publication_date:{year_to}-12-31"),
            "per-page": min(200, max_records - seen),
            "cursor": cursor,
            "select": FIELDS_WITH_REFS if with_refs else FIELDS,
        }
        url = f"{BASE}?search={query}&cursor={cursor}"   # provenance label only
        page = fetch(BASE, params, use_cache=use_cache)
        results = page.get("results") or []
        if not results:
            return
        for w in results:
            yield _to_record(w, url)
            seen += 1
        cursor = (page.get("meta") or {}).get("next_cursor")


def count(query: str, year_from: int, year_to: int, *, use_cache: bool = True) -> int:
    """Total hits without paging through them — for the Search Log sheet."""
    page = fetch(BASE, {
        "search": query,
        "filter": (f"from_publication_date:{year_from}-01-01,"
                   f"to_publication_date:{year_to}-12-31"),
        "per-page": 1,
    }, use_cache=use_cache)
    return (page.get("meta") or {}).get("count", 0)


def by_doi(doi: str, *, use_cache: bool = True) -> Optional[Record]:
    doi = doi.replace("https://doi.org/", "").strip()
    try:
        w = fetch(f"{BASE}/doi:{doi}", {"select": FIELDS_WITH_REFS}, use_cache=use_cache)
    except Exception:
        return None
    return _to_record(w, f"{BASE}/doi:{doi}")


def by_id(openalex_id: str, *, use_cache: bool = True) -> Optional[Record]:
    oid = openalex_id.rsplit("/", 1)[-1]
    try:
        w = fetch(f"{BASE}/{oid}", {"select": FIELDS_WITH_REFS}, use_cache=use_cache)
    except Exception:
        return None
    return _to_record(w, f"{BASE}/{oid}")


def siblings(rec: Record, *, use_cache: bool = True) -> List[Record]:
    """Every OpenAlex record that is really the SAME work as `rec`.

    OpenAlex routinely holds one paper as several records — typically the
    preprint, the conference paper and the journal/"article" version — and it
    does NOT always merge their citation counts.

    Measured on M3ER (Mittal et al., AAAI 2020):

        W2997258743   article           256 citations
        W2987017338   conference-paper   21 citations   <- what the AAAI DOI resolves to
        W4288026349   preprint            1 citation

    Seeding forward-citation traversal from the DOI therefore reaches 21 of 278
    citing papers — it would silently miss 92% of the responders to the gap, and
    nothing in the output would reveal the loss. Any snowballing that starts from
    a DOI alone is unsound for this reason.

    Matching is on exact normalised title, which is safe here because the
    candidates are already restricted to OpenAlex's own results for that title.
    """
    if not rec.title:
        return [rec]

    # Commas, colons and pipes are OpenAlex filter-syntax delimiters, so a title
    # containing any of them is rejected at the API edge with a 400. M3ER's title
    # has both a colon and two commas — the very record that motivated this
    # function could not be looked up without stripping them first.
    safe = re.sub(r"[,:|!+]", " ", rec.title).strip()
    if not safe:
        return [rec]

    try:
        page = fetch(BASE, {
            "filter": f"title.search:{safe}",
            "per-page": 25,
            "select": FIELDS_WITH_REFS,
        }, use_cache=use_cache)
    except Exception:
        # A failed sibling lookup must degrade to "just this record" rather than
        # abort the whole traversal — but it also means T9's fan-out did not
        # happen for this seed.
        return [rec]

    want = rec.norm_title()
    out = {rec.source_id: rec}
    for w in (page.get("results") or []):
        cand = _to_record(w, f"{BASE}?filter=title.search:{safe[:40]}")
        if cand.norm_title() == want and cand.source_id not in out:
            out[cand.source_id] = cand
    return list(out.values())


def cited_by(openalex_id: str, year_from: int, year_to: int, *,
             max_records: int = 500, use_cache: bool = True) -> Iterator[Record]:
    """Papers that CITE this one — forward-citation traversal, method step 3.

    This is how a gap gets pinned: take a paper that states a limitation, then
    ask who responded to it. Without this the review can only report what authors
    admit about themselves.
    """
    oid = openalex_id.rsplit("/", 1)[-1]
    cursor, seen = "*", 0
    while cursor and seen < max_records:
        page = fetch(BASE, {
            "filter": (f"cites:{oid},"
                       f"from_publication_date:{year_from}-01-01,"
                       f"to_publication_date:{year_to}-12-31"),
            "per-page": min(200, max_records - seen),
            "cursor": cursor,
            "select": FIELDS,
        }, use_cache=use_cache)
        results = page.get("results") or []
        if not results:
            return
        for w in results:
            r = _to_record(w, f"{BASE}?filter=cites:{oid}")
            r.found_via = ["forward-cite"]
            yield r
            seen += 1
        cursor = (page.get("meta") or {}).get("next_cursor")
