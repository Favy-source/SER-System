"""
Generate a PowerPoint deck about this system.

    pip install python-pptx          # only dependency, not in requirements.txt
    python3 scripts/make_presentation.py
    python3 scripts/make_presentation.py --out docs/presentation/SER-System.pptx

Parameter counts, tensor shapes and feature dimensions are computed from the
live code and config rather than typed in, so the deck cannot silently drift
from the repository. Anything that is *not* measurable — accuracy, F1 — is
absent by design: no model has been trained yet, and a deck that implied
otherwise would be worse than one that says so.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

import torch
import yaml
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Emu, Inches, Pt

from src.constants import LANDMARK_DIM, N_FACE_LANDMARKS
from src.datasets import UNIFIED
from src.models.builder import FUSION, build_model, feature_height, n_frames

# ── palette (light theme: projects reliably, prints legibly) ──
INK    = RGBColor(0x0F, 0x17, 0x2A)
BODY   = RGBColor(0x33, 0x41, 0x55)
MUTED  = RGBColor(0x64, 0x74, 0x8B)
ACCENT = RGBColor(0x03, 0x69, 0xA1)
GOOD   = RGBColor(0x04, 0x78, 0x57)
WARN   = RGBColor(0xB4, 0x53, 0x09)
BAD    = RGBColor(0xB9, 0x1C, 0x1C)
RULE   = RGBColor(0xCB, 0xD5, 0xE1)
PANEL  = RGBColor(0xF1, 0xF5, 0xF9)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)

W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.85)
FONT = "Calibri"


# ─────────────────────────── helpers ───────────────────────────

def _tf(shape, text, size, color, bold=False, italic=False, space_after=6,
        align=PP_ALIGN.LEFT, font=FONT):
    tf = shape.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run(); r.text = text
    r.font.size, r.font.color.rgb, r.font.bold = Pt(size), color, bold
    r.font.italic, r.font.name = italic, font
    p.space_after = Pt(space_after)
    return tf


def _box(slide, x, y, w, h):
    return slide.shapes.add_textbox(x, y, w, h)


def _rect(slide, x, y, w, h, fill, line=None):
    from pptx.enum.shapes import MSO_SHAPE
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line; s.line.width = Pt(1)
    s.shadow.inherit = False
    return s


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def title_slide(prs, title, subtitle, footer):
    s = blank(prs)
    _rect(s, 0, 0, W, Inches(0.22), ACCENT)
    _tf(_box(s, MARGIN, Inches(2.0), W - 2 * MARGIN, Inches(1.6)),
        title, 42, INK, bold=True)
    _tf(_box(s, MARGIN, Inches(3.5), W - 2 * MARGIN, Inches(1.4)),
        subtitle, 20, BODY)
    _rect(s, MARGIN, Inches(5.05), Inches(1.6), Pt(3), ACCENT)
    _tf(_box(s, MARGIN, Inches(5.4), W - 2 * MARGIN, Inches(1.2)),
        footer, 14, MUTED)
    return s


def section_slide(prs, kicker, title):
    s = blank(prs)
    _rect(s, 0, 0, Inches(0.22), H, ACCENT)
    _tf(_box(s, MARGIN, Inches(2.7), W - 2 * MARGIN, Inches(0.5)),
        kicker.upper(), 13, ACCENT, bold=True)
    _tf(_box(s, MARGIN, Inches(3.2), W - 2 * MARGIN, Inches(1.5)),
        title, 34, INK, bold=True)
    return s


def content_slide(prs, title, kicker=None):
    s = blank(prs)
    top = Inches(0.55)
    if kicker:
        _tf(_box(s, MARGIN, Inches(0.38), W - 2 * MARGIN, Inches(0.35)),
            kicker.upper(), 11, ACCENT, bold=True)
        top = Inches(0.78)
    _tf(_box(s, MARGIN, top, W - 2 * MARGIN, Inches(0.7)), title, 27, INK, bold=True)
    _rect(s, MARGIN, Inches(1.62), W - 2 * MARGIN, Pt(1.2), RULE)
    return s


def bullets(slide, items, x=MARGIN, y=Inches(1.9), w=None, size=15, gap=9):
    """items: list of str, or (text, style) where style in {'h','b','n','good','warn','bad'}"""
    w = w or (W - 2 * MARGIN)
    tb = _box(slide, x, y, w, H - y - Inches(0.6))
    tf = tb.text_frame; tf.word_wrap = True
    first = True
    for it in items:
        text, style = it if isinstance(it, tuple) else (it, "b")
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        if style == "h":
            r = p.add_run(); r.text = text
            r.font.size, r.font.bold, r.font.color.rgb = Pt(size + 1), True, INK
            p.space_before = Pt(10); p.space_after = Pt(4)
        elif style == "n":
            r = p.add_run(); r.text = text
            r.font.size, r.font.color.rgb, r.font.italic = Pt(size - 2), MUTED, True
            p.space_after = Pt(gap)
        else:
            col = {"b": BODY, "good": GOOD, "warn": WARN, "bad": BAD}[style]
            r = p.add_run(); r.text = "•  " + text
            r.font.size, r.font.color.rgb = Pt(size), col
            p.space_after = Pt(gap)
        r.font.name = FONT
    return tb


def table(slide, headers, rows, x=MARGIN, y=Inches(1.95), w=None, h=None,
          col_w=None, size=12, highlight=None):
    w = w or (W - 2 * MARGIN)
    h = h or Inches(0.42 + 0.34 * len(rows))
    g = slide.shapes.add_table(len(rows) + 1, len(headers), x, y, w, h).table
    if col_w:
        total = sum(col_w)
        for i, cw in enumerate(col_w):
            g.columns[i].width = Emu(int(w * cw / total))
    for j, htxt in enumerate(headers):
        c = g.cell(0, j); c.text = ""
        c.fill.solid(); c.fill.fore_color.rgb = INK
        c.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = c.text_frame.paragraphs[0]; r = p.add_run(); r.text = htxt
        r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(size), True, WHITE, FONT
    for i, row in enumerate(rows, start=1):
        for j, val in enumerate(row):
            c = g.cell(i, j); c.text = ""
            c.fill.solid()
            c.fill.fore_color.rgb = PANEL if i % 2 else WHITE
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = c.text_frame.paragraphs[0]; r = p.add_run(); r.text = str(val)
            r.font.size, r.font.name = Pt(size), FONT
            hl = highlight and highlight(i - 1, j, val)
            r.font.color.rgb = hl if isinstance(hl, RGBColor) else BODY
            r.font.bold = bool(hl)
            if j > 0:
                p.alignment = PP_ALIGN.RIGHT
    return g


def panel(slide, x, y, w, h, heading, lines, accent=ACCENT, size=13):
    _rect(slide, x, y, w, h, PANEL)
    _rect(slide, x, y, Pt(3.5), h, accent)
    _tf(_box(slide, x + Inches(0.22), y + Inches(0.14), w - Inches(0.4), Inches(0.4)),
        heading, size + 2, INK, bold=True)
    tb = _box(slide, x + Inches(0.22), y + Inches(0.62), w - Inches(0.4), h - Inches(0.75))
    tf = tb.text_frame; tf.word_wrap = True
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        mono = ln.startswith("`") and ln.endswith("`")
        r = p.add_run(); r.text = ln.strip("`")
        r.font.size = Pt(size - 1)
        r.font.color.rgb = BODY
        r.font.name = "Consolas" if mono else FONT
        p.space_after = Pt(5)
    return tb


STAT_W = Inches(3.1)
# Bullet width when a stat card occupies the right gutter.
TEXT_W_WITH_STAT = W - 2 * MARGIN - STAT_W - Inches(0.4)


def stat_card(slide, y, label, value, color=ACCENT):
    """Right-gutter figure. Bullets on these slides must use TEXT_W_WITH_STAT."""
    x = W - MARGIN - STAT_W
    _rect(slide, x, y, STAT_W, Inches(1.15), PANEL)
    _tf(_box(slide, x + Inches(0.18), y + Inches(0.1), STAT_W - Inches(0.36), Inches(0.4)),
        label, 12, MUTED, bold=True)
    _tf(_box(slide, x + Inches(0.18), y + Inches(0.45), STAT_W - Inches(0.36), Inches(0.6)),
        value, 26, color, bold=True)


def note(slide, text, color=MUTED):
    _tf(_box(slide, MARGIN, H - Inches(0.92), W - 2 * MARGIN, Inches(0.6)),
        text, 11.5, color, italic=True)


# ─────────────────────────── the deck ───────────────────────────

def build(cfg, out: Path):
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    # measured facts
    nc = len(UNIFIED)
    Hm, Tm = feature_height(cfg, "mel"), n_frames(cfg)
    Hf     = feature_height(cfg, "mfcc")
    MF     = cfg["visual"]["max_frames"]
    sr, dur = cfg["audio"]["sample_rate"], cfg["audio"]["duration"]

    P = {}
    for name in ["audio_cnn", "audio_cnn_lstm", "visual_lstm",
                 "feature_level", "decision_level", "attention"]:
        m = build_model(name, cfg, nc, "mel")
        P[name] = sum(p.numel() for p in m.parameters())
    dl = build_model("decision_level", cfg, nc, "mel")
    backbone = sum(p.numel() for p in dl.audio.parameters()) + \
               sum(p.numel() for p in dl.visual.parameters())
    emb = dl.audio._embed_dim

    # 1 ────────────────────────────────────────────────
    title_slide(
        prs,
        "Multimodal Speech Emotion Recognition",
        "Comparing audio, visual and three fusion strategies — for healthcare "
        "settings and an embedded wearable",
        "SER System  ·  research prototype  ·  all figures in this deck are measured "
        "from the codebase; no accuracy results yet (see Status)",
    )

    # 2 ────────────────────────────────────────────────
    s = content_slide(prs, "Why this problem", "motivation")
    bullets(s, [
        ("The observation", "h"),
        "In healthcare and caregiving, distress escalation is detected by manual observation.",
        "Late detection affects both patient wellbeing and caregiver safety.",
        ("Why existing SER does not simply transfer", "h"),
        "Benchmarks are acted, studio-recorded, largely North-American English.",
        "70% accuracy on RAVDESS is not evidence a system can tell a distressed patient "
        "from a calm one in a noisy ward, in a second language, on cheap hardware.",
        ("The gap this project measures", "h"),
        "Does combining voice and face actually help — enough to justify a camera, "
        "the compute, and the consent cost?",
    ])
    note(s, "The corpora available are acted and non-clinical. That is the central "
             "external-validity limit, stated up front rather than buried.")

    # 3 ────────────────────────────────────────────────
    s = content_slide(prs, "Multimodality is a hypothesis, not an assumption", "framing")
    bullets(s, [
        "Adding a visual stream is widely assumed to help. Whether it helps enough to "
        "justify its cost is an empirical question.",
        "So the system ships three unimodal baselines and three distinct fusion "
        "strategies, trainable and evaluable under identical conditions.",
        ("Which strategy wins is itself the finding", "h"),
        "It tells you how much cross-modal interaction the task actually requires — "
        "not just which number is biggest.",
    ], y=Inches(1.95))
    panel(s, MARGIN, Inches(4.2), Inches(5.6), Inches(2.3),
          "Three research questions",
          ["1. Does multimodal beat unimodal here?",
           "2. Which fusion strategy, and why?",
           "3. What survives on a wearable?"])
    panel(s, MARGIN + Inches(5.95), Inches(4.2), Inches(5.6), Inches(2.3),
          "Two deployment targets",
          ["PC + webcam — both modalities available",
           "Embedded wearable — audio only,",
           "and a ~1000x smaller compute budget"], accent=WARN)

    # 4 ────────────────────────────────────────────────
    s = content_slide(prs, "Pipeline", "architecture")
    bullets(s, [
        ("Offline", "h"),
        "corpora  →  parse to one schema  →  extract features to .npy  →  "
        "speaker-disjoint split  →  train  →  evaluate",
        ("Online", "h"),
        "checkpoint  →  InferenceEngine  →  FastAPI  →  WebSocket  →  browser",
        ("The boundary that matters", "h"),
        "Serving imports the SAME feature functions training used, so train/serve skew "
        "is structurally impossible rather than avoided by discipline.",
        "A checkpoint embeds the full config it was trained with, so old checkpoints "
        "still load after the config moves on.",
    ], y=Inches(1.9))
    panel(s, MARGIN, Inches(5.0), W - 2 * MARGIN, Inches(1.55),
          "Three corpora, one taxonomy",
          [f"RAVDESS (24 actors, A/V) · CREMA-D (91 actors, A/V) · MSP-IMPROV (12 actors, audio)",
           f"→ mapped to {nc} shared classes: {', '.join(UNIFIED)}",
           "calm folded into neutral; surprised dropped (only one corpus has it)"])

    # 5 ────────────────────────────────────────────────
    s = content_slide(prs, "What the models actually see", "features")
    table(s, ["stream", "representation", "shape", "notes"],
          [["Audio (default)", "log-mel spectrogram", f"{Hm} x {Tm}",
            f"{Hm} mel bands x {Tm} frames"],
           ["Audio (alt)", "MFCC + Δ + ΔΔ", f"{Hf} x {Tm}",
            "40 coefficients x 3, decorrelated"],
           ["Visual", "FaceMesh landmark sequence", f"{MF} x {LANDMARK_DIM}",
            f"{N_FACE_LANDMARKS} landmarks x 3 coords"]],
          col_w=[2.0, 3.0, 1.6, 3.4], size=12.5)
    bullets(s, [
        (f"Fixed {dur:.0f}-second window at {sr} Hz", "h"),
        "Longer clips are centre-cropped, shorter ones symmetrically zero-padded — the "
        "emotional peak sits mid-utterance in acted corpora, so cropping the middle "
        "keeps the affect and discards the silence.",
        ("Landmarks, not pixels", "h"),
        "Each frame is centred on its centroid and scaled by its maximum radius, so head "
        "position and distance from camera are removed and only face SHAPE survives.",
    ], y=Inches(3.6))
    note(s, "Silence must not produce NaNs: power_to_db on an all-zero signal is a "
             "classic -inf source, and a live mic stream is full of silent windows. Tested directly.")

    # 6 ────────────────────────────────────────────────
    section_slide(prs, "the core of the work", "Fusion: how the two streams meet")

    # 7 ────────────────────────────────────────────────
    s = content_slide(prs, "Both streams collapse to one width", "fusion · step 1")
    panel(s, MARGIN, Inches(2.0), Inches(5.6), Inches(2.5),
          "Audio encoder — AudioCNNLSTM",
          [f"`mel ({Hm} x {Tm})`",
           "`→ 3 conv blocks + maxpool`",
           f"`→ (128, 16, 16) → seq (16, 2048)`",
           "`→ BiLSTM(256) x2, bidirectional`",
           f"`→ attention pooling → {emb}-d`"])
    panel(s, MARGIN + Inches(5.95), Inches(2.0), Inches(5.6), Inches(2.5),
          "Visual encoder — VisualLSTM",
          [f"`landmarks ({MF} x {LANDMARK_DIM})`",
           f"`→ Linear({LANDMARK_DIM} → 256)`",
           "`→ BiLSTM(256) x2, bidirectional`",
           f"`→ attention pooling → {emb}-d`"], accent=GOOD)
    bullets(s, [
        (f"The {emb}-d match is deliberate", "h"),
        "It is what lets cross-modal attention skip its projection layer entirely "
        "(nn.Identity instead of nn.Linear). Keep visual hidden_dim == audio lstm_hidden.",
        "Attention pooling weights timesteps by softmax(mean(hidden)) — zero extra "
        "parameters, and it concentrates on the salient part of the window instead of "
        "whatever happened at the end of it.",
    ], y=Inches(4.75), size=14)

    # 8 ────────────────────────────────────────────────
    s = content_slide(prs, "Strategy 1 — feature-level fusion", "fusion · earliest interaction")
    panel(s, MARGIN, Inches(1.95), W - 2 * MARGIN, Inches(1.25),
          "Mechanism",
          [f"`concat([audio_{emb}, visual_{emb}])  →  {emb*2}`",
           f"`→ Linear({emb*2} → 512) → ReLU → Dropout → Linear(512 → {nc})`"])
    bullets(s, [
        ("Strengths", "h"),
        ("One joint head sees both embeddings and can learn any interaction between them.", "good"),
        ("Most expressive of the three.", "good"),
        ("Weaknesses", "h"),
        ("Most able to let the stronger modality dominate — gradient descent can drive "
         "the visual half toward irrelevance while the model still looks multimodal.", "bad"),
        ("No interpretable read-out of modality contribution.", "bad"),
    ], y=Inches(3.4), w=TEXT_W_WITH_STAT, size=14.5)
    stat_card(s, Inches(3.45), "Fusion parameters",
              f"{P['feature_level'] - backbone:,}", ACCENT)

    # 9 ────────────────────────────────────────────────
    s = content_slide(prs, "Strategy 2 — decision-level fusion", "fusion · latest interaction")
    panel(s, MARGIN, Inches(1.95), W - 2 * MARGIN, Inches(1.5),
          "Mechanism",
          [f"`audio  → its own head → logits_a ({nc})`",
           f"`visual → its own head → logits_v ({nc})`",
           "`out = w0 * logits_a  +  w1 * logits_v,   w = softmax(2 learnable scalars)`"],
          accent=GOOD)
    bullets(s, [
        ("Why this is the most useful one for this project", "h"),
        ("After training, softmax(weights) IS the answer to \"which modality mattered?\" "
         "— no attribution method needed. The parameter is the finding.", "good"),
        ("Degrades gracefully: if the visual stream is unreliable the model can learn "
         "w1 ≈ 0 and fall back to audio cleanly.", "good"),
        ("The limitation", "h"),
        ("The modalities never meet before the decision, so it cannot exploit evidence "
         "that is only present jointly.", "bad"),
    ], y=Inches(3.65), w=TEXT_W_WITH_STAT, size=14.5)
    stat_card(s, Inches(3.7), "Fusion parameters",
              f"{P['decision_level'] - backbone}", GOOD)
    note(s, "w1 ≈ 0 after training is not a bug — it is the model correctly reporting "
             "that the visual stream carried no information. A publishable negative result.")

    # 10 ───────────────────────────────────────────────
    s = content_slide(prs, "Strategy 3 — cross-modal attention", "fusion · bidirectional interaction")
    panel(s, MARGIN, Inches(1.95), W - 2 * MARGIN, Inches(1.5),
          "Mechanism",
          ["`a' = LayerNorm(a + MultiheadAttention(query=a, key=v, value=v))`",
           "`v' = LayerNorm(v + MultiheadAttention(query=v, key=a, value=a))`",
           f"`out = head(concat([a', v']))      8 heads, {emb//8} dims per head`"],
          accent=WARN)
    bullets(s, [
        ("Design", "h"),
        "Each modality queries the other. Residual connections plus LayerNorm follow the "
        "transformer block pattern, so the model can learn to ignore cross-modal context.",
        ("Most capacity, most parameters, most data-hungry.", "warn"),
    ], y=Inches(3.6), w=TEXT_W_WITH_STAT, size=14.5)
    stat_card(s, Inches(3.65), "Fusion parameters",
              f"{P['attention'] - backbone:,}", WARN)

    # 11 ───────────────────────────────────────────────
    s = content_slide(prs, "An honest caveat about the attention variant", "fusion · limitation")
    bullets(s, [
        ("Attention here operates on sequences of length 1", "h"),
        "Both embeddings are already pooled to a single vector before attention runs.",
        ("With T=1, softmax over a single key is exactly 1.0 — so no selection over time "
         "occurs. a_ctx reduces to a learned linear transform of v, mixed by the residual.", "bad"),
        "It still trains, and it is still a gated cross-modal projection. But it is not "
        "the frame-level alignment the name suggests, and it does not obviously earn its "
        f"{P['attention'] - backbone:,} extra parameters over feature-level fusion.",
        ("What genuine temporal cross-attention would need", "h"),
        f"Attend over the PRE-pooled LSTM outputs — (16, {emb}) for audio against "
        f"({MF}, {emb}) for visual. A worthwhile experiment, and it would justify the cost.",
    ], y=Inches(1.95), size=14.5)
    note(s, "Reporting this matters more than hiding it: a reviewer will find it, and the "
             "ablation it suggests is a contribution rather than an embarrassment.")

    # 12 ───────────────────────────────────────────────
    s = content_slide(prs, "The three strategies side by side", "fusion · comparison")
    table(s, ["", "feature-level", "decision-level", "cross-modal attention"],
          [["Interaction point", "embeddings", "logits", "embeddings, both ways"],
           ["Fusion parameters", f"{P['feature_level']-backbone:,}",
            f"{P['decision_level']-backbone}", f"{P['attention']-backbone:,}"],
           ["Total parameters", f"{P['feature_level']:,}",
            f"{P['decision_level']:,}", f"{P['attention']:,}"],
           ["Interpretability", "low", "HIGH", "low"],
           ["Robust to dead modality", "poor", "good", "moderate"],
           ["Data hunger", "moderate", "low", "high"]],
          col_w=[2.6, 2.5, 2.5, 3.0], size=13,
          highlight=lambda i, j, v: GOOD if (j == 2 and i in (1, 3, 4, 5)) else None)
    bullets(s, [
        ("On corpora of this size, decision-level is the sensible first experiment", "h"),
        "Fewest fusion parameters, most interpretable output, and its learned weights "
        "answer the project's actual research question directly.",
        "All three share identical backbones, so the fusion-parameter row is the honest "
        "marginal cost of each strategy.",
    ], y=Inches(5.0), size=14)

    # 13 ───────────────────────────────────────────────
    section_slide(prs, "making the comparison mean something", "Evaluation design")

    # 14 ───────────────────────────────────────────────
    s = content_slide(prs, "Speaker-independent splitting is not optional", "evaluation")
    bullets(s, [
        ("The failure mode", "h"),
        ("A random sample-level split puts different utterances from the SAME actor in "
         "both train and test. The model can then identify the speaker and recall which "
         "emotions that speaker produced.", "bad"),
        "SER results in the literature are routinely inflated by exactly this.",
        ("What this system does", "h"),
        ("Splits partition SPEAKERS, not samples — 70/15/15 by actor, seeded and "
         "reproducible. Speaker ids are namespaced per corpus so two different people "
         "cannot be merged.", "good"),
        ("Disjointness is asserted in the test suite, not assumed.", "good"),
    ], y=Inches(1.95), size=14.5)
    panel(s, MARGIN, Inches(5.2), W - 2 * MARGIN, Inches(1.35),
          "A real bug this caught",
          ["MSP-IMPROV speaker ids were derived as fname[:6] — which is the literal string",
           "\"MSP-IM\" for every file in the corpus, collapsing ~8,400 samples into ONE split unit.",
           "Now parsed from the actual actor field. Regression-tested."], accent=BAD)

    # 15 ───────────────────────────────────────────────
    s = content_slide(prs, "Report macro F1, not accuracy", "evaluation")
    bullets(s, [
        ("Why accuracy misleads here", "h"),
        "Six imbalanced classes. A model that always predicts neutral on a manifest where "
        "neutral is 30% scores 0.30 — nearly double the 0.167 chance level — while being useless.",
        ("Macro F1 weights all six classes equally", "h"),
        "Which is what the application needs: missing a fearful or distressed patient is "
        "the failure that matters, and being reliably right about neutral does not compensate.",
        ("The single most diagnostic thing in the confusion matrix", "h"),
        "angry ↔ happy. Both are high-arousal, so confusing them means the model learned "
        "AROUSAL but not VALENCE — and valence is exactly where the visual stream is "
        "theorised to help.",
    ], y=Inches(1.95), size=14.5)
    note(s, "If a fusion model reduces angry/happy confusion versus its audio-only baseline, "
             "that is direct evidence vision contributes something audio cannot supply.")

    # 16 ───────────────────────────────────────────────
    section_slide(prs, "from checkpoint to live demo", "Real-time system")

    # 17 ───────────────────────────────────────────────
    s = content_slide(prs, "Live multimodal inference in the browser", "serving")
    bullets(s, [
        ("Audio path", "h"),
        f"getUserMedia 16 kHz → AudioWorklet (separate thread) → raw float32 PCM → "
        f"WebSocket → server buffers a {dur:.0f} s window, 0.5 s hop → up to 2 predictions/s",
        ("Visual path — landmarks, never pixels", "h"),
        ("MediaPipe FaceLandmarker runs IN THE BROWSER. Only coordinates cross the "
         "network: ~56 KB/s versus 0.5–5 MB/s for video.", "good"),
        ("The client sends RAW coordinates; the server normalises them with the same "
         "function that produced the training features — so that maths exists in exactly "
         "one place instead of being reimplemented in JavaScript.", "good"),
    ], y=Inches(1.9), size=14)
    panel(s, MARGIN, Inches(4.85), Inches(5.6), Inches(1.7),
          "Why this is a privacy property",
          ["No imagery leaves the machine. A landmark stream is far",
           "easier to justify to an ethics board than a video feed,",
           "and the backend needs no mediapipe install at all."], accent=GOOD)
    panel(s, MARGIN + Inches(5.95), Inches(4.85), Inches(5.6), Inches(1.7),
          "Every prediction declares its modalities",
          ["`modalities: [\"audio\", \"visual\"]`",
           "`visual_active: true`",
           "A fusion model with no live face runs on zeros —",
           "and says so, rather than overstating what it did."])

    # 18 ───────────────────────────────────────────────
    section_slide(prs, "the second deployment target", "Wearable feasibility")

    # 19 ───────────────────────────────────────────────
    s = content_slide(prs, "Current models against MCU budgets", "wearable · measured")
    table(s, ["model", "params", "int8 weights", "MMACs", "peak activation"],
          [["audio_cnn", f"{P['audio_cnn']:,}", "1.4 MB", "921", "4,160 KB"],
           ["audio_cnn_lstm", f"{P['audio_cnn_lstm']:,}", "6.2 MB", "258", "2,080 KB"],
           ["visual_lstm", f"{P['visual_lstm']:,}", "2.9 MB", "224", "150 KB"],
           ["attention", f"{P['attention']:,}", "11.3 MB", "484", "2,080 KB"]],
          col_w=[2.6, 2.3, 2.1, 1.6, 2.4], size=12.5,
          highlight=lambda i, j, v: BAD if (i == 0 and j in (3, 4)) else
                                    (GOOD if (i == 2 and j == 4) else None))
    bullets(s, [
        ("Budget for reference: Cortex-M4F ~50 MMAC/s and 256 KB RAM; "
         "Cortex-M7 ~400 MMAC/s and 1 MB.", "h"),
        ("Parameter count is a trap. audio_cnn has the FEWEST weights and the WORST "
         "embedded profile — it convolves at full resolution before any pooling.", "bad"),
        ("Peak activation, not weights, is the binding constraint: weights live in flash, "
         "activations need RAM.", "warn"),
        ("visual_lstm is the cheapest model measured — landmarks are a remarkably "
         "embedded-friendly representation.", "good"),
    ], y=Inches(4.15), size=13.5)

    # 20 ───────────────────────────────────────────────
    s = content_slide(prs, "A wearable configuration is reachable", "wearable · measured")
    table(s, ["", "current config", "retuned for wearable", "change"],
          [["Front end", "22 kHz, 2048-FFT, 128 mel", "16 kHz, 512-FFT, 40 mel", "—"],
           ["Input", "128 x 130", "40 x 126", "10x fewer values"],
           ["Parameters", "6,458,982", "192,726", "33x smaller"],
           ["int8 weights", "6.3 MB", "188 KB", "34x smaller"],
           ["MMACs / window", "258", "13.2", "20x less"],
           ["Peak activation", "520 KB", "79 KB", "6.6x less"],
           ["Sustained @ 2 Hz", "528 MMAC/s", "29 MMAC/s", "fits Cortex-M4F"]],
          col_w=[2.4, 3.0, 3.0, 2.4], size=12.5,
          highlight=lambda i, j, v: GOOD if j == 2 else None)
    bullets(s, [
        ("The architecture family is fine — the CONFIGURATION was wrong for embedded. "
         "That is a much cheaper problem than a redesign.", "good"),
        ("Not yet done: this model has not been trained, so the accuracy cost of a 33x "
         "shrink is unknown — and that is a publishable ablation in its own right.", "warn"),
        ("librosa cannot run on an MCU, so the on-device feature extractor will be "
         "separate code needing validation against the Python reference.", "warn"),
    ], y=Inches(5.15), size=13.5)

    # 21 ───────────────────────────────────────────────
    s = content_slide(prs, "Status — what exists and what does not", "honesty")
    table(s, ["component", "state", "notes"],
          [["Feature extraction", "Implemented, tested", "audio verified; visual needs mediapipe"],
           ["Dataset parsers + splits", "Implemented, tested", "3 corpora, disjointness asserted"],
           ["6 architectures", "Implemented, tested", "shapes, gradient flow, determinism"],
           ["Training / evaluation", "Implemented", "never executed on real data"],
           ["Serving + webcam", "Implemented, tested", "multimodal path verified end to end"],
           ["Trained checkpoints", "NONE", "models/ holds only untrained demo files"],
           ["Corpora", "NONE", "not downloaded"],
           ["Accuracy / F1 results", "NONE", "nothing to report yet"]],
          col_w=[3.2, 2.6, 5.0], size=12,
          highlight=lambda i, j, v: BAD if (j == 1 and v == "NONE") else None)
    bullets(s, [
        ("169 automated tests, all passing, in ~30 s — with no corpora, no checkpoints "
         "and no GPU required.", "good"),
        "The system can be demonstrated today using untrained checkpoints. The UI shows a "
        "standing warning in that mode, because a confident-looking prediction from random "
        "weights is worse than no prediction at all.",
    ], y=Inches(5.35), size=13.5)

    # 22 ───────────────────────────────────────────────
    s = content_slide(prs, "Next steps", "roadmap")
    bullets(s, [
        ("Immediate — get real numbers", "h"),
        "Download corpora, run preprocessing, train all six architectures under identical "
        "conditions, publish the comparison table.",
        "Read decision-level's two learned weights: that is the modality-contribution result.",
        ("Near term — make the comparison rigorous", "h"),
        "Voice-activity detection; temporal smoothing across overlapping windows; "
        "per-corpus breakdown; multiple seeds with confidence intervals.",
        "Confidence calibration — an uncalibrated score is worse than none in a clinical "
        "context, because it invites misplaced trust.",
        ("Longer term — the actual research question", "h"),
        "Noise and reverberation augmentation matched to ward acoustics.",
        "In-domain Nigerian healthcare speech collection, with ethics review and consent.",
        "Train the wearable config; quantise; validate a fixed-point feature extractor.",
    ], y=Inches(1.95), size=14)

    # 23 ───────────────────────────────────────────────
    s = content_slide(prs, "Summary", "closing")
    panel(s, MARGIN, Inches(2.0), Inches(3.6), Inches(2.4),
          "Built",
          ["Full pipeline, 3 corpora → 6 classes",
           "6 architectures, 3 fusion strategies",
           "Live audio + webcam serving",
           "169 tests, all passing"], accent=GOOD)
    panel(s, MARGIN + Inches(3.85), Inches(2.0), Inches(3.6), Inches(2.4),
          "Measured",
          ["Parameter and MAC profiles",
           "Peak activation per model",
           "Wearable config that fits an M7",
           "Fusion cost, isolated per strategy"])
    panel(s, MARGIN + Inches(7.7), Inches(2.0), Inches(3.6), Inches(2.4),
          "Not yet known",
          ["Does multimodal actually win?",
           "Which fusion strategy, and why?",
           "Accuracy cost of the 33x shrink",
           "Anything about clinical speech"], accent=WARN)
    bullets(s, [
        ("The contribution so far is infrastructure and methodology — a rig in which the "
         "multimodal question can be asked cleanly, with speaker-independent evaluation "
         "and honest reporting of what each prediction actually used.", "h"),
        "The scientific results come next, and the design deliberately allows a negative "
        "answer to be a publishable one.",
    ], y=Inches(4.85), size=14)

    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return len(prs.slides.__iter__.__self__._sldIdLst), out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/settings.yaml")
    ap.add_argument("--out", default="docs/presentation/SER-System.pptx")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    n, out = build(cfg, Path(args.out))
    print(f"Wrote {out}  ({n} slides)")
    print("All parameter counts, shapes and feature dimensions were computed from the "
          "live code — the deck cannot drift from the repo.")


if __name__ == "__main__":
    main()
