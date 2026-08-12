"""
Interactive title/abstract screening.

    python3 -m slr.screen_cli                  # start/resume, highest tier first
    python3 -m slr.screen_cli --tier T1        # just the strongest candidates
    python3 -m slr.screen_cli --stats          # progress, no screening
    python3 -m slr.screen_cli --review-mine    # re-read your own decisions

WHAT THIS IS AND IS NOT
    It is a reading harness. It shows you one record at a time with the protocol
    criteria within reach, and records what YOU decide plus the reason.

    It is not a classifier. It never suggests include/exclude and never fills a
    decision in for you. slr/screen.py already removed everything mechanically
    impossible to include; what remains needs judgement, and that judgement is
    my contribution to the review. An examiner will ask who made
    these calls, and "a script" is not an answer.

RESUMABILITY
    Decisions append to out/decisions.csv as you make them, one row per record,
    flushed immediately. Screening 2,000 records is days of work spread over
    sittings, and a crash on day three must not cost day two. Re-running picks
    up exactly where you stopped.

WHY REASONS ARE MANDATORY ON EXCLUDE
    PRISMA requires exclusions at full-text stage to be reported with reasons,
    and a reason written months later is a reconstruction, not a record. The
    prompt asks while the paper is still in front of you.
"""
import argparse
import csv
import shutil
import sys
import textwrap
from datetime import datetime
from pathlib import Path

from . import protocol

OUT = Path(__file__).resolve().parent / "out"
SCREENING = OUT / "screening.csv"
DECISIONS = OUT / "decisions.csv"

DEC_COLS = ["id", "decision", "ec_code", "reason", "note", "tier", "year",
            "title", "doi", "decided_at"]

TIER_ORDER = {"T1": 0, "T2": 1, "T3": 2, "T4": 3}


# ── display ────────────────────────────────────────────────

def width():
    return min(shutil.get_terminal_size((100, 30)).columns, 100)


def rule(ch="─"):
    return ch * width()


def wrap(text, indent=""):
    return textwrap.fill(text or "", width=width() - len(indent),
                         initial_indent=indent, subsequent_indent=indent)


def show_criteria():
    print("\n" + rule("═"))
    print("INCLUSION — all must hold")
    for k, v in protocol.INCLUSION.items():
        print(wrap(f"{k}  {v}", "  "))
    print("\nEXCLUSION — any one excludes")
    for k, v in protocol.EXCLUSION.items():
        print(wrap(f"{k}  {v}", "  "))
    print("\nTHE INCLUSION TEST — does this paper support or challenge:")
    print(wrap(protocol.CENTRAL_THESIS, "  "))
    print(rule("═"))


def show_record(rec, n, total, done):
    print("\n" + rule("═"))
    pct = (done / total * 100) if total else 0
    print(f"[{rec['id']}]  tier {rec['tier']}   —   {done}/{total} screened ({pct:.1f}%)")
    print(rule())
    print(wrap(rec["title"], ""))
    print()
    meta = [rec.get("year") or "?", rec.get("venue") or "venue unknown",
            f"cited {rec.get('cited_by') or 0}",
            f"OA: {rec.get('oa_status') or 'unknown'}"]
    print(wrap(" · ".join(str(m) for m in meta), "  "))
    authors = rec.get("authors") or ""
    if authors:
        short = "; ".join(authors.split("; ")[:4]) + ("; …" if authors.count(";") >= 4 else "")
        print(wrap(short, "  "))
    print()
    print(wrap(f"satisfies: {rec.get('matched_strings') or '(none — via citation)'}", "  "))
    if rec.get("flags"):
        print(wrap(f"flags: {rec['flags']}", "  "))
    if rec.get("pdf_url"):
        print(wrap(f"pdf: {rec['pdf_url'][:88]}", "  "))
    elif rec.get("_oa_url"):
        # Resolved by slr/access.py rather than supplied by the search. The
        # version is shown because an accepted manuscript is not the version of
        # record — page numbers and wording can differ, and a quotation must be
        # attributed to the version it actually came from.
        v = rec.get("_oa_version") or "version unstated"
        print(wrap(f"pdf: {rec['_oa_url'][:88]}", "  "))
        print(wrap(f"     ^ found open access ({v})", "  "))
    elif rec.get("_oa_checked"):
        print(wrap("pdf: none found — checked Unpaywall and arXiv (threat T7)", "  "))
    if rec.get("doi"):
        print(wrap(f"doi: {rec['doi']}", "  "))
    print(rule("┈"))
    abstract = (rec.get("abstract") or "").strip()
    print(wrap(abstract if abstract else "*** NO ABSTRACT — screen on title only, "
                                         "or retrieve the full text ***", "  "))
    print(rule())


PROMPT = ("  [i]nclude  [e]xclude  [m]aybe  [s]kip  "
          "[c]riteria  [b]ack  [q]uit  > ")


# ── io ─────────────────────────────────────────────────────

def load_screening():
    if not SCREENING.exists():
        sys.exit(f"missing {SCREENING} — run `python3 -m slr.pipeline --run` first")
    with SCREENING.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["decision"] == "review"]

    # Layer on anything slr/access.py resolved. Kept as a SEPARATE file rather
    # than written back into screening.csv, because the pipeline regenerates
    # screening.csv wholesale and would erase it. Same reasoning as decisions.csv.
    access = OUT / "access.csv"
    if access.exists():
        with access.open(encoding="utf-8") as f:
            found = {r["id"]: r for r in csv.DictReader(f)}
        for r in rows:
            a = found.get(r["id"])
            if not a:
                continue
            r["_oa_checked"] = "1"
            if a.get("resolved") == "yes":
                r["_oa_url"] = a.get("url") or a.get("landing_page") or ""
                r["_oa_version"] = a.get("version") or ""
    return rows


def load_decisions():
    if not DECISIONS.exists():
        return {}
    with DECISIONS.open(encoding="utf-8") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def append_decision(row):
    """Append and flush. A sitting's work must survive a crash in the next one."""
    new = not DECISIONS.exists()
    OUT.mkdir(parents=True, exist_ok=True)
    with DECISIONS.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=DEC_COLS)
        if new:
            w.writeheader()
        w.writerow(row)
        f.flush()


def ask(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return "q"


# ── stats ──────────────────────────────────────────────────

def stats():
    recs = load_screening()
    dec = load_decisions()
    from collections import Counter
    by_tier = Counter(r["tier"] for r in recs)
    done_tier = Counter(dec[r["id"]]["tier"] for r in recs if r["id"] in dec)
    outcome = Counter(d["decision"] for d in dec.values())

    print(f"\n{len(recs)} records awaiting screening, {len(dec)} decided "
          f"({len(dec)/max(1,len(recs))*100:.1f}%)\n")
    print(f"  {'tier':5s} {'done':>7s} {'total':>7s}   {'':20s}")
    for t in sorted(by_tier, key=lambda x: TIER_ORDER.get(x, 9)):
        d, tot = done_tier.get(t, 0), by_tier[t]
        bar = "█" * int(20 * d / tot) if tot else ""
        print(f"  {t:5s} {d:>7d} {tot:>7d}   {bar:20s} {d/tot*100:5.1f}%")
    if outcome:
        print("\n  your decisions:")
        for k, v in outcome.most_common():
            print(f"    {k:9s} {v:>6d}")
        ec = Counter(d["ec_code"] for d in dec.values() if d.get("ec_code"))
        if ec:
            print("\n  exclusion reasons:")
            for k, v in ec.most_common():
                print(f"    {k:9s} {v:>6d}  {protocol.EXCLUSION.get(k, '')[:52]}")
    print()


# ── main loop ──────────────────────────────────────────────

def run(tier_filter=None, limit=None):
    recs = load_screening()
    if tier_filter:
        recs = [r for r in recs if r["tier"] in tier_filter]
    recs.sort(key=lambda r: (TIER_ORDER.get(r["tier"], 9), -int(r.get("cited_by") or 0)))

    dec = load_decisions()
    todo = [r for r in recs if r["id"] not in dec]
    if not todo:
        print("\nNothing left to screen in this selection.\n")
        return stats()

    print(f"\n{len(todo)} to screen ({len(dec)} already decided). "
          f"Decisions save as you go — quit any time.\n")
    print("Reminder: this tool records YOUR judgement. It never decides for you.")

    total = len(recs)
    i, history = 0, []
    while i < len(todo):
        rec = todo[i]
        show_record(rec, i, total, len(dec))
        choice = ask(PROMPT).lower()

        if choice in ("q", "quit"):
            break
        if choice in ("c", "criteria", "?"):
            show_criteria()
            continue
        if choice in ("b", "back"):
            if history:
                i = history.pop()
                print("  (going back — re-deciding overwrites nothing until you choose)")
            else:
                print("  already at the first record")
            continue
        if choice in ("s", "skip"):
            history.append(i)
            i += 1
            continue

        if choice in ("i", "include"):
            note = ask("  note (optional, e.g. why it matters): ")
            row = {"decision": "include", "ec_code": "", "reason": "", "note": note}
        elif choice in ("m", "maybe"):
            note = ask("  what would settle it? ")
            row = {"decision": "maybe", "ec_code": "", "reason": "", "note": note}
        elif choice in ("e", "exclude"):
            print("   " + "  ".join(f"[{k}]" for k in protocol.EXCLUSION))
            ec = ask("  exclusion code: ").upper()
            while ec not in protocol.EXCLUSION:
                if ec in ("", "q"):
                    ec = None
                    break
                print(f"    not a code. one of: {', '.join(protocol.EXCLUSION)}")
                ec = ask("  exclusion code: ").upper()
            if ec is None:
                continue
            reason = ask("  reason (required — PRISMA reports these): ")
            while not reason:
                reason = ask("  reason (required): ")
            row = {"decision": "exclude", "ec_code": ec, "reason": reason, "note": ""}
        else:
            print("  ? unrecognised — i / e / m / s / c / b / q")
            continue

        row.update({
            "id": rec["id"], "tier": rec["tier"], "year": rec.get("year", ""),
            "title": rec["title"][:200], "doi": rec.get("doi", ""),
            "decided_at": datetime.now().isoformat(timespec="seconds"),
        })
        append_decision(row)
        dec[rec["id"]] = row
        history.append(i)
        i += 1

    print(f"\nSaved to {DECISIONS}")
    stats()


def review_mine():
    dec = load_decisions()
    if not dec:
        return print("\nNo decisions recorded yet.\n")
    for d in sorted(dec.values(), key=lambda x: x["id"]):
        mark = {"include": "+", "exclude": "-", "maybe": "?"}.get(d["decision"], " ")
        print(f"{mark} [{d['id']}] {d['tier']} {d['year']}  {d['title'][:66]}")
        if d.get("ec_code"):
            print(f"      {d['ec_code']}: {d['reason'][:80]}")
        elif d.get("note"):
            print(f"      note: {d['note'][:80]}")


def main(argv=None):
    p = argparse.ArgumentParser(description="Interactive SLR screening")
    p.add_argument("--tier", default="", help="comma-separated, e.g. T1 or T1,T2")
    p.add_argument("--stats", action="store_true", help="progress only")
    p.add_argument("--review-mine", action="store_true", help="list your decisions")
    args = p.parse_args(argv)

    if args.stats:
        return stats()
    if args.review_mine:
        return review_mine()
    tiers = {t.strip().upper() for t in args.tier.split(",") if t.strip()} or None
    return run(tiers)


if __name__ == "__main__":
    sys.exit(main() or 0)
