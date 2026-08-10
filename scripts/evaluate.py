"""
Evaluation and latency benchmarking.

Usage:
    python scripts/evaluate.py --checkpoint models/audio_cnn_lstm_best.pt
    python scripts/evaluate.py --checkpoint models/attention_best.pt --latency_runs 200
"""
import sys
from contextlib import nullcontext
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import json
import time
import yaml
import numpy as np
import pandas as pd
import torch
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    accuracy_score, classification_report,
    confusion_matrix, f1_score,
)
from torch.utils.data import DataLoader
from tqdm import tqdm

from src.constants import LANDMARK_DIM
from src.datasets import EmotionDataset, LABEL2IDX, IDX2LABEL, UNIFIED
from src.models.builder import build_model, feature_height, is_multimodal, n_frames


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint",   required=True)
    p.add_argument("--config",       default="config/settings.yaml")
    p.add_argument("--latency_runs", type=int, default=100)
    return p.parse_args()


def predict(model, loader, device, multi):
    model.eval()
    all_preds, all_labels = [], []
    with torch.no_grad():
        for batch in tqdm(loader, desc="Evaluating"):
            if multi:
                xa, xv, y = batch[0].to(device), batch[1].to(device), batch[2]
                logits = model(xa, xv)
            else:
                xa, y = batch[0].to(device), batch[1]
                logits = model(xa)
            all_preds.extend(logits.argmax(1).cpu().tolist())
            all_labels.extend(y.tolist())
    return np.array(all_labels), np.array(all_preds)


def benchmark_latency(model, cfg, device, multi, n_runs, feature="mel"):
    # Shapes must come from the config the model was BUILT from, and from the
    # feature it expects — otherwise an mfcc checkpoint gets a mel-shaped dummy.
    dummy_a = torch.randn(1, 1, feature_height(cfg, feature), n_frames(cfg)).to(device)
    dummy_v = torch.zeros(1, cfg["visual"]["max_frames"], LANDMARK_DIM).to(device)

    def infer():
        if multi:
            model(dummy_a, dummy_v)
        else:
            model(dummy_a)

    model.eval()
    with torch.no_grad():
        for _ in range(10):  # warmup
            infer()

        times = []
        for _ in range(n_runs):
            if device.type == "cuda":
                torch.cuda.synchronize()
            t0 = time.perf_counter()
            infer()
            if device.type == "cuda":
                torch.cuda.synchronize()
            times.append((time.perf_counter() - t0) * 1000)

    return np.array(times)


def main():
    args = parse_args()
    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    ckpt = torch.load(args.checkpoint, map_location=device)
    model_name = ckpt["model_name"]
    ckpt_cfg   = ckpt.get("cfg", cfg)
    feature    = ckpt.get("feature", "mel")

    model = build_model(model_name, ckpt_cfg, len(UNIFIED), feature).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()
    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Model: {model_name} | Parameters: {n_params:,} | Device: {device}")

    proc = Path(cfg["data"]["processed_path"])
    test_df = pd.read_csv(proc / "test_split.csv")

    multi    = is_multimodal(model_name)
    modality = "multimodal" if multi else ("visual" if model_name == "visual_lstm" else "audio")
    ds       = EmotionDataset(test_df, str(proc), modality, feature,
                              max_frames=cfg["visual"]["max_frames"])
    loader   = DataLoader(ds, batch_size=32, shuffle=False, num_workers=4)

    labels, preds = predict(model, loader, device, multi)

    acc  = accuracy_score(labels, preds)
    f1_w = f1_score(labels, preds, average="weighted")
    f1_m = f1_score(labels, preds, average="macro")

    print(f"\nAccuracy:      {acc:.4f}")
    print(f"Weighted F1:   {f1_w:.4f}")
    print(f"Macro F1:      {f1_m:.4f}")
    print(f"\n{classification_report(labels, preds, target_names=UNIFIED)}")

    # confusion matrix
    results_dir = Path(cfg["output"]["results_dir"])
    results_dir.mkdir(exist_ok=True)
    cm = confusion_matrix(labels, preds)
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=UNIFIED, yticklabels=UNIFIED, ax=ax)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(f"{model_name} — Confusion Matrix (n={len(labels)})")
    fig.tight_layout()
    cm_path = results_dir / f"{model_name}_confusion.png"
    fig.savefig(cm_path, dpi=150)
    print(f"Confusion matrix: {cm_path}")

    # latency benchmark
    print(f"\nLatency benchmark ({args.latency_runs} runs)...")
    times = benchmark_latency(model, ckpt_cfg, device, multi, args.latency_runs, feature)
    lat_mean = times.mean()
    lat_p50  = np.percentile(times, 50)
    lat_p95  = np.percentile(times, 95)
    lat_p99  = np.percentile(times, 99)
    print(f"Mean: {lat_mean:.2f} ms | p50: {lat_p50:.2f} ms | p95: {lat_p95:.2f} ms | p99: {lat_p99:.2f} ms")

    results = {
        "model":           model_name,
        "n_params":        n_params,
        "n_test":          int(len(labels)),
        "accuracy":        round(float(acc),  4),
        "f1_weighted":     round(float(f1_w), 4),
        "f1_macro":        round(float(f1_m), 4),
        "latency_mean_ms": round(float(lat_mean), 3),
        "latency_p50_ms":  round(float(lat_p50),  3),
        "latency_p95_ms":  round(float(lat_p95),  3),
        "latency_p99_ms":  round(float(lat_p99),  3),
        "device":          str(device),
    }
    out_json = results_dir / f"{model_name}_results.json"
    out_json.write_text(json.dumps(results, indent=2))
    print(f"Results: {out_json}")


if __name__ == "__main__":
    main()
