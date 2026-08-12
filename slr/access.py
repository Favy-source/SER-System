"""
Resolve legally-readable full text for records that arrived without a link.

    python3 -m slr.access --tier T1          # resolve the strongest candidates
    python3 -m slr.access --tier T1,T2
    python3 -m slr.access --stats            # coverage report, no network

WHY THIS EXISTS
    Threat T7 in the protocol is full-text access, and it is not abstract: with
    no institutional subscriptions, a paper this review cannot open is a paper it
    cannot quality-appraise. Of the 277 top-tier records, 118 arrived with no
    link at all.

    OpenAlex reports open-access status but often not a usable URL, and Crossref
    reports neither. Unpaywall exists precisely to close that gap — it indexes
    author manuscripts, repository copies and publisher OA versions against a
    DOI, and it is free.

WHAT THIS DOES NOT DO
    It never circumvents a paywall. It finds copies the publisher or author has
    already made openly available, and records honestly when none exists. A
    record that stays closed is reported as closed and becomes evidence for T7
    rather than a gap in the workflow.

    The VERSION matters and is recorded: an accepted manuscript is not the
    version of record, and quoting a page number from a preprint that shifted in
    proof is a citation error waiting to happen.
"""
import argparse
import csv
import sys
import time
from collections import Counter
from pathlib import Path

from .sources.base import CONTACT_EMAIL, RATE_LIMIT, SourceError, fetch

OUT = Path(__file__).resolve().parent / "out"
SCREENING = OUT / "screening.csv"
ACCESS = OUT / "access.csv"

UNPAYWALL = "https://api.unpaywall.org/v2"
RATE_LIMIT.setdefault("api.unpaywall.org", 0.15)

COLS = ["id", "doi", "tier", "title", "resolved", "oa_status", "version",
        "host_type", "url", "landing_page", "checked_at"]

READABLE = {"gold", "green", "hybrid", "bronze", "diamond"}


def resolve(doi: str, use_cache: bool = True) -> dict:
    """Ask Unpaywall for the best openly-available copy of a DOI."""
    doi = (doi or "").strip().lower()
    if not doi:
        return {"resolved": "no", "reason": "no DOI"}
    try:
        d = fetch(f"{UNPAYWALL}/{doi}", {"email": CONTACT_EMAIL}, use_cache=use_cache)
    except SourceError as e:
        return {"resolved": "error", "reason": str(e)[:80]}

    if not d or not d.get("is_oa"):
        return {"resolved": "no", "oa_status": (d or {}).get("oa_status") or "closed"}

    loc = d.get("best_oa_location") or {}
    return {
        "resolved": "yes",
        "oa_status": d.get("oa_status") or "",
        # "publishedVersion" is the version of record; "acceptedVersion" is the
        # author manuscript post-review; "submittedVersion" is a preprint. Page
        # numbers and even wording can differ, so the version is recorded and
        # must be cited accordingly.
        "version": loc.get("version") or "",
        "host_type": loc.get("host_type") or "",
        "url": loc.get("url_for_pdf") or loc.get("url") or "",
        "landing_page": loc.get("url_for_landing_page") or "",
    }


def _norm(t: str) -> str:
    import re
    import unicodedata
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def resolve_arxiv(title: str, use_cache: bool = True) -> dict:
    """Second route: an author preprint on arXiv, matched on exact title.

    Unpaywall indexes repositories and publisher OA, but this literature lives
    heavily on arXiv, and a great many closed IEEE and CVF papers have an author
    preprint there. Skipping this route would report papers as unreadable that
    are one search away.

    Matched on NORMALISED EXACT title, never fuzzily: a near-match would attach
    the wrong full text to a record, and a review that quality-appraises the
    wrong paper is worse than one that admits it could not read it.
    """
    from .sources import arxiv as _ax
    if not title or len(title) < 20:
        return {"resolved": "no"}
    words = [w for w in _norm(title).split() if len(w) > 2][:12]
    if len(words) < 4:
        return {"resolved": "no"}
    q = " AND ".join(f"all:{w}" for w in words)
    try:
        hits = list(_ax.search(q, 1900, 2100, max_records=12, use_cache=use_cache))
    except Exception:
        return {"resolved": "no"}
    want = _norm(title)
    for h in hits:
        if _norm(h.title) == want:
            return {"resolved": "yes", "oa_status": "green",
                    "version": "submittedVersion", "host_type": "repository",
                    "url": h.pdf_url or f"https://arxiv.org/abs/{h.source_id}",
                    "landing_page": f"https://arxiv.org/abs/{h.source_id}"}
    return {"resolved": "no"}


def load_targets(tiers):
    if not SCREENING.exists():
        sys.exit(f"missing {SCREENING} — run `python3 -m slr.pipeline --run` first")
    with SCREENING.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["decision"] == "review"]
    if tiers:
        rows = [r for r in rows if r["tier"] in tiers]
    # Only records that actually need help: no direct link already.
    return [r for r in rows if not r["pdf_url"].strip()]


def load_done():
    if not ACCESS.exists():
        return {}
    with ACCESS.open(encoding="utf-8") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def append(row):
    new = not ACCESS.exists()
    OUT.mkdir(parents=True, exist_ok=True)
    with ACCESS.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in COLS})
        f.flush()


def stats():
    if not SCREENING.exists():
        sys.exit("no screening.csv")
    with SCREENING.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["decision"] == "review"]
    done = load_done()
    print(f"\n{len(rows)} records awaiting screening\n")
    print(f"  {'tier':5s} {'total':>6s} {'direct':>7s} {'resolved':>9s} {'still closed':>13s}")
    for t in ("T1", "T2", "T3", "T4"):
        sub = [r for r in rows if r["tier"] == t]
        if not sub:
            continue
        direct = sum(1 for r in sub if r["pdf_url"].strip())
        res = sum(1 for r in sub if done.get(r["id"], {}).get("resolved") == "yes")
        closed = len(sub) - direct - res
        print(f"  {t:5s} {len(sub):>6d} {direct:>7d} {res:>9d} {closed:>13d}")
    if done:
        print("\n  versions found:")
        for k, v in Counter(d["version"] for d in done.values()
                            if d.get("resolved") == "yes").most_common():
            print(f"    {k or '(unstated)':22s} {v}")
        print("\n  hosted by:")
        for k, v in Counter(d["host_type"] for d in done.values()
                            if d.get("resolved") == "yes").most_common():
            print(f"    {k or '(unstated)':22s} {v}")
    print()


def run(tiers, limit=None, use_cache=True):
    targets = load_targets(tiers)
    done = load_done()
    todo = [r for r in targets if r["id"] not in done]
    if limit:
        todo = todo[:limit]
    if not todo:
        print("\nNothing left to resolve in this selection.\n")
        return stats()

    print(f"\nResolving open-access copies for {len(todo)} records "
          f"({len(done)} already checked). Results save as I go.\n")
    got = 0
    for i, rec in enumerate(todo, 1):
        r = resolve(rec["doi"], use_cache=use_cache)
        if r.get("resolved") != "yes":
            alt = resolve_arxiv(rec["title"], use_cache=use_cache)
            if alt.get("resolved") == "yes":
                r = {**r, **alt}
        row = {"id": rec["id"], "doi": rec["doi"], "tier": rec["tier"],
               "title": rec["title"][:150],
               "checked_at": time.strftime("%Y-%m-%d"), **r}
        append(row)
        if r.get("resolved") == "yes":
            got += 1
            print(f"  [{i}/{len(todo)}] {rec['id']} OK  {r.get('version','?'):18s} "
                  f"{(r.get('url') or '')[:64]}")
        elif i % 25 == 0:
            print(f"  [{i}/{len(todo)}] …{got} found so far")
    print(f"\nResolved {got} of {len(todo)}.")
    stats()


def main(argv=None):
    p = argparse.ArgumentParser(description="Find readable copies of paywalled records")
    p.add_argument("--tier", default="T1", help="comma-separated, e.g. T1 or T1,T2")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--stats", action="store_true")
    p.add_argument("--no-cache", action="store_true")
    a = p.parse_args(argv)
    if a.stats:
        return stats()
    tiers = {t.strip().upper() for t in a.tier.split(",") if t.strip()}
    return run(tiers, limit=a.limit, use_cache=not a.no_cache)


if __name__ == "__main__":
    sys.exit(main() or 0)
