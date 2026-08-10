"""
Snowballing — backward and forward citation traversal.

WHY THIS IS A SEPARATE RETRIEVAL METHOD, NOT A NICETY
    Step 3 of the gap-analysis method is "find who responded to the gap". A
    keyword search cannot do that: the responders often use different vocabulary
    from the paper they are answering. MulT does not describe itself as "fixing
    TFN's limitation"; you find that relationship by asking who CITES TFN.

    This is also the only mechanism that can distinguish the three gap types:

      type (a)  author-stated   — read the seed's own Limitations section
      type (b)  pinned by later papers — FORWARD citations: someone built on it
      type (c)  scope gap       — nobody in EITHER direction addresses it, which
                                  is a claim you can only make after looking

    Type (c) is the one that justifies this thesis, and a reviewer is entitled to
    ask how thoroughly you looked before claiming nobody had done it. This module
    is that answer.

BACKWARD = what the seed cites (its intellectual parents)
FORWARD  = what cites the seed (its responders)
"""
from typing import Dict, Iterable, List, Optional, Tuple

from .sources import openalex
from .sources.base import Record


def forward(seed_doi_or_id: str, year_from: int, year_to: int, *,
            max_records: int = 500, use_cache: bool = True
            ) -> Tuple[Optional[Record], List[Record]]:
    """Papers that cite the seed. Returns (seed_record, citing_records).

    Traverses EVERY OpenAlex record for the work, not just the one the DOI
    resolves to. OpenAlex splits a paper across preprint / conference / journal
    records without always merging their citation counts, so a DOI-only seed can
    reach a small minority of the true responders — 21 of 278 in the M3ER case
    that motivated this. See openalex.siblings().
    """
    seed = (openalex.by_doi(seed_doi_or_id, use_cache=use_cache)
            if "/" in seed_doi_or_id and not seed_doi_or_id.startswith("W")
            else openalex.by_id(seed_doi_or_id, use_cache=use_cache))
    if seed is None:
        return None, []

    citing, seen = [], set()
    for sib in openalex.siblings(seed, use_cache=use_cache):
        for r in openalex.cited_by(sib.source_id, year_from, year_to,
                                   max_records=max_records, use_cache=use_cache):
            if r.source_id not in seen:
                seen.add(r.source_id)
                citing.append(r)
        # Report the fullest citation count we found, not the DOI record's.
        seed.cited_by_count = max(seed.cited_by_count, sib.cited_by_count)
        if len(seed.referenced_works) < len(sib.referenced_works):
            seed.referenced_works = sib.referenced_works
    return seed, citing


def backward(seed: Record, year_from: int, year_to: int, *,
             max_records: int = 200, use_cache: bool = True) -> List[Record]:
    """Papers the seed cites.

    OpenAlex gives referenced_works as bare IDs with no metadata, so each one
    costs a request. Capped, and the year filter is applied AFTER retrieval
    because the IDs carry no date — a pre-window reference still costs the call
    but is then dropped, which is why the cap matters.
    """
    out: List[Record] = []
    for oid in seed.referenced_works[:max_records]:
        rec = openalex.by_id(oid, use_cache=use_cache)
        if rec is None:
            continue
        if rec.year is not None and not (year_from <= rec.year <= year_to):
            continue
        rec.found_via = ["backward-cite"]
        out.append(rec)
    return out


def snowball(seeds: Iterable[Tuple[str, str]], year_from: int, year_to: int, *,
             do_backward: bool = True, do_forward: bool = True,
             max_forward: int = 300, max_backward: int = 100,
             use_cache: bool = True, log=print) -> Tuple[List[Record], Dict[str, dict]]:
    """Traverse from every seed. Returns (records, per-seed report).

    The report is what goes in the Search Log sheet: PRISMA requires records
    identified via "other methods" to be counted separately from database
    searching, and this is that count.
    """
    records: List[Record] = []
    report: Dict[str, dict] = {}

    for doi, label in seeds:
        entry = {"label": label, "doi": doi, "resolved": False, "openalex_records": 0,
                 "forward": 0, "backward": 0, "cited_by_count": 0}
        seed = openalex.by_doi(doi, use_cache=use_cache)
        if seed is None:
            entry["error"] = "not resolvable in OpenAlex"
            report[doi] = entry
            log(f"  [seed] {label}: NOT FOUND ({doi})")
            continue

        entry["resolved"] = True
        entry["title"] = seed.title

        if do_forward:
            # forward() fans out across every OpenAlex record for this work.
            seed, fwd = forward(doi, year_from, year_to,
                                max_records=max_forward, use_cache=use_cache)
            records += fwd
            entry["forward"] = len(fwd)
            entry["openalex_records"] = len(openalex.siblings(seed, use_cache=use_cache))
        entry["cited_by_count"] = seed.cited_by_count

        if do_backward:
            bwd = backward(seed, year_from, year_to,
                           max_records=max_backward, use_cache=use_cache)
            records += bwd
            entry["backward"] = len(bwd)

        report[doi] = entry
        log(f"  [seed] {label}: {entry['forward']} forward, {entry['backward']} backward "
            f"(cited {seed.cited_by_count}x total)")

    return records, report
