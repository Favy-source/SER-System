"""
Repair the Canva-redesigned deck.

    .venv/bin/python scripts/fix_canva_deck.py

WHY THIS IS NEEDED
    Canva's redesign improved the layout and, in the process, silently changed
    wording. Two of those changes reintroduce claims this project had already
    corrected against evidence:

      "Speaker Emotion Recognition"   SER is SPEECH emotion recognition. On a
                                      slide about the candidate's own manuscript,
                                      this is the kind of error a panel notices.

      "three fusion architectures     They are implemented and UNTRAINED. Every
       tested"                        fusion checkpoint in models/ is
                                      DEMO_UNTRAINED. "Tested" is the exact
                                      overclaim that was removed once already.

    Slide 8 also reverted to pre-correction wording, and three typos arrived.

HOW REPLACEMENT WORKS
    PowerPoint splits a sentence across several runs whenever formatting changes
    mid-line, so a naive `run.text.replace(...)` misses anything spanning a
    boundary. This walks each paragraph, and when a match spans runs it writes
    the result into the first run and blanks the rest — which preserves the first
    run's formatting and drops only the formatting of the fragments consumed.
"""
import sys
from pathlib import Path

from pptx import Presentation

ROOT = Path(__file__).resolve().parent.parent
DECK = ROOT / "docs/presentation/NwachukwuchinemeremfavourP2602387.pptx"

# (wrong, right, why) — every entry is a correction of fact or spelling, never
# a rewrite of the candidate's own voice.
FIXES = [
    ("Speaker Emotion Recognition", "Speech Emotion Recognition",
     "SER is Speech Emotion Recognition; 'Speaker' is a different task"),
    ("three fusion architectures tested", "three fusion architectures implemented",
     "they are implemented and untrained — 'tested' overclaims"),
    ("stregthening", "strengthening", "typo"),
    ("dployability", "deployability", "typo"),
    ("Audio + visual fusion implemented — rigorous validation is the core of this research.",
     "Audio and webcam capture verified live; the trained checkpoint is audio-only. "
     "Training and validating fusion is the proposed research.",
     "reverted to pre-correction wording; the running system reports the camera "
     "cannot contribute with an audio-only checkpoint"),
    ("MFCC • Pitch + Energy", "Log-mel • MFCC • 468 landmarks",
     "reverted to the audio-only feature list, contradicting the multimodal claim "
     "on the same slide"),
    ("Speaker-independent SER baseline: 55.1% accuracy, 0.489 macro-F1; "
     "live streaming inference.",
     "Speaker-independent SER baseline: 55.1% accuracy, 0.489 macro-F1 "
     "(3 held-out actors, n=156); live streaming inference.",
     "the sample size and held-out speaker count were dropped — they are what "
     "make the number auditable rather than merely quoted"),
]

# Figures Canva did not carry across, with where they go and why there.
FIGURES = [
    # (file, slide number, left, top, width — inches on a 20 x 11.25 canvas)
    ("fig_per_class_recall.png", 8, 10.05, 5.55, 8.60,
     "slide 8 already states the 55.1% baseline; the chart is the per-class "
     "breakdown behind it. Its right half was empty — text runs only to x=8.1."),
]


def replace_in_paragraph(para, old, new):
    """Replace across run boundaries, keeping the first run's formatting."""
    full = "".join(r.text for r in para.runs)
    if old not in full or not para.runs:
        return False
    para.runs[0].text = full.replace(old, new)
    for r in para.runs[1:]:
        r.text = ""
    return True


def main():
    if not DECK.exists():
        sys.exit(f"missing {DECK}")
    prs = Presentation(DECK)

    applied = {old: 0 for old, _, _ in FIXES}
    for i, slide in enumerate(prs.slides, 1):
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for para in shape.text_frame.paragraphs:
                for old, new, _ in FIXES:
                    if replace_in_paragraph(para, old, new):
                        applied[old] += 1
                        print(f"  slide {i}: {old[:52]!r} -> fixed")

    # Canva left the file's authorship blank and titled it after its template.
    cp = prs.core_properties
    cp.author = "Nwachukwu Chinemerem Favour"
    cp.last_modified_by = "Nwachukwu Chinemerem Favour"
    cp.title = "MMU Achievers Research Scholarship 2026 - Nwachukwu Chinemerem Favour"

    # Re-insert figures Canva dropped.
    from pptx.util import Inches as _In
    from PIL import Image as _I
    for name, slide_no, left, top, width, why in FIGURES:
        src = ROOT / "docs/presentation" / name
        if not src.exists():
            print(f"  figure MISSING on disk: {name}")
            continue
        slide = prs.slides[slide_no - 1]
        iw, ih = _I.open(src).size
        w = _In(width)
        h = int(w * ih / iw)
        slide.shapes.add_picture(str(src), _In(left), _In(top), w, h)
        print(f"  slide {slide_no}: inserted {name} ({width:.2f}in wide) — {why}")

    prs.save(DECK)
    print(f"\nSaved {DECK.relative_to(ROOT)}")
    missed = [o for o, n in applied.items() if n == 0]
    if missed:
        print("\nNOT FOUND (check by hand — the wording may differ slightly):")
        for m in missed:
            print(f"  {m!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
