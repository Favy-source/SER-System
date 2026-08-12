"""
Generate the Results chapter skeleton from the protocol.

    python3 -m slr.results_skeleton                    # print it
    python3 -m slr.results_skeleton --out docs/slr/RESULTS_SKELETON.md

WHY GENERATE IT RATHER THAN WRITE IT
    Because the Results sections map 1:1 to Review Questions, and the Review
    Questions live in protocol.py, the chapter's shape is already determined —
    it just has not been written down. Generating it means the skeleton cannot
    drift from the protocol, and any ReQ added later gets a section automatically
    instead of being forgotten.

    It also makes the golden thread checkable rather than aspirational:

        the questions drive the search
        -> the extracted data answers the questions
        -> the synthesis reveals the gaps
        -> the gaps justify the framework

    Every section below names the extraction column that feeds it. A section
    with no column feeding it is a question the review cannot answer, and it is
    better to discover that now than at the writing-up stage.

WHAT IT DELIBERATELY LEAVES BLANK
    Every number. The tables ship with headers and empty cells because filling
    them requires screening and extraction decisions that are the reviewer's.
    A skeleton with plausible numbers already in it would be the single easiest
    way to end up reporting something nobody actually counted.
"""
import argparse
import sys
from pathlib import Path

from . import gaps as G
from . import protocol as P

# What each Review Question's Results section should actually contain: the
# tables to build, and which extraction column supplies each one.
SECTION_PLAN = {
    "ReQ1": [
        ("Approaches proposed for healthcare and caregiving contexts",
         "Healthcare / Caregiving?", "Count Yes / mentioned only / No. The "
         "'mentioned only' column is the interesting one — it separates papers "
         "that TARGET care settings from papers that list healthcare as a "
         "possible application in their introduction and never return to it."),
        ("Multimodal vs unimodal performance",
         "Unimodal Baseline Compared?", "Only papers that compared can speak to "
         "this. Papers reporting a multimodal number with no unimodal baseline "
         "cannot support 'multimodal is better' and must be excluded from that "
         "claim, however good the number looks."),
    ],
    "ReQ2": [
        ("Modality combinations", "Modalities Used",
         "Cross-tabulate against Best Accuracy, but do NOT rank across datasets — "
         "see the metric-comparability warning below."),
        ("Feature representations", "Architecture / Model", ""),
    ],
    "ReQ3": [
        ("Fusion strategies and their reported performance", "Fusion Strategy",
         "Group by strategy; report the range, not a single best. A single best "
         "is a dataset artefact."),
        ("Architectures", "Architecture / Model", ""),
    ],
    "ReQ4": [
        ("Dataset frequency", "Dataset(s)",
         "The headline count. Preliminary abstract-level signal already shows "
         "IEMOCAP dominant — confirm on full texts."),
        ("Elicitation: acted vs spontaneous", "Dataset(s)",
         "Derived from the dataset, not stated per paper: RAVDESS/SAVEE/EMO-DB "
         "are acted; IEMOCAP is elicited-improvised; MSP-Podcast and AFEW are "
         "in-the-wild. This mapping IS the representativeness argument."),
        ("Healthcare representativeness", "Dataset(s) x Healthcare / Caregiving?",
         "The gap this thesis targets: how many papers claiming healthcare "
         "relevance evaluate on a corpus recorded in a care setting? The "
         "expected answer is very few, and that is a reportable finding."),
    ],
    "ReQ5": [
        ("Evaluation protocol reported", "Evaluation Protocol",
         "THE headline finding candidate. Count speaker-independent / LOSO / "
         "k-fold SI / random split / cross-corpus / NOT REPORTED. The NR count "
         "is a result in itself."),
        ("Metric type", "Metric Type",
         "Accuracy, WA, UA/UAR, weighted-F1 and macro-F1 are NOT comparable. "
         "Any table mixing them is invalid; report them in separate columns."),
        ("Performance by protocol", "Evaluation Protocol x Best Accuracy (%)",
         "If speaker-independent studies report systematically lower accuracy "
         "than speaker-dependent ones, that difference is a quantitative "
         "contribution — and it is exactly what this project's own baseline "
         "shows at the single-study level (66% validation vs 55% test)."),
    ],
    "ReQ6": [
        ("Real-time capability and latency", "Latency Reported (ms)",
         "Record whether the figure is model-forward or end-to-end. Most papers "
         "do not say, and that ambiguity is a finding — see gap G3."),
        ("Edge deployment and compression", "Edge Hardware Used, Compression", ""),
        ("Robustness", "Robustness Tested",
         "Noise, occlusion, missing modality, speaker variation — count each."),
        ("Ethics and privacy", "Ethics / Privacy Discussed?",
         "Distinguish papers that DISCUSS privacy from those that IMPLEMENT "
         "something (federated learning, on-device processing, differential "
         "privacy). The gap is usually between the two."),
    ],
    "ReQ7": [
        ("Synthesis of gaps", "(from the Gap Chains sheet)",
         "Not searched for directly. Emerges from the chains: GAP -> CAUSE -> "
         "METHOD -> RESEARCH QUESTION."),
    ],
}


def build() -> str:
    L = []
    w = L.append
    w("# Results — chapter skeleton")
    w("")
    w(f"Generated from `slr/protocol.py` v{P.VERSION} and `slr/gaps.py`. "
      f"Re-run `python3 -m slr.results_skeleton` after any protocol change.")
    w("")
    w("**Every table below is empty on purpose.** Filling them requires screening "
      "and extraction decisions that are mine to make. A skeleton pre-filled with "
      "plausible numbers is the easiest way to end up reporting something nobody "
      "counted.")
    w("")
    w("## The thread this chapter has to hold")
    w("")
    w(f"> {P.GOLDEN_THREAD}")
    w("")
    w("Each section states the extraction column that feeds it. A section with no "
      "column feeding it is a question this review cannot answer — better found "
      "now than at writing-up.")
    w("")
    w("## Before any table: two rules that invalidate results if broken")
    w("")
    w("1. **Never pool incomparable metrics.** Accuracy, WA, UA/UAR, weighted-F1 "
      "and macro-F1 measure different things. A mean across them is meaningless. "
      "Report them in separate columns or separate tables.")
    w("2. **Never pool incomparable tasks.** Categorical classification, "
      "dimensional regression and multi-label prediction do not share a metric "
      "space. The `Task Type` column exists to keep CMU-MOSI regression out of "
      "the same table as IEMOCAP accuracy.")
    w("")
    w("---")
    w("")

    for req, text in P.REVIEW_QUESTIONS.items():
        rqs = ", ".join(P.REQ_TO_RQ.get(req, []))
        w(f"## {req}. {text}")
        w("")
        w(f"*Feeds Research Question(s): **{rqs}**. "
          f"Evidence source: {P.REQ_EVIDENCE_SOURCE.get(req, '—')}.*")
        w("")
        for title, col, note in SECTION_PLAN.get(req, []):
            w(f"### {title}")
            w("")
            w(f"`extraction column: {col}`")
            w("")
            if note:
                w(f"> {note}")
                w("")
            w("| category | n | % of included | notes |")
            w("|---|---:|---:|---|")
            w("|  |  |  |  |")
            w("")
        rel = [g for g in G.GAP_CHAINS if req in ("ReQ7",) or g["rq"] in P.REQ_TO_RQ.get(req, [])]
        if rel:
            w(f"**Gap chains landing here:** " +
              ", ".join(f"`{g['id']}` ({g['type']}, {g['status']})" for g in rel))
            w("")
        w("---")
        w("")

    w("## Threats to report alongside these results")
    w("")
    for tid, name, desc, _ in P.THREATS:
        w(f"- **{tid} {name}** — {desc.split('.')[0]}.")
    w("")
    w("## Gap chains in full")
    w("")
    w("| ID | type | status | gap | primary RQ |")
    w("|---|---|---|---|---|")
    for g in G.GAP_CHAINS:
        stmt = g["statement"].replace("|", "/")[:110]
        w(f"| {g['id']} | {g['type']} | {g['status']} | {stmt} | {g['rq']} |")
    w("")
    return "\n".join(L)


def main(argv=None):
    p = argparse.ArgumentParser(description="Generate the Results chapter skeleton")
    p.add_argument("--out", default="")
    a = p.parse_args(argv)
    md = build()
    if a.out:
        dest = Path(a.out)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(md)
        print(f"wrote {a.out}  ({len(md.splitlines())} lines)")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
