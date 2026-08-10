"""
Duplicate detection and record merging.

WHY THIS IS NOT TRIVIAL
    PRISMA requires "records removed before screening: duplicates" as a hard
    number, and that number is only defensible if the rule producing it is
    stated. Four sources overlap heavily: the same paper can appear as an
    OpenAlex work, a Crossref DOI, a PubMed record and an arXiv preprint — four
    rows, four different identifiers, one paper.

THREE PASSES, IN ORDER OF CONFIDENCE
    1. DOI exact (after normalisation). Unambiguous.
    2. Normalised title + year within +/- 1. Catches the preprint-to-published
       case, where the DOI legitimately differs and the year usually shifts by
       one. The year guard is what stops two genuinely different papers that
       share a generic title ("Speech Emotion Recognition") from collapsing.
    3. Normalised title alone, ONLY where one side has no year at all. Without
       this, a record missing its year can never merge with anything.

MERGE POLICY — EC4
    "keep the peer-reviewed version of a preprint/published pair, recording the
    preprint as a merged alias". So the canonical record is the non-preprint one;
    the preprint's identifier survives in `merged_from` rather than vanishing,
    because an examiner may ask what the duplicate count is made of.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .sources.base import Record

# Preference order when choosing which record survives a merge. OpenAlex first
# because it is the only source carrying OA status and references, both of which
# later stages need; arXiv last because it is the one that fails IC3.
SOURCE_RANK = {"openalex": 0, "pubmed": 1, "crossref": 2, "arxiv": 3}


@dataclass
class Merged:
    record: Record
    merged_from: List[str] = field(default_factory=list)   # "source:id" of absorbed rows
    sources: List[str] = field(default_factory=list)


def _better(a: Record, b: Record) -> Record:
    """Which of two records for the same work should survive?"""
    # EC4: a peer-reviewed version always beats a preprint.
    if a.is_preprint != b.is_preprint:
        return b if a.is_preprint else a
    ra, rb = SOURCE_RANK.get(a.source, 9), SOURCE_RANK.get(b.source, 9)
    if ra != rb:
        return a if ra < rb else b
    # Same source rank: prefer the record that can actually be screened.
    return a if len(a.abstract) >= len(b.abstract) else b


def _absorb(keep: Record, drop: Record) -> None:
    """Move any information the loser has and the winner lacks.

    A merge must never LOSE data. Crossref may hold the DOI that OpenAlex is
    missing; arXiv may hold the only readable PDF; PubMed may hold the abstract
    that IEEE never deposited. Field-by-field, best-of-both.
    """
    if not keep.doi and drop.doi:
        keep.doi = drop.doi
    if len(drop.abstract) > len(keep.abstract):
        keep.abstract = drop.abstract
    if not keep.pdf_url and drop.pdf_url:
        keep.pdf_url = drop.pdf_url
    if not keep.oa_status and drop.oa_status:
        keep.oa_status = drop.oa_status
    if not keep.venue and drop.venue:
        keep.venue = drop.venue
    if not keep.venue_type and drop.venue_type:
        keep.venue_type = drop.venue_type
    if not keep.language and drop.language:
        keep.language = drop.language
    if not keep.year and drop.year:
        keep.year = drop.year
    if len(drop.authors) > len(keep.authors):
        keep.authors = drop.authors
    if len(drop.referenced_works) > len(keep.referenced_works):
        keep.referenced_works = drop.referenced_works
    # Citation counts differ by source methodology; keep the highest and treat it
    # as an indicator, never as a precise figure.
    keep.cited_by_count = max(keep.cited_by_count, drop.cited_by_count)
    # A record found by BOTH a search string and a citation trail is stronger
    # evidence, not weaker — union rather than overwrite.
    keep.matched_strings = sorted(set(keep.matched_strings) | set(drop.matched_strings))
    keep.found_via = sorted(set(keep.found_via) | set(drop.found_via))
    # If either side is a published version, the merged work is not a preprint.
    keep.is_preprint = keep.is_preprint and drop.is_preprint


def deduplicate(records: List[Record]) -> Tuple[List[Merged], int]:
    """Returns (unique merged records, number of duplicate rows removed)."""
    merged: List[Merged] = [Merged(record=r, sources=[r.source]) for r in records]

    # ── pass 1: DOI ──
    merged = _pass(merged, lambda r: r.norm_doi() or None)

    # ── pass 2: title + year (+/- 1) ──
    merged = _pass_title_year(merged)

    # ── pass 3: title alone, only when a year is missing ──
    merged = _pass(merged, lambda r: r.norm_title() if (r.norm_title() and not r.year) else None,
                   also_match_titled=True)

    removed = len(records) - len(merged)
    return merged, removed


def _collapse_group(group: List[Merged]) -> Merged:
    winner = group[0]
    for other in group[1:]:
        keep_rec = _better(winner.record, other.record)
        drop = other if keep_rec is winner.record else winner
        keep = winner if keep_rec is winner.record else other
        _absorb(keep.record, drop.record)
        keep.merged_from += drop.merged_from + [f"{drop.record.source}:{drop.record.source_id}"]
        keep.sources = sorted(set(keep.sources) | set(drop.sources))
        winner = keep
    return winner


def _pass(items: List[Merged], key_fn, also_match_titled: bool = False) -> List[Merged]:
    buckets: Dict[object, List[Merged]] = defaultdict(list)
    unkeyed: List[Merged] = []
    for m in items:
        k = key_fn(m.record)
        if k is None:
            unkeyed.append(m)
        else:
            buckets[k].append(m)

    if also_match_titled:
        # A yearless record should be able to merge into an existing titled one.
        titled: Dict[str, Merged] = {}
        for m in unkeyed:
            t = m.record.norm_title()
            if t:
                titled.setdefault(t, m)
        out, absorbed = [], set()
        for k, group in buckets.items():
            host = titled.get(k)
            if host is not None:
                group = [host] + group
                absorbed.add(id(host))
            out.append(_collapse_group(group))
        out += [m for m in unkeyed if id(m) not in absorbed]
        return out

    return unkeyed + [_collapse_group(g) for g in buckets.values()]


def _pass_title_year(items: List[Merged]) -> List[Merged]:
    """Same normalised title, years within 1 of each other.

    Grouped by title first, then partitioned by year proximity inside the group
    so that a 2019 preprint and its 2020 paper merge while a 2016 and a 2023
    paper sharing a generic title do not.
    """
    by_title: Dict[str, List[Merged]] = defaultdict(list)
    untitled: List[Merged] = []
    for m in items:
        t = m.record.norm_title()
        # Very short titles are too collision-prone to merge on.
        (by_title[t] if len(t) >= 12 else untitled).append(m)

    out = list(untitled)
    for group in by_title.values():
        if len(group) == 1:
            out.append(group[0])
            continue
        group.sort(key=lambda m: (m.record.year or 0))
        cluster = [group[0]]
        for m in group[1:]:
            prev = cluster[-1].record.year or 0
            cur = m.record.year or 0
            if prev and cur and abs(cur - prev) > 1:
                out.append(_collapse_group(cluster))
                cluster = [m]
            else:
                cluster.append(m)
        out.append(_collapse_group(cluster))
    return out
