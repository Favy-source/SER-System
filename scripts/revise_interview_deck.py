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
from datetime import datetime
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

CANDIDATE = "Nwachukwu Chinemerem Favour"
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


def reorder(prs, order):
    """Rearrange slides to `order` (a list of current 0-based indices).

    python-pptx has no public reorder API, so this manipulates the presentation's
    slide-id list directly. That list is what defines slide sequence; the slide
    parts themselves are untouched, so no content, layout or relationship is
    disturbed — only the order they are presented in.
    """
    id_list = prs.slides._sldIdLst
    entries = list(id_list)
    if sorted(order) != list(range(len(entries))):
        raise ValueError(f"order must be a permutation of 0..{len(entries) - 1}, got {order}")
    for e in entries:
        id_list.remove(e)
    for i in order:
        id_list.append(entries[i])


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
         f"({spk} held-out actors, n={n}). {lat:.0f} ms model inference; "
         f"110-155 ms end-to-end in-browser.",
         "Replaced '~80% on internal validation', which no result file supports. "
         f"Also distinguishes the {lat:.0f} ms benchmark (model forward pass only) "
         "from what the running dashboard reports end-to-end — a panel would "
         "reasonably read a bare '22 ms' as the latter. The range is the span "
         "actually observed across capture runs (108, 129, 153 ms) and must "
         "contain the figure visible in the slide-7 screenshot, or the two "
         "slides contradict each other.")

    edit(4, "Text 2",
         "A working real-time system — live audio and webcam capture, three fusion "
         "architectures implemented, audio model evaluated speaker-independently.",
         "Precise about what is measured. The speaker-independent evaluation is of "
         "the AUDIO model; the fusion architectures are built but not yet trained.")

    edit(4, "Text 19",
         "Live audio + webcam capture verified in-browser (face tracked, 4 fps, GPU). "
         "The trained checkpoint is audio-only — training and validating fusion is the "
         "proposed research.",
         "CORRECTION. An earlier revision claimed 'audio + visual fusion verified "
         "live in-browser'. Running the system contradicts that: it displays "
         "'Loaded model is audio-only, so the camera cannot contribute.' Capture "
         "works both ways; the only trained checkpoint is audio-only and every "
         "fusion checkpoint in models/ is DEMO_UNTRAINED.")

    edit(4, "Text 17",
         "Real-time pipeline (FastAPI / WebSockets) with a React dashboard. "
         "Honest limitation: 0.88 recall on high-arousal emotions, 0.08 on happy — "
         "arousal is learned, valence is not.",
         "Moves the limitation here now that the fusion status occupies Text 19. "
         "Naming your own weakness before a panel finds it is the strongest "
         "available signal of research maturity.")

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
    # ── Slide 6: relabelled to the IPS email's own vocabulary ──
    # The committee reads their list and ticks items off. Blocks headed
    # "Competitions & Leadership" and "Service & Motivation" make them hunt for
    # "co-curriculum", "awards" and "publications". These headings say the words
    # the email said, in the email's order.
    edit(6, "Text 1", "Co-curriculum, Competitions & Awards",
         "Slide title now names what the email asked for.")

    edit(6, "Text 4", "Co-curriculum & Positions Held",
         "Email item 2: 'involvement of co-curriculum other than academic, or "
         "position held in club during university'.")
    edit(6, "Text 5",
         "Pioneer Vice-President, Dept. of ICT, ABSU | "
         "Vice-President, Rotary Club (2018-2019) | "
         "SDG volunteer (NYSC) & community outreach",
         "Groups the two club positions and the volunteering under co-curriculum. "
         "Adds the Rotary Vice-Presidency, which was missing entirely.")

    edit(6, "Text 8", "Competitions & Awards",
         "Email items 3 and 4: research-related competition, and award at "
         "university / national / international level.")
    edit(6, "Text 9",
         "Silver medal — national informatics competition (2018) | "
         "MTN Foundation Scholarship (2017) — awarded on merit, national level",
         "Puts both competitive awards together and states their level, which is "
         "what the email asks for. Drops the Rubik's cube placing: beside a "
         "national informatics medal it reads as filler to an academic panel.")

    edit(6, "Text 12", "Research Engagement & Publications",
         "Email item 5: published paper and Scopus/WoS screenshots, 'if any'.")
    edit(6, "Text 13",
         "Manuscript in preparation (SER) | Systematic review underway — 2,526 records "
         "identified by a protocol-driven, reproducible search | "
         "AI R&D contributor, Nupat Technologies",
         "Adds the systematic review with its real corpus size. A protocol executed "
         "as code is concrete evidence of research method, which is what the panel "
         "is assessing in the absence of an indexed publication.")

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

    # ── new slide: the prototype actually running ──
    #
    # A screenshot of the live system is the one artefact a panel cannot get from
    # reading an application. It gets its own slide rather than sharing the box
    # with the recall chart, because two images crammed into a 6.1x2.25in panel
    # are both illegible at projector size.
    #
    # The capture is honest: real RAVDESS speech fed to the real model, camera
    # off because the trained checkpoint is audio-only. Nothing is mocked.
    shot = ROOT / "docs/presentation/fig_prototype_live.png"
    if shot.exists():
        blank = prs.slides.add_slide(s[0].slide_layout)
        t = blank.shapes.add_textbox(Inches(0.65), Inches(0.50), Inches(12.0), Inches(0.72))
        r = t.text_frame.paragraphs[0].add_run()
        r.text = "The Prototype, Running"
        r.font.name, r.font.size, r.font.bold = "Cambria", Pt(29), True
        r.font.color.rgb = RGBColor(0x1E, 0x27, 0x61)

        cap = blank.shapes.add_textbox(Inches(0.65), Inches(1.26), Inches(12.0), Inches(0.5))
        cr = cap.text_frame.paragraphs[0].add_run()
        cr.text = ("Both streams, running. Audio inference on held-out RAVDESS speech; "
                   "facial landmarks tracked live at 8 fps on GPU.")
        cr.font.size, cr.font.bold = Pt(13), False
        cr.font.color.rgb = RGBColor(0x33, 0x45, 0x4F)
        cap.text_frame.word_wrap = True

        # Two panels at MATCHED HEIGHT so their tops and bottoms align; the widths
        # differ because the crops differ in aspect. Equal widths would have left
        # one panel floating above the other's baseline.
        from PIL import Image as _I
        vis = ROOT / "docs/presentation/fig_visual_pipeline.png"
        panels = [(shot, "Trained audio model: angry at 96% confidence, 153 ms end to end.")]
        if vis.exists():
            panels.append((vis, "Visual pipeline: 468 landmarks, face tracked, 8 fps, GPU. "
                                "Captured but not yet consumed — the trained checkpoint "
                                "is audio-only."))

        # Height is derived from the WIDTH budget, not chosen. Side by side, the
        # two aspects sum to ~4.55:1, so the widest the pair can be is what fits
        # across the slide — picking a height first left either overflow or a
        # third of the slide empty.
        gap = Inches(0.35)
        avail = prs.slide_width - Inches(1.0) - gap
        aspects = [(lambda s: s[0] / s[1])(_I.open(p).size) for p, _ in panels]
        H = int(avail / sum(aspects))
        sizes = [(int(H * a), H) for a in aspects]
        total = sum(w for w, _ in sizes) + gap * (len(sizes) - 1)
        x = int((prs.slide_width - total) / 2)
        top = Inches(1.92)
        for (path, sub), (w, h) in zip(panels, sizes):
            blank.shapes.add_picture(str(path), x, top, w, h)
            tb = blank.shapes.add_textbox(x, top + h + Inches(0.12), w, Inches(0.9))
            tb.text_frame.word_wrap = True
            sr = tb.text_frame.paragraphs[0].add_run()
            sr.text = sub
            sr.font.size = Pt(10.5)
            sr.font.color.rgb = RGBColor(0x5A, 0x6B, 0x76)
            x += w + gap

        # The line that makes the slide an argument rather than two screenshots.
        foot = blank.shapes.add_textbox(Inches(0.65), Inches(6.15),
                                        Inches(12.0), Inches(0.7))
        foot.text_frame.word_wrap = True
        fr = foot.text_frame.paragraphs[0].add_run()
        fr.text = ("Two streams captured, one model trained. Joining them — and proving "
                   "the join recovers the valence the audio model cannot read — is the "
                   "research I am proposing.")
        fr.font.size, fr.font.bold = Pt(13), True
        fr.font.color.rgb = RGBColor(0x1E, 0x27, 0x61)

        changes.append(("NEW", "The Prototype, Running",
                        "(slide did not exist)",
                        "Adds a screenshot of the live system. Real RAVDESS speech through "
                        "the real model, correctly classified. This is the artefact a panel "
                        "cannot get from reading your application."))

    # ── Slide 7: correct the supervisor claim ──
    #
    # The original said Kanesaraj works on "quantized, edge-deployed models".
    # Across his 71 indexed works there are ZERO papers on quantisation, pruning,
    # distillation or compression. Said to his face on a panel, that reads as
    # not having read him.
    #
    # His real direction is a better fit anyway: real-time deep learning on
    # Raspberry Pi for biomedical signals (digital stethoscope 2026, energy-
    # efficient COPD detection 2025), and his most-cited paper — 167 citations —
    # is on psychosocial barriers to healthcare technology ADOPTION, which is
    # this thesis's deployment gap seen from the human side.
    #
    # Wan-Noorshahida is likewise not primarily a face researcher: her record is
    # hand gesture recognition (96 cites), gait recognition, crowd density. That
    # maps onto the BEHAVIOURAL third modality, not the facial stream.
    edit(7, "Text 3",
         "A precise fit: Assoc. Prof. Kanesaraj runs real-time deep learning on "
         "Raspberry Pi for biomedical signals, and publishes on the barriers to "
         "healthcare technology adoption — my deployment gap from the human side. "
         "Assoc. Prof. Wan-Noorshahida works on gait and gesture recognition: the "
         "behavioural modality in my proposal.",
         "CORRECTION. The original credited Kanesaraj with research on 'quantized, "
         "edge-deployed models'; he has no such papers across 71 indexed works. "
         "Replaced with what both supervisors actually publish, verified against "
         "OpenAlex. The true fit is stronger than the claimed one.")

    # ── Slide 7: Fit & Vision, kept ──
    # It answers none of the seven requested items, which is why it was briefly
    # trimmed. Restored deliberately: "please include the following" sets a floor
    # rather than a ceiling, "why MMU?" is near-certain to be asked, and having
    # the supervisor mapping on screen means pointing rather than improvising.
    # It costs about fifteen seconds against a two-and-a-half minute surplus.

    # ── reorder to follow the IPS email's own sequence ──
    #
    # The committee works through the list they asked for, so the deck is ordered
    # to let them tick items off in order:
    #
    #   1 CGPA
    #   2 co-curriculum other than academic, or position held in a club
    #   3 research-related conference / competition
    #   4 award at university / national / international level
    #   5 published paper first page + Scopus/WoS screenshot
    #   6 other achievements
    #   7 title of the research proposal and the problem that inspired it
    #
    # This is a REORDER, not a redesign — every slide keeps its content and
    # layout. Note that "professional experience" is item 6 (other achievements),
    # NOT item 2: the club positions are co-curriculum and live on the
    # recognition slide. Getting those two the wrong way round puts work history
    # where the committee is looking for university involvement.
    #
    # The proposal moving to fifth also reads better: the achievements establish
    # the candidate, then the proposal lands as the climax with the prototype
    # evidence immediately behind it.
    ORDER = [
        0,   # cover — name, programme, proposal title
        1,   # academic record: CGPA, degree                 <- item 1
        5,   # co-curriculum, competitions, awards, pubs     <- items 2, 3, 4, 5
        4,   # professional experience & leadership          <- item 6
        2,   # research proposal + core problem              <- item 7
        3,   # preliminary work: measured results
        7,   # the prototype, running  (added above)
        6,   # close
    ]
    reorder(prs, ORDER)

    # ── authorship metadata ──
    # The source deck carries "PptxGenJS" as author and title, from whatever tool
    # generated it. Applying this here rather than to the output file means it
    # survives a rebuild; fixing the output directly was silently undone the next
    # time this script ran.
    cp = prs.core_properties
    cp.author = CANDIDATE
    cp.last_modified_by = CANDIDATE
    cp.title = f"MMU Achievers Research Scholarship 2026 - {CANDIDATE}"
    cp.category = ""
    cp.keywords = ""
    cp.comments = ""
    cp.modified = datetime.now()
    changes.append(("all", "slide order",
                    "1 cover · 2 academic · 3 proposal · 4 prototype · "
                    "5 experience · 6 recognition · 7 fit",
                    "Reordered to follow the IPS email's own sequence so the panel can "
                    "tick their list off in order. Content and layout unchanged."))

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
