"""
Extract the decision-relevant facts from each record, so screening is fast.

    python3 -m slr.prescreen --tier T1            # write the briefs
    python3 -m slr.prescreen --tier T1 --print    # read them in the terminal

THE LINE THIS MODULE DOES NOT CROSS
    It reports what a record SAYS. It never says what to do about it.

    Screening decisions are the reviewer's contribution to a systematic review,
    and an examiner will ask who made them. So there is no "recommended
    decision" field here and there never should be — a column of suggestions,
    clicked through 277 times, is the same thing as the tool deciding.

    What it removes is the tedium: most of the 90 seconds a record takes is
    spent hunting an abstract for six facts that are always the same six facts.
    Those are surfaced here, each tagged with the criterion it bears on, with
    the sentence it came from so the reviewer can check rather than trust.

WHY EVERY FACT CARRIES ITS EVIDENCE
    A fact without its source is a claim the reviewer has to take on faith, and
    keyword matching is wrong often enough that faith is misplaced. Quoting the
    matched fragment means a wrong extraction is visible in half a second
    instead of propagating into the extraction sheet.
"""
import argparse
import csv
import re
import sys
import textwrap
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
SCREENING = OUT / "screening.csv"
BRIEFS = OUT / "prescreen.csv"


def rx(*alts):
    return re.compile("|".join(alts), re.I)


# Each probe: (label, criterion it bears on, pattern)
PROBES = [
    ("modalities: speech/audio", "IC5", rx(r"\bspeech\b", r"\baudio\b", r"\bacoustic\b",
                                           r"\bvocal\b", r"\bprosod")),
    ("modalities: face/visual", "IC5", rx(r"\bfacial\b", r"\bface\b", r"\bvisual\b",
                                          r"\bexpression\b")),
    ("modalities: text", "EC2", rx(r"\btext\b", r"\btranscript", r"\blinguistic\b",
                                   r"\blexical\b")),
    ("modalities: physiological", "IC5", rx(r"\bEEG\b", r"\bECG\b", r"\bGSR\b", r"\bEDA\b",
                                            r"physiolog", r"heart rate", r"\bPPG\b")),
    ("modalities: body/pose", "IC5", rx(r"\bposture\b", r"\bgesture\b", r"\bskeletal\b",
                                        r"\bbody\b", r"\bgait\b")),
    ("multimodal / fusion", "IC3", rx(r"multimodal", r"multi-modal", r"\bfusion\b",
                                      r"audio-?visual")),
    ("empirical results", "IC4", rx(r"\baccuracy\b", r"\bF1\b", r"\bUAR\b", r"\brecall\b",
                                    r"\bprecision\b", r"we (?:achieve|obtain|report)",
                                    r"\d{2}(?:\.\d+)?\s?%")),
    ("review / survey", "IC4", rx(r"\bsurvey\b", r"systematic review", r"\bwe review\b",
                                  r"this review", r"\btaxonomy\b")),
    ("unimodal baseline", "EC2", rx(r"unimodal", r"single[- ]modal", r"compared? (?:with|to) "
                                    r"(?:the )?(?:audio|visual|speech)[- ]only")),
    ("healthcare / caregiving", "IC3", rx(r"\bclinical\b", r"\bpatient", r"healthcare",
                                          r"caregiv", r"\bnurs", r"dementia",
                                          r"mental health", r"\bhospital\b", r"\btherap")),
    ("evaluation protocol", "IC4", rx(r"speaker[- ]independent", r"subject[- ]independent",
                                      r"leave[- ]one[- ]speaker[- ]out", r"\bLOSO\b",
                                      r"cross[- ]corpus", r"\bk[- ]fold\b",
                                      r"cross[- ]validation", r"train(?:ing)?[/ ]test")),
    ("real-time / latency", "IC3", rx(r"real[- ]time", r"\blatency\b", r"inference time",
                                      r"\bms\b")),
    ("edge / on-device", "IC3", rx(r"\bedge\b", r"on[- ]device", r"embedded",
                                   r"Raspberry Pi", r"\bJetson\b", r"\bTinyML\b")),
    ("privacy / ethics", "IC4", rx(r"\bprivacy\b", r"\bethic", r"\bconsent\b",
                                   r"federated", r"\bGDPR\b")),
    ("non-human subject", "EC3", rx(r"\bcattle\b", r"\bcanine\b", r"\bmice\b", r"\brodent",
                                    r"\banimal\b", r"\bprimate\b", r"livestock")),
    ("synthesis / generation", "EC3", rx(r"speech synthesis", r"text[- ]to[- ]speech",
                                         r"\bTTS\b", r"talking head", r"face generation",
                                         r"voice conversion")),
]

DATASETS = rx(r"\bIEMOCAP\b", r"\bRAVDESS\b", r"\bCREMA[- ]?D\b", r"\bMSP[- ]IMPROV\b",
              r"\bMSP[- ]Podcast\b", r"\bSAVEE\b", r"\bEMO[- ]?DB\b", r"\bTESS\b",
              r"\bMELD\b", r"\bMOSEI\b", r"\bMOSI\b", r"\bAffectNet\b", r"\bFER[- ]?2013\b",
              r"\bAFEW\b", r"\bCK\+", r"\bDEAP\b", r"\bSEED\b", r"\bWESAD\b",
              r"\beNTERFACE\b")


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]


def evidence_for(pattern, sents, cap=120):
    """The sentence fragment that triggered a match, so it can be checked."""
    for s in sents:
        m = pattern.search(s)
        if m:
            start = max(0, m.start() - 40)
            frag = s[start:m.end() + 60].strip()
            return ("…" if start else "") + " ".join(frag.split())[:cap]
    return ""


def brief(rec):
    text = f"{rec['title']}. {rec['abstract']}"
    sents = sentences(text)
    facts = []
    for label, crit, pattern in PROBES:
        if pattern.search(text):
            facts.append({"fact": label, "criterion": crit,
                          "evidence": evidence_for(pattern, sents)})
    ds = sorted(set(m.group(0) for m in DATASETS.finditer(text)))
    return facts, ds


def render(rec, facts, ds, width=96):
    w = lambda t, i="  ": textwrap.fill(t, width, initial_indent=i, subsequent_indent=i)
    out = [f"\n[{rec['id']}] {rec['tier']} · {rec['year']} · cited {rec['cited_by']}",
           w(rec["title"], ""),
           w(f"{rec['venue'] or 'venue unknown'} · satisfies {rec['matched_strings']}")]
    if ds:
        out.append(w(f"datasets named: {', '.join(ds)}"))
    if not rec["abstract"].strip():
        out.append(w("*** NO ABSTRACT — nothing below was extractable ***"))
    out.append("")
    for f in facts:
        out.append(w(f"[{f['criterion']}] {f['fact']}"))
        if f["evidence"]:
            out.append(w(f'"{f["evidence"]}"', "        "))
    missing = [lbl for lbl, _, pat in PROBES
               if lbl.startswith(("empirical", "multimodal", "evaluation"))
               and not pat.search(f"{rec['title']}. {rec['abstract']}")]
    if missing:
        out.append(w(f"NOT FOUND in the abstract: {', '.join(missing)}"))
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description="Extract decision-relevant facts per record")
    p.add_argument("--tier", default="T1")
    p.add_argument("--print", action="store_true", dest="show")
    p.add_argument("--limit", type=int, default=None)
    a = p.parse_args(argv)

    if not SCREENING.exists():
        sys.exit(f"missing {SCREENING}")
    tiers = {t.strip().upper() for t in a.tier.split(",") if t.strip()}
    with SCREENING.open(encoding="utf-8") as f:
        recs = [r for r in csv.DictReader(f)
                if r["decision"] == "review" and r["tier"] in tiers]
    recs.sort(key=lambda r: -int(r["cited_by"] or 0))
    if a.limit:
        recs = recs[:a.limit]

    rows = []
    for r in recs:
        facts, ds = brief(r)
        if a.show:
            print(render(r, facts, ds))
        rows.append({
            "id": r["id"], "tier": r["tier"], "year": r["year"],
            "cited_by": r["cited_by"], "title": r["title"],
            "datasets": "; ".join(ds),
            "facts": " | ".join(f"[{f['criterion']}] {f['fact']}" for f in facts),
            "evidence": " || ".join(f'{f["fact"]}: "{f["evidence"]}"'
                                    for f in facts if f["evidence"]),
            "no_abstract": "" if r["abstract"].strip() else "YES",
        })

    OUT.mkdir(parents=True, exist_ok=True)
    with BRIEFS.open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    print(f"\nwrote {BRIEFS} — {len(rows)} briefs")
    print("These are facts, not recommendations. The include/exclude call is yours.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
