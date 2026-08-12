"""
Descriptive counts over the retrieved corpus, organised by Review Question.

    python3 -m slr.synthesis              # print the tables
    python3 -m slr.synthesis --json out/synthesis.json

WHAT THESE NUMBERS ARE
    Signals read off TITLES AND ABSTRACTS of the 2,029 records awaiting
    screening. They say what the corpus talks about.

WHAT THEY ARE NOT — read this before quoting any of them
    They are not findings, and they must never be reported as "N% of studies
    use random splits". Abstracts systematically under-report method: most
    papers describe their train/test split in section 4, not in the abstract.
    So a paper counted here as "protocol not stated" may well state it on page
    six.

    Absence in an abstract is evidence about ABSTRACTS, not about practice.

    What the counts are legitimately good for:
      1. Prioritising extraction. A paper whose abstract already advertises
         "speaker-independent" is a cheap confirmation; one that says nothing is
         where the real reading has to happen.
      2. Generating the hypothesis that ReQ5 then tests properly on full texts.
      3. Sizing the work — knowing 1,700 papers need their protocol dug out by
         hand is a planning fact worth having early.

    The ReQ5 finding itself has to come from full-text extraction, on included
    papers only, recorded in the Data Extraction sheet's "Evaluation Protocol"
    column. This module tells you where to look, not what you found.
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
SCREENING = OUT / "screening.csv"


def pat(*alts):
    return re.compile("|".join(alts), re.I)


# ── ReQ5: evaluation protocol ──────────────────────────────
SPEAKER_INDEP = pat(r"speaker[- ]independent", r"subject[- ]independent",
                    r"leave[- ]one[- ]speaker[- ]out", r"\bLOSO\b",
                    r"speaker[- ]disjoint", r"cross[- ]subject")
CROSS_CORPUS = pat(r"cross[- ]corpus", r"cross[- ]dataset", r"cross[- ]domain")
SPEAKER_DEP = pat(r"speaker[- ]dependent", r"subject[- ]dependent")
GENERIC_SPLIT = pat(r"\bk[- ]fold\b", r"cross[- ]validation", r"train(?:ing)?[/ ]test",
                    r"\bhold[- ]out\b", r"\b\d0[/:]\d0 split\b", r"random split")
UAR = pat(r"unweighted average recall", r"\bUAR\b", r"unweighted accuracy",
          r"macro[- ]F1", r"weighted[- ]F1")

# ── ReQ4: datasets ─────────────────────────────────────────
DATASETS = {
    "IEMOCAP": pat(r"\bIEMOCAP\b"), "RAVDESS": pat(r"\bRAVDESS\b"),
    "CREMA-D": pat(r"\bCREMA[- ]?D\b"), "MSP-IMPROV": pat(r"\bMSP[- ]IMPROV\b"),
    "MSP-Podcast": pat(r"\bMSP[- ]Podcast\b"), "SAVEE": pat(r"\bSAVEE\b"),
    "EMO-DB": pat(r"\bEMO[- ]?DB\b", r"Berlin.{0,12}emotional"), "TESS": pat(r"\bTESS\b"),
    "MELD": pat(r"\bMELD\b"), "CMU-MOSEI": pat(r"\bMOSEI\b"), "CMU-MOSI": pat(r"\bMOSI\b"),
    "AffectNet": pat(r"\bAffectNet\b"), "FER2013": pat(r"\bFER[- ]?2013\b"),
    "AFEW": pat(r"\bAFEW\b"), "CK+": pat(r"\bCK\+"), "DEAP": pat(r"\bDEAP\b"),
    "SEED": pat(r"\bSEED\b"), "WESAD": pat(r"\bWESAD\b"),
    "eNTERFACE": pat(r"\beNTERFACE\b"), "EmoReact/wild": pat(r"in[- ]the[- ]wild"),
}
ACTED = pat(r"\bacted\b", r"\bposed\b", r"\bsimulated\b", r"\bscripted\b")
NATURAL = pat(r"\bspontaneous\b", r"naturalistic", r"in[- ]the[- ]wild",
              r"\becological validity\b", r"real[- ]world recording")

# ── ReQ3: fusion ───────────────────────────────────────────
FUSION = {
    "feature-level / early": pat(r"feature[- ]level", r"early fusion", r"concatenat"),
    "decision-level / late": pat(r"decision[- ]level", r"late fusion", r"score[- ]level"),
    "attention / cross-modal": pat(r"cross[- ]modal attention", r"co[- ]attention",
                                   r"attention[- ]based fusion", r"transformer fusion"),
    "tensor / bilinear": pat(r"tensor fusion", r"bilinear pool"),
    "hybrid": pat(r"hybrid fusion"),
    "graph": pat(r"graph[- ]based fusion", r"\bGNN\b", r"graph neural"),
}

# ── ReQ6: deployment, robustness, privacy ──────────────────
DEPLOY = {
    "edge / on-device": pat(r"\bedge\b", r"on[- ]device", r"embedded", r"Raspberry Pi",
                            r"\bJetson\b", r"\bTinyML\b"),
    "compression": pat(r"quantiz", r"quantis", r"prun", r"distill", r"compress"),
    "latency / real-time": pat(r"real[- ]time", r"\blatency\b", r"inference time"),
    "robustness": pat(r"\bnois", r"occlusion", r"\brobust"),
    "missing modality": pat(r"missing modalit", r"modality dropout", r"incomplete modalit"),
    "privacy / federated": pat(r"\bprivacy\b", r"federated", r"differential privacy"),
    "healthcare / clinical": pat(r"\bclinical\b", r"\bpatient", r"healthcare",
                                 r"caregiv", r"\bnurs", r"dementia", r"mental health"),
}


def load():
    if not SCREENING.exists():
        sys.exit(f"missing {SCREENING} — run `python3 -m slr.pipeline --run` first")
    with SCREENING.open(encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r["decision"] == "review"]


def table(title, counts, total, note=""):
    print(f"\n{title}")
    if note:
        print(f"  {note}")
    print(f"  {'':34s} {'n':>6s} {'% of corpus':>12s}")
    for k, v in counts:
        print(f"  {k:34s} {v:>6d} {v/total*100:>11.1f}%")


def main(argv=None):
    p = argparse.ArgumentParser(description="Descriptive counts by Review Question")
    p.add_argument("--json", default="")
    p.add_argument("--tier", default="", help="restrict, e.g. T1")
    a = p.parse_args(argv)

    recs = load()
    if a.tier:
        want = {t.strip().upper() for t in a.tier.split(",")}
        recs = [r for r in recs if r["tier"] in want]
    n = len(recs)
    txt = [f"{r['title']} {r['abstract']}" for r in recs]
    has_abs = sum(1 for r in recs if r["abstract"].strip())

    print(f"\n{'='*74}\nDESCRIPTIVE COUNTS — {n} records awaiting screening")
    print(f"{has_abs} have an abstract ({has_abs/n*100:.1f}%); "
          f"{n-has_abs} are title-only.")
    print("These are SIGNALS FROM ABSTRACTS, not findings. Abstracts under-report")
    print("method: a paper silent here may state its protocol on page six.")
    print("=" * 74)

    si  = sum(1 for t in txt if SPEAKER_INDEP.search(t))
    cc  = sum(1 for t in txt if CROSS_CORPUS.search(t))
    sd  = sum(1 for t in txt if SPEAKER_DEP.search(t))
    gs  = sum(1 for t in txt if GENERIC_SPLIT.search(t))
    uar = sum(1 for t in txt if UAR.search(t))
    silent = sum(1 for t in txt if not (SPEAKER_INDEP.search(t) or CROSS_CORPUS.search(t)
                                        or SPEAKER_DEP.search(t) or GENERIC_SPLIT.search(t)))
    table("ReQ5 — evaluation protocol mentioned in the abstract",
          [("speaker/subject-independent", si), ("cross-corpus or cross-dataset", cc),
           ("speaker/subject-dependent", sd),
           ("a split mentioned, kind unstated", gs),
           ("UAR / macro-F1 reported", uar),
           ("NOTHING about evaluation", silent)], n,
          note="The last row is where the reading effort goes — it is not a claim "
               "that those studies lack a protocol.")

    ds = sorted(((k, sum(1 for t in txt if rx.search(t))) for k, rx in DATASETS.items()),
                key=lambda x: -x[1])
    table("ReQ4 — datasets named in the abstract", [d for d in ds if d[1] > 0][:14], n)
    table("ReQ4 — elicitation language",
          [("acted / posed / scripted", sum(1 for t in txt if ACTED.search(t))),
           ("spontaneous / naturalistic / in-the-wild",
            sum(1 for t in txt if NATURAL.search(t)))], n)

    table("ReQ3 — fusion strategy named in the abstract",
          sorted(((k, sum(1 for t in txt if rx.search(t))) for k, rx in FUSION.items()),
                 key=lambda x: -x[1]), n)

    table("ReQ6 — deployment, robustness and ethics",
          sorted(((k, sum(1 for t in txt if rx.search(t))) for k, rx in DEPLOY.items()),
                 key=lambda x: -x[1]), n)

    # The intersection that matters to this thesis.
    both = sum(1 for t in txt if DEPLOY["edge / on-device"].search(t)
               and DEPLOY["healthcare / clinical"].search(t))
    tri = sum(1 for t in txt if DEPLOY["edge / on-device"].search(t)
              and DEPLOY["healthcare / clinical"].search(t)
              and DEPLOY["privacy / federated"].search(t))
    print(f"\nTHE INTERSECTION THIS THESIS OCCUPIES")
    print(f"  edge AND healthcare                    {both:>6d}  {both/n*100:.1f}%")
    print(f"  edge AND healthcare AND privacy        {tri:>6d}  {tri/n*100:.1f}%")
    print(f"  ...against {n} records. Consistent with the S7 conjunction ladder,")
    print("  which returns zero on the full seven-clause query.\n")

    if a.json:
        Path(a.json).write_text(json.dumps({
            "n": n, "with_abstract": has_abs,
            "req5": {"speaker_independent": si, "cross_corpus": cc,
                     "speaker_dependent": sd, "split_kind_unstated": gs,
                     "uar_or_macro_f1": uar, "silent_on_evaluation": silent},
            "req4_datasets": dict(ds),
            "req3_fusion": {k: sum(1 for t in txt if rx.search(t)) for k, rx in FUSION.items()},
            "req6": {k: sum(1 for t in txt if rx.search(t)) for k, rx in DEPLOY.items()},
            "intersection": {"edge_and_health": both, "edge_health_privacy": tri},
            "caveat": ("Signals from titles and abstracts of the retrieved corpus. "
                       "Not findings; abstracts under-report method. The ReQ5 result "
                       "must come from full-text extraction on included papers."),
        }, indent=2))
        print(f"wrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
