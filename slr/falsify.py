"""
The falsification test — a conjunction ladder.

    python3 -m slr.falsify              # runs S7, the protocol's falsification string
    python3 -m slr.falsify --string S3
    python3 -m slr.falsify --json out/falsification.json

THE PROBLEM THIS SOLVES
    S7 is a seven-way conjunction and it returns ZERO. Run as a single query that
    looks like a failure. It is not: it is the point.

    A type-(c) scope gap is the claim "nobody has done all of these things at
    once". You cannot support that claim by asserting it, and you cannot support
    it with a single zero either — a zero is equally consistent with the query
    being broken, which is exactly what a reviewer will suspect first.

    What supports it is a LADDER. Run the full conjunction; then drop one clause
    at a time and re-count. The result is a table that says, with numbers:

        all 7 clauses          ->    0     nobody does all of this
        without privacy        ->   14     14 papers do everything but privacy
        without healthcare     ->    9     ...
        without edge           ->    2     ...

    Now the zero is evidence rather than an absence, because you have shown the
    query works when relaxed, and you have identified WHICH constraint is doing
    the excluding. That last part is the real prize: the binding clause names
    the thing the field has not combined, and that is the gap the thesis fills.

WHAT IT CANNOT TELL YOU
    A count of zero is a claim about the SEARCHED corpus, not about reality. It
    is bounded by the sources, the window, and the vocabulary of the clauses.
    The output therefore reports the survivors of each rung so they can be read,
    because a single genuine counter-example — as with Mutheeswaran et al. 2026
    against Research RQ3 — matters more than any count.
"""
import argparse
import json
import sys
from itertools import combinations
from pathlib import Path
from typing import Dict, List

from . import booleanq, protocol
from .booleanq import And, Node, Or, Term
from .dedupe import deduplicate
from .sources import arxiv, crossref, openalex
from .sources import pubmed as pubmed_src
from .sources.base import Record, SourceError

OUT = Path(__file__).resolve().parent / "out"


def clause_label(c: Node) -> str:
    """A short human name for a clause, for the ladder table."""
    ts = booleanq.terms(c)
    if not ts:
        return "?"
    head = ts[0].text + ("*" if ts[0].wildcard else "")
    return head if len(ts) == 1 else f"{head} (+{len(ts) - 1})"


def retrieve_pool(node: Node, *, max_per_source: int = 300,
                  sources=("openalex", "crossref", "pubmed", "arxiv"),
                  use_cache: bool = True, log=print) -> List[Record]:
    """Build ONE candidate pool, retrieved with the MOST RELAXED form of the query.

    The whole ladder is then evaluated locally against this single pool. That is
    deliberate: if each rung issued its own API query, the rungs would be drawn
    from different candidate pools and their counts would not be comparable —
    a lower rung could return fewer records than a higher one purely because the
    API ranked things differently. One pool, many predicates, comparable counts.
    """
    mods = {"openalex": openalex, "crossref": crossref,
            "pubmed": pubmed_src, "arxiv": arxiv}
    clauses = node.children if isinstance(node, And) else [node]

    # The pool must SPAN every dimension of the conjunction. Retrieving on the
    # topic clause alone ("emotion recognition") produced 1,082 generic papers in
    # which every rung of the ladder scored zero — a pool that cannot distinguish
    # "the field has not combined these" from "my pool never contained edge or
    # clinical work in the first place", which makes the ladder uninformative.
    #
    # So one probe per clause: topic AND that clause. Each probe guarantees the
    # pool contains papers that are strong on that specific dimension, which is
    # what the drop-one rungs need in order to release anything.
    topic = clauses[1] if len(clauses) > 1 else clauses[0]
    probes = [(f"topic x {clause_label(c)}", And([topic, c]))
              for i, c in enumerate(clauses) if c is not topic]

    pool: List[Record] = []
    per_probe = max(60, max_per_source // max(1, len(probes)))
    for label, probe in probes:
        log(f"  probe: {label}")
        for name in sources:
            mod = mods[name]
            if name == "openalex":
                q = booleanq.to_openalex(probe)
            elif name == "pubmed":
                q = booleanq.to_pubmed(probe)
            elif name == "arxiv":
                q = booleanq.to_arxiv(probe)
            else:
                q = booleanq.api_query(probe)
            try:
                got = list(mod.search(q, protocol.YEAR_MIN, protocol.YEAR_MAX,
                                      max_records=per_probe, use_cache=use_cache))
            except SourceError as e:
                log(f"    {name}: FAILED ({e})")
                continue
            log(f"    {name}: {len(got)}")
            pool += got

    merged, dupes = deduplicate(pool)
    log(f"  pool: {len(pool)} retrieved, {dupes} duplicates -> {len(merged)} unique")
    return [m.record for m in merged]


def ladder(node: Node, pool: List[Record], *, depth: int = 0) -> Dict:
    """Full conjunction, then every drop-k subset, deepening until something gives.

    `depth=0` means AUTO: keep dropping more clauses until some rung is non-zero.
    A ladder in which every rung is zero proves nothing — it is equally consistent
    with a broken query — so the ladder must descend far enough to show the search
    working. That descent is the whole evidential value.
    """
    clauses = list(node.children) if isinstance(node, And) else [node]
    labels = [clause_label(c) for c in clauses]
    max_k = len(clauses) - 1

    def survivors(idxs_dropped):
        keep = [c for i, c in enumerate(clauses) if i not in idxs_dropped]
        pred = And(keep) if len(keep) > 1 else keep[0]
        return [r for r in pool if pred.matches(r.searchable())]

    full = survivors(set())
    rungs, reached, auto = [], 0, (depth <= 0)
    limit = max_k if auto else min(depth, max_k)
    for k in range(1, limit + 1):
        for combo in combinations(range(len(clauses)), k):
            surv = survivors(set(combo))
            rungs.append({
                "dropped": [labels[i] for i in combo],
                "dropped_idx": list(combo),
                "n_clauses": len(clauses) - k,
                "count": len(surv),
                "examples": [{"title": r.title, "year": r.year, "doi": r.doi,
                              "venue": r.venue, "cited_by": r.cited_by_count}
                             for r in sorted(surv, key=lambda x: -(x.cited_by_count or 0))[:5]],
            })
        reached = k
        # In auto mode stop as soon as a rung releases something: that is the
        # shallowest depth at which the search demonstrably works.
        if auto and any(r["count"] > 0 for r in rungs):
            break
    rungs.sort(key=lambda r: (-r["count"], len(r["dropped"])))

    # A clause is only "binding" if relaxing it actually RELEASES papers. With
    # every rung at zero there is no binding clause, and claiming one would be
    # reading structure into noise.
    drop1 = [r for r in rungs if len(r["dropped"]) == 1 and r["count"] > 0]
    binding = max(drop1, key=lambda r: r["count"]) if drop1 else None
    informative = any(r["count"] > 0 for r in rungs)

    return {
        "clauses": labels,
        "pool_size": len(pool),
        "depth_reached": reached,
        "informative": informative,
        "full_conjunction": {
            "count": len(full),
            "survivors": [{"title": r.title, "year": r.year, "doi": r.doi,
                           "venue": r.venue, "cited_by": r.cited_by_count}
                          for r in full],
        },
        "binding_clause": (None if binding is None else {
            "clause": binding["dropped"][0],
            "papers_released": binding["count"],
            "interpretation": (
                f"Relaxing '{binding['dropped'][0]}' alone releases "
                f"{binding['count']} paper{'' if binding['count'] == 1 else 's'}. "
                f"That clause is the constraint the literature has not satisfied "
                f"in combination with the others."),
        }),
        "rungs": rungs,
    }


def render(result: Dict, log=print):
    log("")
    log(f"CONJUNCTION LADDER — pool of {result['pool_size']} unique candidate papers")
    log("")
    log(f"  {'clauses':>7}  {'n':>5}   dropped")
    log(f"  {'-'*7}  {'-'*5}   {'-'*60}")
    n = len(result["clauses"])
    log(f"  {n:>7}  {result['full_conjunction']['count']:>5}   (none — the full conjunction)")
    for r in result["rungs"]:
        log(f"  {r['n_clauses']:>7}  {r['count']:>5}   without {', '.join(r['dropped'])}")

    full = result["full_conjunction"]
    log("")
    if full["count"] == 0 and not result["informative"]:
        # The dangerous case. Every rung is zero, so the ladder has NOT shown the
        # search working, and the top-level zero is unsupported. Saying otherwise
        # would be the exact error this tool exists to prevent: presenting an
        # absence of evidence as evidence of absence.
        log("  LADDER IS UNINFORMATIVE — every rung returned zero.")
        log("  This does NOT support a scope-gap claim. A zero at every depth is")
        log("  equally consistent with a pool that never contained the relevant")
        log("  papers, or with clause vocabulary that matches nothing.")
        log("  Fix the pool or the clause wording before citing this result.")
    elif full["count"] == 0:
        log("  FULL CONJUNCTION RETURNS ZERO.")
        log(f"  Supported: relaxing the conjunction DOES release papers (first at "
            f"depth {result['depth_reached']}), so the search demonstrably works and")
        log("  the zero reflects the literature. This is evidence for a type-(c)")
        log("  scope gap.")
    else:
        log(f"  FULL CONJUNCTION RETURNS {full['count']} — the scope gap does NOT hold as stated.")
        log("  Read these before making any 'nobody has done this' claim:")
        for s in full["survivors"][:10]:
            log(f"    - {s['year']}  {s['title'][:80]}")
            log(f"      {s['venue'][:60]}  doi:{s['doi']}")

    b = result.get("binding_clause")
    if b:
        log("")
        log(f"  BINDING CLAUSE: {b['clause']}")
        log(f"  {b['interpretation']}")

    log("")
    log("  CAVEAT: a count of zero is a claim about the searched corpus, not about")
    log("  reality. It is bounded by the sources, the 2015-2026 window and the")
    log("  vocabulary of these clauses. One genuine counter-example outweighs it.")


def main(argv=None):
    p = argparse.ArgumentParser(description="Conjunction-ladder falsification test")
    p.add_argument("--string", default="S7", help="protocol search string ID (default S7)")
    p.add_argument("--depth", type=int, default=2, help="max clauses to drop at once")
    p.add_argument("--max-per-source", type=int, default=300)
    p.add_argument("--json", default="", help="also write the full result here")
    p.add_argument("--no-cache", action="store_true")
    args = p.parse_args(argv)

    entry = next((s for s in protocol.SEARCH_STRINGS if s["id"] == args.string.upper()), None)
    if entry is None:
        p.error(f"no such search string: {args.string}")

    print(f"{entry['id']} — {entry['purpose'][:100]}", flush=True)
    print(f"serves {', '.join(entry['serves'])}\n", flush=True)

    node = booleanq.parse(entry["string"])
    if not isinstance(node, And):
        p.error(f"{entry['id']} is not a conjunction; a ladder needs ANDed clauses")

    print("Building the candidate pool (relaxed retrieval, one pool for all rungs):",
          flush=True)
    pool = retrieve_pool(node, max_per_source=args.max_per_source,
                         use_cache=not args.no_cache)

    result = ladder(node, pool, depth=args.depth)
    result["string_id"] = entry["id"]
    result["purpose"] = entry["purpose"]
    result["serves"] = entry["serves"]
    result["protocol_string"] = entry["string"]
    render(result)

    OUT.mkdir(parents=True, exist_ok=True)
    dest = Path(args.json) if args.json else OUT / f"falsification_{entry['id']}.json"
    dest.write_text(json.dumps(result, indent=2))
    print(f"\n  written: {dest}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
