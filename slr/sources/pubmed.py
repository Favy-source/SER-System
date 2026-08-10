"""
PubMed / MEDLINE adapter (NCBI E-utilities).

ROLE IN THE REVIEW
    PubMed is database D5 in the protocol and is the ONLY source that indexes the
    clinical literature properly. It is where ReQ4 (dataset representativeness in
    healthcare settings) and the healthcare-deployment half of ReQ6 have to be
    answered — an engineering-only corpus would systematically miss the papers
    that report what actually happens when affective computing meets a ward.

    Unlike OpenAlex and Crossref, PubMed accepts real Boolean queries, so the
    protocol string is TRANSLATED faithfully via booleanq.to_pubmed() with [tiab]
    field tags rather than flattened. matches() is still applied locally so every
    source ends up filtered by the identical predicate.

    Two-step protocol, as NCBI requires: esearch returns PMIDs, efetch returns
    the records. Batched at 200 to stay well inside the 3-requests-per-second
    limit for unauthenticated clients.

API: https://www.ncbi.nlm.nih.gov/books/NBK25501/
"""
import xml.etree.ElementTree as ET
from typing import Iterator, List, Optional

from .base import Record, classify_venue, fetch

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
BATCH = 200


def _text(node, path, default="") -> str:
    el = node.find(path)
    return "".join(el.itertext()).strip() if el is not None else default


def _year(article) -> Optional[int]:
    y = _text(article, ".//Journal/JournalIssue/PubDate/Year")
    if y.isdigit():
        return int(y)
    # Older records carry a free-text MedlineDate like "2015 Nov-Dec" instead.
    md = _text(article, ".//Journal/JournalIssue/PubDate/MedlineDate")
    for tok in md.split():
        if tok[:4].isdigit():
            return int(tok[:4])
    return None


def _abstract(article) -> str:
    """Structured abstracts split into labelled sections; join them in order.

    Dropping the labels loses nothing for Boolean matching and avoids emitting
    "BACKGROUND: ... METHODS: ..." noise into the screening sheet.
    """
    parts = []
    for el in article.findall(".//Abstract/AbstractText"):
        txt = "".join(el.itertext()).strip()
        if txt:
            parts.append(txt)
    return " ".join(parts)


def _to_record(pa, url: str) -> Record:
    article = pa.find(".//Article")
    if article is None:
        return None

    pmid = _text(pa, ".//PMID")
    doi = ""
    for aid in pa.findall(".//ArticleIdList/ArticleId"):
        if aid.get("IdType") == "doi":
            doi = (aid.text or "").strip()
            break

    authors = []
    for a in article.findall(".//AuthorList/Author"):
        last, fore = _text(a, "LastName"), _text(a, "ForeName")
        name = " ".join(x for x in (fore, last) if x) or _text(a, "CollectiveName")
        if name:
            authors.append(name)

    venue = _text(article, ".//Journal/Title")
    ptypes = [(_text(p, ".") or "") for p in article.findall(".//PublicationType")]

    return Record(
        source="pubmed",
        source_id=pmid,
        title=_text(article, "ArticleTitle"),
        abstract=_abstract(article),
        year=_year(article),
        doi=doi,
        authors=authors,
        venue=venue,
        venue_type=classify_venue(venue, "journal" if venue else ""),
        language=_text(article, "Language").lower(),
        oa_status="",
        pdf_url="",
        # PubMed does not report citation counts; 0 here means "not reported",
        # which the pipeline records rather than treating as a real zero.
        cited_by_count=0,
        is_preprint=any("preprint" in p.lower() for p in ptypes),
        raw_url=url,
    )


def esearch(query: str, year_from: int, year_to: int, *,
            max_records: int = 1000, use_cache: bool = True) -> List[str]:
    """Return PMIDs. `query` must already be in PubMed Boolean syntax."""
    term = f'({query}) AND ("{year_from}"[dp] : "{year_to}"[dp])'
    ids, retstart = [], 0
    while retstart < max_records:
        res = fetch(f"{EUTILS}/esearch.fcgi", {
            "db": "pubmed", "term": term, "retmode": "json",
            "retmax": min(BATCH, max_records - retstart), "retstart": retstart,
        }, use_cache=use_cache)
        block = (res or {}).get("esearchresult") or {}
        got = block.get("idlist") or []
        ids.extend(got)
        total = int(block.get("count", 0))
        retstart += len(got)
        if not got or retstart >= total:
            break
    return ids


def efetch(pmids: List[str], *, use_cache: bool = True) -> Iterator[Record]:
    for i in range(0, len(pmids), BATCH):
        chunk = pmids[i:i + BATCH]
        url = f"{EUTILS}/efetch.fcgi?id={chunk[0]}...+{len(chunk)}"
        xml = fetch(f"{EUTILS}/efetch.fcgi", {
            "db": "pubmed", "id": ",".join(chunk), "retmode": "xml",
        }, parse="text", use_cache=use_cache)
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            continue          # a malformed batch must not kill the whole search
        for pa in root.findall(".//PubmedArticle"):
            rec = _to_record(pa, url)
            if rec:
                yield rec


def search(query: str, year_from: int, year_to: int, *,
           max_records: int = 1000, use_cache: bool = True) -> Iterator[Record]:
    ids = esearch(query, year_from, year_to, max_records=max_records, use_cache=use_cache)
    yield from efetch(ids, use_cache=use_cache)


def count(query: str, year_from: int, year_to: int, *, use_cache: bool = True) -> int:
    term = f'({query}) AND ("{year_from}"[dp] : "{year_to}"[dp])'
    res = fetch(f"{EUTILS}/esearch.fcgi", {
        "db": "pubmed", "term": term, "retmode": "json", "retmax": 0,
    }, use_cache=use_cache)
    return int(((res or {}).get("esearchresult") or {}).get("count", 0))
