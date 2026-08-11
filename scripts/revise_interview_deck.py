"""
Revise the MMU High Achievers interview deck IN PLACE.

    .venv/bin/python scripts/revise_interview_deck.py

WHY EDIT RATHER THAN REGENERATE
    The existing deck is well designed and its framing is the candidate's own.
    Regenerating would throw that away. This script rewrites only the specific
    runs of text that are factually wrong or incomplete, preserving every shape,
    image, colour and layout.

THE CHANGE THAT MATTERS
    Two slides claimed "~80% on internal validation". No artefact in this
    repository supports that number. The only measured result is
    results/audio_cnn_lstm_results.json:

        accuracy 0.5513 · macro-F1 0.4891 · n=156 · held-out actors 16, 17, 19
        latency  21.7 ms mean, 26.4 ms p95, CPU

    Presenting an unsourced ~80% would be risky for any candidate. For THIS
    candidate it is specifically dangerous, because the proposal's own argument
    is that speaker-independent evaluation is the correct protocol and that
    headline numbers are inflated by improper splits (Review Question ReQ5). A
    panel that asks "which protocol produced the 80%?" would be asking the
    question the research itself invites, and there is no defensible answer.

    The honest figure is also the stronger one: 55.1% speaker-independent, with
    validation at 66%, is an 11-point gap caused by speaker variation alone —
    and that gap IS the research problem.
"""
import json
import sys
from pathlib import Path

from pptx import Presentation

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs/presentation/MMU_Interview_Favour (2).pptx"
DST = ROOT / "docs/presentation/MMU_Interview_Favour_REVISED.pptx"
RESULTS = ROOT / "results/audio_cnn_lstm_results.json"


def set_text(shape, text):
    """Replace a shape's text while keeping the first run's formatting.

    python-pptx drops all character formatting if you assign to
    text_frame.text, which would strip the deck's fonts and colours. Writing
    into the first run and emptying the rest keeps the design intact.
    """
    tf = shape.text_frame
    para = tf.paragraphs[0]
    if not para.runs:
        para.add_run()
    para.runs[0].text = text
    for r in para.runs[1:]:
        r.text = ""
    for p in tf.paragraphs[1:]:
        for r in p.runs:
            r.text = ""


def set_lines(shape, lines):
    """Same as set_text but for the two-line label/value boxes in the diagram.

    Each box is a separate paragraph with its own formatting (bold label above,
    lighter detail below), so they must be written paragraph-by-paragraph rather
    than collapsed into one.
    """
    tf = shape.text_frame
    for i, para in enumerate(tf.paragraphs):
        text = lines[i] if i < len(lines) else ""
        if not para.runs:
            if not text:
                continue
            para.add_run()
        para.runs[0].text = text
        for r in para.runs[1:]:
            r.text = ""


def find(slide, name):
    for sh in slide.shapes:
        if sh.name == name:
            return sh
    return None


def main():
    if not SRC.exists():
        sys.exit(f"missing source deck: {SRC}")
    m = json.loads(RESULTS.read_text())
    acc = m["accuracy"] * 100
    f1 = m["f1_macro"]
    lat = m["latency_mean_ms"]
    p95 = m["latency_p95_ms"]
    n = m["n_test"]
    spk = len(m["test_speakers"])

    prs = Presentation(SRC)
    s = prs.slides
    changes = []

    def edit(slide_no, shape_name, new, why):
        sh = find(s[slide_no - 1], shape_name)
        if sh is None or not sh.has_text_frame:
            changes.append((slide_no, shape_name, "NOT FOUND", why))
            return
        old = sh.text_frame.text.strip().replace("\n", " | ")
        set_text(sh, new)
        changes.append((slide_no, shape_name, old, why))

    # ── Slide 4: the unsupported accuracy claim ──
    edit(4, "Text 15",
         f"{acc:.1f}% accuracy · {f1:.3f} macro-F1 — speaker-independent "
         f"({spk} held-out actors, n={n}). {lat:.0f} ms mean inference, {p95:.0f} ms p95.",
         "Replaced '~80% on internal validation', which no result file supports. "
         "The real figure is speaker-independent and therefore defensible.")

    edit(4, "Text 2",
         "A working real-time multimodal system — audio and webcam, three fusion "
         "strategies implemented, evaluated speaker-independently.",
         "Sharpened: the prototype is multimodal and already measured, not "
         "'under validation'.")

    edit(4, "Text 19",
         "Audio + visual fusion verified live in-browser. Honest limitation: high-arousal "
         "emotions reach 0.88 recall, happy 0.08 — the model has learned arousal, not valence.",
         "States the known weakness before a panel finds it. Naming your own "
         "limitation is the strongest available signal of research maturity.")

    edit(4, "Text 22",
         "Private repository · full code, tests and results available on request",
         "The printed URL (github.com/Favy-source/speech-emotion-recognition) does "
         "not match the actual repo (SER-System), which is private and would 404.")

    # ── Slide 4: make the pipeline diagram match the multimodal claim ──
    # The headline now says "audio and webcam", but the diagram still described
    # an audio-only path (Streaming Audio -> MFCC/Pitch/Energy). A panel reading
    # the diagram would see a contradiction of the sentence above it.
    def edit_lines(slide_no, shape_name, lines, why):
        sh = find(s[slide_no - 1], shape_name)
        if sh is None or not sh.has_text_frame:
            changes.append((slide_no, shape_name, "NOT FOUND", why))
            return
        old = sh.text_frame.text.strip().replace("\n", " | ")
        set_lines(sh, lines)
        changes.append((slide_no, shape_name, old, why))

    edit_lines(4, "Text 4", ["Streaming", "Audio + Webcam"],
               "Diagram said audio-only while the slide claims multimodal.")
    edit_lines(4, "Text 7", ["Feature Extraction",
                             "Log-mel · MFCC · 468 face landmarks"],
               "Names the actual features the system extracts, including visual.")
    edit_lines(4, "Text 10", ["Fusion + Classifier",
                              "feature · decision · cross-modal attention"],
               "Shows the three fusion strategies — the technical core of the "
               "proposal and the thing worth a panel's attention.")

    # ── Slide 5: the same claim, second occurrence ──
    edit(5, "Text 17",
         "Up to 60% load-time reduction | Led engineering teams as CTO (Nuvoro) | "
         f"Speaker-independent SER baseline: {acc:.1f}% accuracy, {f1:.3f} macro-F1",
         "Second occurrence of the unsupported '~80%'.")

    # ── Slide 6: missing position, and the SLR as research evidence ──
    edit(6, "Text 5",
         "Silver medal — national informatics competition (2018) | "
         "Pioneer Vice-President, Dept. of ICT, ABSU | "
         "Vice-President, Rotary Club (2018-2019)",
         "Adds Rotary Club Vice-Presidency, which was missing. Drops the Rubik's "
         "cube placing: against genuinely competitive items it reads as filler to "
         "an academic panel.")

    edit(6, "Text 9",
         "Manuscript in preparation (SER) | Systematic review underway — protocol-driven, "
         "reproducible search across OpenAlex, Crossref, PubMed and arXiv | "
         "AI R&D contributor, Nupat Technologies",
         "Adds the systematic review. A registered protocol executed as code is "
         "concrete evidence of research method, which is what the panel is assessing.")

    # ── Slide 4: fill the empty screenshot placeholder ──
    #
    # The deck shipped with a dashed box reading "Live-dashboard screenshot —
    # add here". An unfilled placeholder on a scholarship slide is worse than no
    # box at all, so it is filled with a real measured figure. A live screenshot
    # is still the better artefact if one can be captured; swapping it in means
    # replacing this picture and restoring the caption.
    fig = ROOT / "docs/presentation/fig_per_class_recall.png"
    slide4 = s[3]
    box = find(slide4, "Shape 20")          # the dashed placeholder frame
    caption = find(slide4, "Text 21")       # "Live-dashboard screenshot — add here"
    if fig.exists() and box is not None:
        pad = 60000                          # ~0.07in inset so the frame still reads
        slide4.shapes.add_picture(
            str(fig),
            box.left + pad, box.top + pad,
            width=box.width - 2 * pad,
            height=box.height - 2 * pad - 300000,   # leave room for the caption
        )
        if caption is not None:
            set_text(caption, "")
        # The repository caption sits below the figure rather than over it.
        cap2 = find(slide4, "Text 22")
        if cap2 is not None:
            cap2.top = box.top + box.height - 330000
        changes.append((4, "Shape 20", "Live-dashboard screenshot — add here",
                        "Filled the empty placeholder with the measured per-class "
                        "recall figure. Swap for a live screenshot if you capture one."))

    prs.save(DST)

    print(f"Wrote {DST.relative_to(ROOT)}\n")
    print(f"Measured results used (from {RESULTS.name}):")
    print(f"  accuracy {acc:.2f}%   macro-F1 {f1:.4f}   n={n}   "
          f"held-out actors: {', '.join(m['test_speakers'])}")
    print(f"  latency  {lat:.1f} ms mean, {p95:.1f} ms p95, {m['device']}\n")
    print("Changes:")
    for slide_no, name, old, why in changes:
        print(f"\n  SLIDE {slide_no} [{name}]")
        print(f"    was: {old[:150]}")
        print(f"    why: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
