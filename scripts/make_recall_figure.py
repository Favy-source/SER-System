"""
Per-class recall figure for the interview deck.

    .venv/bin/python scripts/make_recall_figure.py

WHY A BAR CHART AND NOT THE CONFUSION MATRIX
    The slide's placeholder is 6.10 x 2.25 in — a 2.7:1 box. A 6x6 confusion
    matrix forced into that aspect is unreadable at projector size.

    More importantly, the data's job here is a magnitude comparison across six
    classes, and that job picks a bar chart. The confusion matrix answers "what
    was it mistaken FOR", which is a second-order question; the finding worth
    five seconds of a panel's attention is the CLIFF — three high-arousal classes
    near 0.88, then everything else collapsing.

    The full matrix stays in results/ for anyone who asks.

DESIGN
    One series, so one hue and no legend — the title names the measure. Direct
    value labels on every bar (there are only six, so "never label every point"
    does not bite). Recessive axes: no frame, no grid, no x-axis at all, since
    the labels carry the numbers. Colours are the deck's own tokens so the figure
    reads as part of the slide rather than an import.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results/audio_cnn_lstm_results.json"
DEST = ROOT / "docs/presentation/fig_per_class_recall.png"

# The deck's own palette, read off the pptx rather than guessed.
NAVY, TEAL, INK, MUTED, SURFACE = "#1E2761", "#1C7293", "#1A2333", "#6B7A90", "#F1F5FA"


def main():
    m = json.loads(RESULTS.read_text())
    per = m["per_class"]
    rows = sorted(((k, v["recall"], int(v["support"])) for k, v in per.items()),
                  key=lambda r: r[1])          # ascending: best ends up on top

    # Support folded into the axis label rather than given its own right-hand
    # column: at slide size that column left a wide dead gap, and n belongs with
    # the class name anyway.
    labels = [f"{k}  (n={sup})" for k, _, sup in rows]
    vals = [v for _, v, _ in rows]

    fig, ax = plt.subplots(figsize=(6.10, 2.25), dpi=300)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    ax.barh(labels, vals, height=0.62, color=TEAL, zorder=2)

    for y, (name, v, sup) in enumerate(rows):
        ax.text(v + 0.018, y, f"{v:.2f}", va="center", ha="left",
                fontsize=8, color=INK, fontweight="bold", zorder=3)

    ax.set_xlim(0, 1.02)
    ax.set_title(f"Per-class recall — speaker-independent, {m['n_test']} clips, "
                 f"{len(m['test_speakers'])} held-out actors",
                 fontsize=8.5, color=NAVY, fontweight="bold", loc="left", pad=8)

    # Recessive axes: the value labels carry the numbers, so the x-axis is noise.
    ax.get_xaxis().set_visible(False)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=7.5, colors=INK)

    fig.text(0.012, 0.035,
             "Arousal is learned; valence is not — the gap this research targets.",
             fontsize=6.8, color=MUTED, style="italic")

    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(DEST, facecolor=SURFACE, edgecolor="none")
    print(f"Wrote {DEST.relative_to(ROOT)}")
    for name, v, sup in reversed(rows):
        print(f"  {name:9s} recall {v:.3f}  (n={sup})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
