"""
Generate the reading list as Markdown.

    python3 -m slr.reading_list                       # T1, to docs/slr/READING_LIST.md
    python3 -m slr.reading_list --tier T1,T2
    python3 -m slr.reading_list --out somewhere.md

WHAT IT IS
    A working document: every record awaiting screening, with a checkbox, a link
    where one exists, and the facts already extracted from its abstract. Ordered
    so the papers that matter most to this review come first.

    It does NOT say which to include. That judgement is the reviewer's, and this
    file exists to make it fast, not to make it for them.

ORDERING, AND WHY
    1. Papers reporting BOTH speaker-dependent and speaker-independent results.
       Six of them in T1. They are the nucleus of the ReQ5 finding, because the
       gap between those two numbers is the thing this thesis argues about.
    2. Papers mentioning edge deployment AND healthcare — the intersection the
       thesis occupies, and the ones most likely to challenge its novelty.
    3. Everything else, grouped by the Review Question its search string serves,
       most-cited first.

    Reading in that order means the papers that could change the argument are
    read while there is still time to change it.
"""
import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

from . import protocol as P

OUT = Path(__file__).resolve().parent / "out"
SCREENING = OUT / "screening.csv"
ACCESS = OUT / "access.csv"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "docs/slr/READING_LIST.md"

SD = re.compile(r"speaker[- ]dependent|subject[- ]dependent", re.I)
SI = re.compile(r"speaker[- ]independent|subject[- ]independent|"
                r"leave[- ]one[- ]speaker[- ]out|\bLOSO\b|cross[- ]subject", re.I)
EDGE = re.compile(r"\bedge\b|on[- ]device|embedded|Raspberry Pi|\bJetson\b|\bTinyML\b", re.I)
HEALTH = re.compile(r"\bclinical\b|\bpatient|healthcare|caregiv|\bnurs|dementia|"
                    r"mental health|\bhospital\b", re.I)
DATASETS = re.compile(r"\bIEMOCAP\b|\bRAVDESS\b|\bCREMA[- ]?D\b|\bMSP[- ]IMPROV\b|"
                      r"\bMSP[- ]Podcast\b|\bSAVEE\b|\bEMO[- ]?DB\b|\bTESS\b|\bMELD\b|"
                      r"\bMOSEI\b|\bMOSI\b|\bAffectNet\b|\bFER[- ]?2013\b|\bAFEW\b|"
                      r"\bCK\+|\bDEAP\b|\bSEED\b|\bWESAD\b|\beNTERFACE\b", re.I)
NO_MULTIMODAL = re.compile(r"multimodal|multi-modal|\bfusion\b|audio-?visual", re.I)
EMPIRICAL = re.compile(r"\baccuracy\b|\bF1\b|\bUAR\b|\brecall\b|\d{2}(?:\.\d+)?\s?%", re.I)


def load():
    if not SCREENING.exists():
        sys.exit(f"missing {SCREENING} — run `python3 -m slr.pipeline --run` first")
    with SCREENING.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["decision"] == "review"]
    links = {}
    if ACCESS.exists():
        with ACCESS.open(encoding="utf-8") as f:
            for a in csv.DictReader(f):
                if a.get("resolved") == "yes":
                    links[a["id"]] = (a.get("url") or a.get("landing_page") or "",
                                      a.get("version") or "")
    return rows, links


def link_for(r, links):
    if r["pdf_url"].strip():
        return r["pdf_url"].strip(), ""
    return links.get(r["id"], ("", ""))


def entry(r, links):
    text = f"{r['title']}. {r['abstract']}"
    url, ver = link_for(r, links)
    bits = []
    if r["year"]:
        bits.append(r["year"])
    if r["venue"]:
        bits.append(r["venue"][:46])
    if int(r["cited_by"] or 0):
        bits.append(f"cited {r['cited_by']}")

    L = [f"- [ ] **{r['id']}** · {r['title'].strip()}",
         f"      {' · '.join(bits)}"]
    if url:
        L.append(f"      [full text]({url})" + (f" — *{ver}*" if ver else ""))
    else:
        L.append("      **no open copy found** — request via library, or contact the author")

    ds = sorted({m.group(0).upper() for m in DATASETS.finditer(text)})
    notes = []
    if ds:
        notes.append("datasets: " + ", ".join(ds))
    if SD.search(text) and SI.search(text):
        notes.append("**reports speaker-dependent AND independent**")
    elif SI.search(text):
        notes.append("speaker-independent")
    if EDGE.search(text) and HEALTH.search(text):
        notes.append("**edge + healthcare**")
    if not NO_MULTIMODAL.search(text):
        notes.append("no multimodal/fusion language — check EC2")
    if not EMPIRICAL.search(text):
        notes.append("no results in abstract — check IC4")
    if not r["abstract"].strip():
        notes.append("**no abstract** — title-only")
    if notes:
        L.append(f"      {' · '.join(notes)}")
    return "\n".join(L)


def build(tiers):
    rows, links = load()
    rows = [r for r in rows if r["tier"] in tiers]
    rows.sort(key=lambda r: -int(r["cited_by"] or 0))
    total = len(rows)
    have = sum(1 for r in rows if link_for(r, links)[0])

    both = [r for r in rows if SD.search(f"{r['title']}. {r['abstract']}")
            and SI.search(f"{r['title']}. {r['abstract']}")]
    inter = [r for r in rows if r not in both
             and EDGE.search(f"{r['title']}. {r['abstract']}")
             and HEALTH.search(f"{r['title']}. {r['abstract']}")]
    seen = {r["id"] for r in both} | {r["id"] for r in inter}
    rest = [r for r in rows if r["id"] not in seen]

    L = []
    w = L.append
    w(f"# Reading list — {', '.join(sorted(tiers))}")
    w("")
    w(f"**{total} papers** awaiting my screening decision. "
      f"{have} have a link here ({have/total*100:.0f}%); the rest need a library "
      f"request or an author email.")
    w("")
    w("Generated from `slr/out/screening.csv`. Tick as I go; the decision itself is "
      "recorded with `python3 -m slr.screen_cli --tier T1`, which saves after every "
      "record.")
    w("")
    w("## The test every paper has to answer")
    w("")
    w(f"> {P.CENTRAL_THESIS}")
    w("")
    w("Does this paper **support** it, **challenge** it, or neither? Neither means "
      "background, or out.")
    w("")
    w("---")
    w("")

    if both:
        w(f"## 1. Read these first — {len(both)} papers reporting both evaluation conditions")
        w("")
        w("Each of these reports speaker-dependent *and* speaker-independent results for "
          "the same system. The gap between those two numbers is what ReQ5 is about "
          "(distinct from my own 66% val vs 55% test spread, where both splits were "
          "speaker-independent and the 11-point gap came from 3-actor fold variance).")
        w("")
        w("Read them with one question: **how far does accuracy fall when speakers are "
          "held out?** Record both numbers.")
        w("")
        for r in both:
            w(entry(r, links))
            w("")
        w("---")
        w("")

    if inter:
        w(f"## 2. Then these — {len(inter)} papers at the edge + healthcare intersection")
        w("")
        w("These sit closest to the space this thesis claims. They are the papers most "
          "likely to be raised as *hasn't this been done?*, so they are worth reading "
          "before the argument hardens rather than after.")
        w("")
        for r in inter:
            w(entry(r, links))
            w("")
        w("---")
        w("")

    w(f"## 3. The rest — {len(rest)} papers, grouped by Review Question")
    w("")
    w("Each paper appears under the Review Question its matched search string serves. "
      "A paper matching several strings appears under the first.")
    w("")
    by_req = defaultdict(list)
    str_to_req = {s["id"]: s["serves"] for s in P.SEARCH_STRINGS}
    for r in rest:
        ids = [x.strip() for x in r["matched_strings"].split(";") if x.strip()]
        reqs = str_to_req.get(ids[0], ["(via citation only)"]) if ids else ["(via citation only)"]
        by_req[reqs[0]].append(r)

    for req in list(P.REVIEW_QUESTIONS) + ["(via citation only)"]:
        group = by_req.get(req)
        if not group:
            continue
        qtext = P.REVIEW_QUESTIONS.get(req, "Found by citation traversal, not by a search string.")
        w(f"### {req} — {qtext}")
        w("")
        w(f"*{len(group)} papers*")
        w("")
        for r in group:
            w(entry(r, links))
            w("")
        w("")

    w("---")
    w("")
    w("## When a paper cannot be read")
    w("")
    w("Record it as excluded under **EC5 (inaccessible)**, not under a content criterion. "
      "Access-driven and content-driven exclusions are counted separately in the PRISMA "
      "flow, so an unreadable paper stays visible as an access limit rather than "
      "disappearing into a relevance judgement. This is threat T7, and it currently "
      "affects 24% of the working corpus.")
    w("")
    return "\n".join(L)


def main(argv=None):
    p = argparse.ArgumentParser(description="Generate the reading list")
    p.add_argument("--tier", default="T1")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    a = p.parse_args(argv)
    tiers = {t.strip().upper() for t in a.tier.split(",") if t.strip()}
    md = build(tiers)
    dest = Path(a.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(md)
    print(f"wrote {dest}  ({len(md.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
