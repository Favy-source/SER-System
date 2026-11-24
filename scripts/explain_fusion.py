"""
Show what the three fusion strategies actually do, by running them.

    python3 scripts/explain_fusion.py
    python3 scripts/explain_fusion.py --verbose

Walks the same tensors the real pipeline uses and prints, at each stage:

  1. how audio and visual reach a shared 512-d embedding
  2. where each strategy combines them, and what it combines
  3. how sensitive each one is to the visual stream, measured
  4. what decision-level fusion's two learnable weights mean

The weights here are randomly initialised, so the *values* are noise. The
shapes, parameter counts, and combination points are exactly the real ones —
which is the part worth understanding before any training happens.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

import numpy as np
import torch
import torch.nn.functional as F
import yaml

from src.constants import LANDMARK_DIM
from src.datasets import UNIFIED
from src.models.builder import build_model, feature_height, n_frames

BAR = "=" * 74
SUB = "-" * 74


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default="config/settings.yaml")
    p.add_argument("--verbose", action="store_true", help="print per-layer shapes")
    p.add_argument("--seed", type=int, default=0)
    return p.parse_args()


def section(title):
    print(f"\n{BAR}\n  {title}\n{BAR}")


def main():
    args = parse_args()
    torch.manual_seed(args.seed)
    cfg = yaml.safe_load(open(args.config))

    H, T = feature_height(cfg, "mel"), n_frames(cfg)
    MF   = cfg["visual"]["max_frames"]
    nc   = len(UNIFIED)

    audio  = torch.randn(1, 1, H, T)
    visual = torch.randn(1, MF, LANDMARK_DIM)

    # ------------------------------------------------------------------
    section("1. THE TWO STREAMS — different data, same embedding width")

    print(f"""
  audio  : mel spectrogram        {tuple(audio.shape)}
           {H} mel bands x {T} frames, from 3 s at {cfg['audio']['sample_rate']} Hz

  visual : landmark sequence      {tuple(visual.shape)}
           {MF} frames x {LANDMARK_DIM} values ({LANDMARK_DIM // 3} landmarks x 3 coords)
""")

    a_net = build_model("audio_cnn_lstm", cfg, nc, "mel")
    v_net = build_model("visual_lstm",    cfg, nc)
    a_net.eval(); v_net.eval()

    with torch.no_grad():
        a_cnn = a_net.cnn(audio)
        a_emb = a_net.embed(audio)
        v_emb = v_net.embed(visual)

    print(f"  AudioCNNLSTM   CNN {tuple(a_cnn.shape)}"
          f"  ->  reshape to sequence (1, {a_cnn.shape[3]}, {a_cnn.shape[1]*a_cnn.shape[2]})")
    print(f"                 BiLSTM + attention pooling  ->  embed {tuple(a_emb.shape)}")
    print(f"  VisualLSTM     Linear({LANDMARK_DIM}->256) -> BiLSTM + attention pooling")
    print(f"                 ->  embed {tuple(v_emb.shape)}")
    print(f"""
  Both collapse to {a_net._embed_dim}-d. That match is deliberate: it is what lets
  cross-modal attention skip a projection layer entirely (nn.Identity instead
  of nn.Linear). Keep visual_lstm.hidden_dim == audio_cnn_lstm.lstm_hidden.
""")

    # ------------------------------------------------------------------
    section("2. THE THREE STRATEGIES — a ladder of increasing coupling")

    models = {}
    for name in ("feature_level", "decision_level", "attention"):
        m = build_model(name, cfg, nc, "mel"); m.eval()
        models[name] = m

    print(f"""
  feature_level    EARLIEST interaction
      cat([audio_512, visual_512]) -> 1024 -> Linear(1024->512) -> Linear(512->6)
      One joint head sees both embeddings and can learn any interaction.
      Most expressive; most able to let the stronger modality dominate.

  decision_level   LATEST interaction
      audio  -> its own head -> logits_a (1, 6)
      visual -> its own head -> logits_v (1, 6)
      out = w0*logits_a + w1*logits_v,  where w = softmax(2 learnable scalars)
      TWO fusion parameters in total. The modalities never meet before the
      decision, so it cannot exploit joint-only evidence — but the weights are
      directly readable as "which modality mattered".

  attention        BIDIRECTIONAL interaction
      a' = LayerNorm(a + MultiheadAttention(query=a, key=v, value=v))
      v' = LayerNorm(v + MultiheadAttention(query=v, key=a, value=a))
      out = head(cat([a', v']))
      Each modality queries the other, with residuals so it can learn to ignore
      the other stream. Most capacity, most parameters, most data-hungry.
""")

    print(SUB)
    print(f"  {'strategy':<16}{'total params':>14}{'fusion params':>15}{'head input':>13}")
    print(SUB)
    for name, m in models.items():
        total = sum(p.numel() for p in m.parameters())
        backbone = sum(p.numel() for p in m.audio.parameters()) + \
                   sum(p.numel() for p in m.visual.parameters())
        fusion_only = total - backbone
        head_in = {"feature_level": "1024", "decision_level": "n/a (logits)", "attention": "1024"}[name]
        print(f"  {name:<16}{total:>14,}{fusion_only:>15,}{head_in:>13}")
    print(SUB)
    print("  feature_level and attention strip the unused unimodal classifier heads;\n"
          "  decision_level retains them because it mixes unimodal logits.")

    # ------------------------------------------------------------------
    section("3. HOW MUCH DOES THE VISUAL STREAM MOVE THE OUTPUT?")

    print("""
  Same audio every time. Compare three visual conditions:
    zeros    what the server feeds when no camera is attached
    face A   one landmark window
    face B   a different landmark window

  The gap tells you whether the visual branch is wired in and being used.
""")
    zeros  = torch.zeros(1, MF, LANDMARK_DIM)
    faceA  = torch.randn(1, MF, LANDMARK_DIM)
    torch.manual_seed(args.seed + 99)
    faceB  = torch.randn(1, MF, LANDMARK_DIM)

    print(SUB)
    print(f"  {'strategy':<16}{'|zeros - faceA|':>18}{'|faceA - faceB|':>18}{'verdict':>16}")
    print(SUB)
    for name, m in models.items():
        with torch.no_grad():
            p0 = F.softmax(m(audio, zeros), 1)[0].numpy()
            pA = F.softmax(m(audio, faceA), 1)[0].numpy()
            pB = F.softmax(m(audio, faceB), 1)[0].numpy()
        d_zero = float(np.abs(p0 - pA).sum())
        d_face = float(np.abs(pA - pB).sum())
        verdict = "responsive" if d_zero > 1e-4 else "NOT WIRED"
        print(f"  {name:<16}{d_zero:>18.4f}{d_face:>18.4f}{verdict:>16}")
    print(SUB)
    print("""  Total absolute change in the probability vector (max possible = 2.0).
  Non-zero in both columns means the model genuinely consumes the visual
  input rather than ignoring it. This is the exact property
  test_visual_input_changes_fusion_prediction asserts for all three.""")

    # ------------------------------------------------------------------
    section("4. DECISION-LEVEL WEIGHTS — the interpretable one")

    dl = models["decision_level"]
    w = torch.softmax(dl.weights, dim=0).detach().numpy()
    print(f"""
  raw parameter      : {dl.weights.detach().numpy().round(4).tolist()}
  softmax(weights)   : [audio {w[0]:.4f}, visual {w[1]:.4f}]   (sums to {w.sum():.4f})

  After training, these two numbers ARE the answer to the project's central
  research question: how much does the visual modality contribute?

    w1 near 0.5   both modalities carry comparable weight
    w1 near 0.0   the visual stream was not useful and the model learned to
                  ignore it — a legitimate and publishable NEGATIVE result
    w1 near 1.0   visual dominates, which on acted corpora would be surprising
                  and worth investigating for leakage

  No attribution method needed; the parameter is the finding. Neither
  feature_level nor attention can give you this directly, which is the main
  reason all three are kept rather than picking the best scorer.

  Read them from a trained checkpoint with:

    ckpt = torch.load("models/decision_level_best.pt", weights_only=False)
    m = build_model("decision_level", ckpt["cfg"], 6, ckpt["feature"])
    m.load_state_dict(ckpt["model"])
    print(torch.softmax(m.weights, dim=0))
""")

    # ------------------------------------------------------------------
    section("5. TEMPORAL CROSS-MODAL ATTENTION — sequence alignment")

    at = models["attention"]
    with torch.no_grad():
        a_seq = at.audio.encode_sequence(audio)
        v_seq = at.v_proj(at.visual.encode_sequence(visual))
    print(f"""
  Attention operates on the PRE-pooled temporal sequences:

    audio  sequence  {tuple(a_seq.shape)}
    visual sequence  {tuple(v_seq.shape)}

  Audio attends across all {v_seq.shape[1]} visual frames (with zero-padded frames masked)
  and visual attends across all {a_seq.shape[1]} audio steps, before residual LayerNorm
  and temporal attention pooling. Q, K, and V projections all receive gradients.

  v_proj is {type(at.v_proj).__name__} here, because both embeddings are already {at.audio._embed_dim}-d.
""")

    section("WHAT TO EXPECT WHEN YOU TRAIN")
    print("""
  Report macro F1, not accuracy — six imbalanced classes make accuracy reward
  the majority class. Then read the confusion matrix for angry/happy: both are
  high-arousal, and separating them needs valence, which is the subtlest thing
  in the audio channel and where vision is theorised to help most.

  If a fusion model reduces angry/happy confusion versus its audio-only
  baseline, that is direct evidence the visual stream contributes something
  audio cannot supply. If it does not, the multimodal hypothesis is not
  supported on this data — which is itself a result worth reporting, not a
  failure.
""")


if __name__ == "__main__":
    main()
