"""
Search -> normalise -> dedupe -> auto-screen -> export.

RUN
    python3 -m slr.pipeline --dry-run                  # query plan, no network
    python3 -m slr.pipeline --run                      # full pilot
    python3 -m slr.pipeline --run --strings S1,S6 --sources openalex,pubmed
    python3 -m slr.pipeline --run --snowball           # + citation traversal
    python3 -m slr.pipeline --counts                   # hit counts only, cheap

OUTPUTS (slr/out/)
    search_log.csv   one row per source x string: hits, retrieved, kept
    screening.csv    one row per unique record, ready for manual screening
    prisma.json      the PRISMA 2020 identification and screening numbers
    records.jsonl    full normalised records, for the extraction stage

WHAT THIS DOES AND DOES NOT DECIDE
    It identifies, deduplicates, and removes only what mechanically cannot be
    included. Every surviving record lands in screening.csv with decision
    "review" and a blank `my_decision` column for the reviewer to fill in.
    The include/exclude judgement stays human — see slr/screen.py.

REPRODUCIBILITY — AND ITS LIMIT
    Every API response is cached under slr/cache/ (gitignored). Once the cache
    exists, re-running reproduces the identical corpus, and prisma.json refers to
    that fixed snapshot rather than to whatever the databases hold today.

    The limit, stated because it was measured rather than assumed: the FIRST
    fetch is at the mercy of live API behaviour. Two runs of this pipeline
    differed by ~2,000 retrieved records with zero errors logged, because arXiv
    served transient empty pages mid-result-set and pagination accepted them as
    the end of the results. That specific cause is fixed (sources/arxiv.py
    re-checks against opensearch:totalResults before stopping), but the general
    point stands: a cold run is reproducible only up to API weather.

    The practical consequence for the review is that the cache IS the primary
    evidence. Preserve it alongside the outputs, and treat a cold re-run as a
    new search that needs its own Search Log row, not as a replication.
"""
import argparse
import csv
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Dict, List

from . import booleanq, protocol
from .dedupe import deduplicate
from .screen import screen_all
from .sources import arxiv, crossref, openalex
from .sources import pubmed as pubmed_src
from .sources.base import Record, SourceError, cache_stats

OUT = Path(__file__).resolve().parent / "out"

SOURCES = {
    "openalex": ("D1", openalex),
    "crossref": ("D2", crossref),
    "pubmed":   ("D3", pubmed_src),
    "arxiv":    ("D4", arxiv),
}


def log(msg: str = ""):
    """Flush every line: these runs are long and a buffered log is useless
    when you need to see where a search stalled."""
    print(msg, flush=True)


def query_for(source: str, string: str) -> str:
    """Each API gets the best query form it can actually honour.

    OpenAlex, PubMed and arXiv all accept real Boolean, so each receives a
    faithful translation of the protocol string in its own dialect. Only
    Crossref lacks Boolean support (query.bibliographic is OR-with-ranking), so
    it receives a bag-of-words query and leans on relevance ordering.

    In every case matches() re-applies the exact protocol predicate locally, so
    the four sources are subject to an identical final filter regardless of what
    their APIs can express.
    """
    if source == "openalex":
        return booleanq.to_openalex(string)
    if source == "pubmed":
        return booleanq.to_pubmed(string)
    if source == "arxiv":
        return booleanq.to_arxiv(string)
    return booleanq.api_query(string)


# ── stages ─────────────────────────────────────────────────

def run_search(sources: List[str], strings: List[dict], *,
               max_per_source: int, use_cache: bool = True) -> (List[Record], List[dict]):
    records: List[Record] = []
    search_log: List[dict] = []
    today = date.today().isoformat()

    for s in strings:
        for name in sources:
            db_code, mod = SOURCES[name]
            q = query_for(name, s["string"])
            row = {
                "date": today, "database": name, "db_code": db_code,
                "string_id": s["id"], "serves_ReQ": ", ".join(s["serves"]),
                "purpose": s["purpose"],
                "protocol_string": s["string"],
                "query_sent": q,
                "filters": f"{protocol.YEAR_MIN}-{protocol.YEAR_MAX}",
                "hits_reported": "", "retrieved": 0, "matched_predicate": 0,
                "notes": "",
            }
            log(f"[{s['id']}/{name}] {q[:110]}")
            t0 = time.time()
            try:
                got = list(mod.search(q, protocol.YEAR_MIN, protocol.YEAR_MAX,
                                      max_records=max_per_source, use_cache=use_cache))
            except SourceError as e:
                row["notes"] = f"FAILED: {e}"
                log(f"    !! {e}")
                search_log.append(row)
                continue

            kept = 0
            for r in got:
                if booleanq.matches(s["string"], r.title, r.abstract):
                    r.matched_strings = [s["id"]]
                    r.found_via = ["search"]
                    records.append(r)
                    kept += 1

            row["retrieved"] = len(got)
            row["matched_predicate"] = kept
            # Hit counts come free from the same cached page for OpenAlex and
            # Crossref; asking arXiv/PubMed again would cost another request.
            row["hits_reported"] = len(got) if len(got) < max_per_source else f">={len(got)}"
            search_log.append(row)
            log(f"    {len(got)} retrieved -> {kept} satisfy {s['id']}  "
                f"({time.time() - t0:.1f}s)")

    return records, search_log


def run_snowball(strings: List[dict], *, use_cache: bool = True):
    from . import citations
    log("\n== Snowballing (PRISMA 'other methods') ==")
    recs, report = citations.snowball(
        protocol.SNOWBALL_SEEDS, protocol.YEAR_MIN, protocol.YEAR_MAX,
        use_cache=use_cache, log=log)
    log(f"  -> {len(recs)} records from citation traversal")
    return recs, report


# ── screening tiers ────────────────────────────────────────
#
# The pilot leaves ~1,700 records for manual screening, of which a large slice
# arrived ONLY because they cite a seed paper. Screening them in retrieval order
# would mean working through hundreds of loosely-related citing papers before
# reaching the records that satisfy the protocol directly.
#
# Tiers give that work a defensible order. They are a READING ORDER, not a
# decision and not a ranking of quality — every tier is screened, and a T4 record
# can still be included. The tier is recorded in the CSV so the order is
# reproducible and can be reported.

TIERS = {
    "T1": "satisfies 2+ protocol strings, retrieved by search — strongest candidates",
    "T2": "satisfies 1 protocol string, retrieved by search",
    "T3": "satisfies a protocol string, reached via citation traversal",
    "T4": "reached via citation traversal only, satisfies no string — widest net",
    "X":  "auto-excluded; no manual screening needed",
}


def tier_of(s) -> str:
    if s.decision != "review":
        return "X"
    n = len(s.record.matched_strings)
    by_search = "search" in s.record.found_via
    if n >= 2 and by_search:
        return "T1"
    if n >= 1 and by_search:
        return "T2"
    if n >= 1:
        return "T3"
    return "T4"


def _tier_key(s):
    order = {"T1": 0, "T2": 1, "T3": 2, "T4": 3, "X": 4}
    return (order[tier_of(s)], -(s.record.cited_by_count or 0))


def export(screened, search_log, prisma, snowball_report=None):
    OUT.mkdir(parents=True, exist_ok=True)

    # ── search_log.csv ──
    if search_log:
        with (OUT / "search_log.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(search_log[0].keys()))
            w.writeheader()
            w.writerows(search_log)

    # ── screening.csv ──
    screened = sorted(screened, key=_tier_key)
    cols = ["id", "tier", "decision", "criterion", "reason", "suggestion", "flags",
            "title", "authors", "year", "venue", "venue_type", "doi",
            "oa_status", "pdf_url", "cited_by", "sources", "merged_from",
            "matched_strings", "found_via", "abstract",
            # left blank on purpose — these are the reviewer's columns
            "my_TA_decision", "my_TA_reason", "my_fulltext_decision", "my_EC_code",
            "notes"]
    with (OUT / "screening.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for i, s in enumerate(screened, 1):
            r = s.record
            w.writerow({
                "id": f"R{i:04d}", "tier": tier_of(s),
                "decision": s.decision, "criterion": s.criterion,
                "reason": s.reason, "suggestion": s.suggestion,
                "flags": "; ".join(s.flags),
                "title": r.title, "authors": "; ".join(r.authors[:8]),
                "year": r.year or "", "venue": r.venue, "venue_type": r.venue_type,
                "doi": r.doi, "oa_status": r.oa_status, "pdf_url": r.pdf_url,
                "cited_by": r.cited_by_count,
                "sources": "; ".join(s.sources),
                "merged_from": "; ".join(s.merged_from),
                "matched_strings": "; ".join(r.matched_strings),
                "found_via": "; ".join(r.found_via),
                "abstract": (r.abstract or "")[:4000],
                "my_TA_decision": "", "my_TA_reason": "",
                "my_fulltext_decision": "", "my_EC_code": "", "notes": "",
            })

    # ── records.jsonl ──
    with (OUT / "records.jsonl").open("w", encoding="utf-8") as f:
        for s in screened:
            f.write(json.dumps(s.record.to_dict()) + "\n")

    # ── prisma.json ──
    if snowball_report:
        prisma["snowball_seeds"] = snowball_report
    (OUT / "prisma.json").write_text(json.dumps(prisma, indent=2))


def build_prisma(n_raw_db, n_raw_other, n_dupes, screened) -> dict:
    by_criterion = Counter(s.criterion for s in screened if s.decision == "auto-exclude")
    reviewable = [s for s in screened if s.decision == "review"]
    flag_counts = Counter(f for s in reviewable for f in s.flags)
    by_string = Counter(sid for s in reviewable for sid in s.record.matched_strings)
    by_year = Counter(s.record.year for s in reviewable if s.record.year)

    tiers = Counter(tier_of(s) for s in screened)
    return {
        "generated": date.today().isoformat(),
        "protocol_version": protocol.VERSION,
        "screening_tiers": {
            "counts": {k: tiers.get(k, 0) for k in ("T1", "T2", "T3", "T4", "X")},
            "meaning": TIERS,
            "note": ("A reading order for manual screening, not a decision and not a "
                     "quality ranking. Every tier is screened; a T4 record can still "
                     "be included."),
        },
        "window": [protocol.YEAR_MIN, protocol.YEAR_MAX],
        "identification": {
            "records_from_databases": n_raw_db,
            "records_from_other_methods": n_raw_other,
            "total_identified": n_raw_db + n_raw_other,
            "duplicates_removed": n_dupes,
            "records_after_deduplication": n_raw_db + n_raw_other - n_dupes,
        },
        "automated_screening": {
            "auto_excluded_total": sum(by_criterion.values()),
            "auto_excluded_by_criterion": dict(by_criterion),
            "records_awaiting_manual_screening": len(reviewable),
            "note": ("Automated screening applies MECHANICAL criteria only "
                     "(IC2 year, IC5 language, EC3 non-human/synthesis, EC5 "
                     "non-archival, and the protocol Boolean predicate). No "
                     "record is auto-included; IC3, IC4, EC1 and EC2 require "
                     "the reviewer's judgement."),
        },
        "reviewable_corpus": {
            "by_search_string": dict(sorted(by_string.items())),
            "by_year": dict(sorted(by_year.items())),
            "stratified": {
                "2015_2019": sum(v for k, v in by_year.items() if 2015 <= k <= 2019),
                "2020_2026": sum(v for k, v in by_year.items() if 2020 <= k <= 2026),
            },
            "flags": dict(flag_counts),
        },
        "threats_evidence": {
            "screened_on_title_only": flag_counts.get("abstract_missing", 0),
            "language_unreported": flag_counts.get("language_unreported", 0),
            "access_unknown": flag_counts.get("access_unknown", 0),
            "preprint_only": flag_counts.get("preprint_only", 0),
            "single_reviewer": True,
            "note": ("These figures populate the Threats to Validity sheet with "
                     "measured numbers rather than generic statements."),
        },
        "cache": cache_stats(),
    }


# ── CLI ────────────────────────────────────────────────────

def dry_run(sources, strings):
    log(f"SLR pilot — protocol v{protocol.VERSION}, window "
        f"{protocol.YEAR_MIN}-{protocol.YEAR_MAX}")
    log(f"{len(strings)} search strings x {len(sources)} sources "
        f"= {len(strings) * len(sources)} queries\n")
    for s in strings:
        log(f"--- {s['id']}  (serves {', '.join(s['serves'])}) — {s['purpose'][:70]}")
        log(f"    protocol: {s['string'][:150]}")
        try:
            ast = booleanq.parse(s["string"])
            log(f"    parsed:   {len(booleanq.terms(ast))} terms, OK")
        except ValueError as e:
            log(f"    parsed:   *** PARSE ERROR: {e} ***")
            continue
        for name in sources:
            log(f"    {name:9s} {query_for(name, s['string'])[:130]}")
        log("")
    log(f"Snowball seeds: {len(protocol.SNOWBALL_SEEDS)}")
    for doi, label in protocol.SNOWBALL_SEEDS:
        log(f"    {doi:32s} {label}")
    log(f"\nCache: {cache_stats()}")


def counts_only(sources, strings, use_cache=True):
    log(f"{'string':7s} {'source':10s} {'hits':>10s}   purpose")
    total = defaultdict(int)
    for s in strings:
        for name in sources:
            _, mod = SOURCES[name]
            try:
                n = mod.count(query_for(name, s["string"]),
                              protocol.YEAR_MIN, protocol.YEAR_MAX, use_cache=use_cache)
            except SourceError as e:
                log(f"{s['id']:7s} {name:10s} {'ERROR':>10s}   {e}")
                continue
            total[name] += n
            log(f"{s['id']:7s} {name:10s} {n:>10,}   {s['purpose'][:50]}")
    log("")
    for name, n in total.items():
        log(f"TOTAL {name:10s} {n:>10,}")


def main(argv=None):
    p = argparse.ArgumentParser(description="SLR search pipeline")
    p.add_argument("--dry-run", action="store_true", help="print the query plan, no network")
    p.add_argument("--counts", action="store_true", help="hit counts only (1 request per query)")
    p.add_argument("--run", action="store_true", help="execute the full pipeline")
    p.add_argument("--sources", default="openalex,crossref,pubmed,arxiv")
    p.add_argument("--strings", default="", help="comma-separated IDs, e.g. S1,S6")
    p.add_argument("--max-per-source", type=int, default=300,
                   help="cap per source per string (pilot default keeps runs short)")
    p.add_argument("--snowball", action="store_true", help="also traverse citations")
    p.add_argument("--no-cache", action="store_true", help="bypass the disk cache")
    args = p.parse_args(argv)

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    bad = [s for s in sources if s not in SOURCES]
    if bad:
        p.error(f"unknown source(s): {bad}. Choose from {list(SOURCES)}")

    strings = protocol.SEARCH_STRINGS
    if args.strings:
        want = {x.strip().upper() for x in args.strings.split(",")}
        strings = [s for s in strings if s["id"] in want]
        if not strings:
            p.error(f"no search strings matched {sorted(want)}")

    if args.dry_run:
        dry_run(sources, strings)
        return 0
    if args.counts:
        counts_only(sources, strings, use_cache=not args.no_cache)
        return 0
    if not args.run:
        p.print_help()
        return 1

    use_cache = not args.no_cache
    t0 = time.time()

    log(f"== Searching: {len(strings)} strings x {len(sources)} sources ==")
    records, search_log = run_search(sources, strings,
                                     max_per_source=args.max_per_source,
                                     use_cache=use_cache)
    n_db = len(records)

    snow_report = None
    if args.snowball:
        snow_recs, snow_report = run_snowball(strings, use_cache=use_cache)
        records += snow_recs
    n_other = len(records) - n_db

    log(f"\n== Deduplicating {len(records)} records ==")
    merged, n_dupes = deduplicate(records)
    log(f"  {n_dupes} duplicates removed -> {len(merged)} unique works")

    log("\n== Automated screening (mechanical criteria only) ==")
    screened = screen_all(merged, strings, protocol.YEAR_MIN, protocol.YEAR_MAX)
    excluded = [s for s in screened if s.decision == "auto-exclude"]
    review = [s for s in screened if s.decision == "review"]
    for crit, n in Counter(s.criterion for s in excluded).most_common():
        log(f"  auto-excluded {n:5d}  {crit}")
    log(f"  -> {len(review)} records await YOUR screening decision")

    prisma = build_prisma(n_db, n_other, n_dupes, screened)
    export(screened, search_log, prisma, snow_report)

    log(f"\n== Done in {time.time() - t0:.0f}s ==")
    log(f"  {OUT / 'search_log.csv'}")
    log(f"  {OUT / 'screening.csv'}   <- screen this one")
    log(f"  {OUT / 'prisma.json'}")
    log(f"  {OUT / 'records.jsonl'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
