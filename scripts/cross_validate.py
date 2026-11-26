"""
Resumable k-fold speaker-independent cross-validation harness.

Usage:
    .venv/bin/python scripts/cross_validate.py --models audio_cnn_lstm --folds 5
    .venv/bin/python scripts/cross_validate.py \
        --models audio_cnn_lstm,visual_lstm,decision_level,feature_level,attention \
        --folds 5 --only-with-video --resume
    .venv/bin/python scripts/cross_validate.py \
        --models audio_cnn_lstm --folds 5 --split-mode random   # SD ablation control

Outputs (in cfg["output"]["results_dir"]):
    cv_<run_id>.json           per-fold + mean±std + pooled OOF metrics & confusion matrix
    cv_<run_id>_confusion.png  pooled out-of-fold confusion matrix
    cv_folds/<run_id>/fold_<k>.json  per-fold cache enabling --resume
"""
import argparse
import json
import sys
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import torch
import torch.nn as nn
import yaml
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.utils.class_weight import compute_class_weight
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader

from src.datasets import (
    EmotionDataset,
    LABEL2IDX,
    UNIFIED,
    random_kfolds,
    speaker_independent_kfolds,
)
from src.models.builder import FUSION, UNIMODAL, build_model, is_multimodal

ALL_MODELS = sorted(UNIMODAL | FUSION)


def _run_epoch(model, loader, criterion, optimizer, scaler, device, train: bool, multi: bool):
    model.train(train)
    total_loss = 0.0
    correct = 0
    total = 0

    for batch in loader:
        if multi:
            xa, xv, y = batch[0].to(device), batch[1].to(device), batch[2].to(device)
        else:
            xa, y = batch[0].to(device), batch[1].to(device)
            xv = None

        amp_ctx = torch.autocast("cuda") if scaler else nullcontext()
        with torch.set_grad_enabled(train), amp_ctx:
            logits = model(xa, xv) if multi else model(xa)
            loss = criterion(logits, y)

        if train:
            optimizer.zero_grad()
            if scaler:
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
            else:
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()

        bs = y.size(0)
        total_loss += loss.item() * bs
        correct += (logits.argmax(1) == y).sum().item()
        total += bs

    return total_loss / max(1, total), correct / max(1, total)


def _predict_all(model, loader, device, multi: bool):
    model.eval()
    all_labels: List[int] = []
    all_preds: List[int] = []
    with torch.no_grad():
        for batch in loader:
            if multi:
                xa, xv, y = batch[0].to(device), batch[1].to(device), batch[2]
                logits = model(xa, xv)
            else:
                xa, y = batch[0].to(device), batch[1]
                logits = model(xa)
            all_preds.extend(logits.argmax(1).cpu().tolist())
            all_labels.extend(y.tolist())
    return all_labels, all_preds


def _class_weights(train_df: pd.DataFrame, num_classes: int, device) -> torch.Tensor:
    labels = train_df["label"].map(LABEL2IDX).values
    present = np.unique(labels)
    present_w = compute_class_weight("balanced", classes=present, y=labels)
    weights = np.ones(num_classes, dtype=np.float32)
    weights[present] = present_w
    return torch.tensor(weights, dtype=torch.float32).to(device)


def train_and_eval_fold(
    fold_idx: int,
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    model_name: str,
    feature: str,
    cfg: dict,
    proc_dir: Path,
    device: torch.device,
    epochs: int,
    patience: int,
    seed: int,
    ckpt_dest: Optional[Path] = None,
) -> dict:
    """Train one CV fold with early stopping on val_loss and evaluate on test_df."""
    t0 = time.perf_counter()
    torch.manual_seed(seed + fold_idx)
    np.random.seed(seed + fold_idx)

    tc = cfg["training"]
    multi = is_multimodal(model_name)
    modality = "multimodal" if multi else ("visual" if model_name == "visual_lstm" else "audio")
    max_frames = cfg["visual"]["max_frames"]
    num_workers = int(tc.get("num_workers", 0))
    pin_mem = bool(tc.get("pin_memory", False)) and device.type == "cuda"

    def make_loader(split_df: pd.DataFrame, shuffle: bool) -> DataLoader:
        ds = EmotionDataset(split_df, str(proc_dir), modality, feature, max_frames=max_frames)
        return DataLoader(
            ds,
            batch_size=tc["batch_size"],
            shuffle=shuffle,
            num_workers=num_workers,
            pin_memory=pin_mem,
        )

    train_loader = make_loader(train_df, True)
    val_loader = make_loader(val_df, False)
    test_loader = make_loader(test_df, False)

    num_classes = len(UNIFIED)
    model = build_model(model_name, cfg, num_classes, feature).to(device)
    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)

    criterion = nn.CrossEntropyLoss(weight=_class_weights(train_df, num_classes, device))
    optimizer = AdamW(model.parameters(), lr=tc["learning_rate"], weight_decay=tc["weight_decay"])
    scheduler = CosineAnnealingLR(optimizer, T_max=max(1, epochs))
    scaler = torch.amp.GradScaler("cuda") if tc.get("amp", False) and device.type == "cuda" else None

    best_val_loss = float("inf")
    best_val_acc = 0.0
    best_epoch = 0
    best_state = None
    patience_ctr = 0

    for epoch in range(1, epochs + 1):
        tr_loss, tr_acc = _run_epoch(model, train_loader, criterion, optimizer, scaler, device, True, multi)
        vl_loss, vl_acc = _run_epoch(model, val_loader, criterion, None, scaler, device, False, multi)
        scheduler.step()

        if vl_loss < best_val_loss:
            best_val_loss = vl_loss
            best_val_acc = vl_acc
            best_epoch = epoch
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            patience_ctr = 0
        else:
            patience_ctr += 1
            if patience_ctr >= patience:
                break

    if best_state is not None:
        model.load_state_dict(best_state)
        if ckpt_dest is not None:
            ckpt_dest.parent.mkdir(parents=True, exist_ok=True)
            torch.save({
                "epoch": best_epoch,
                "model": best_state,
                "val_loss": best_val_loss,
                "val_acc": best_val_acc,
                "model_name": model_name,
                "feature": feature,
                "cfg": cfg,
                "fold": fold_idx,
                "test_speakers": sorted(test_df["speaker"].unique().tolist()),
            }, ckpt_dest)

    y_true, y_pred = _predict_all(model, test_loader, device, multi)
    acc = float(accuracy_score(y_true, y_pred))
    f1_m = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    f1_w = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))
    rep = classification_report(
        y_true, y_pred, labels=list(range(num_classes)),
        target_names=UNIFIED, output_dict=True, zero_division=0,
    )

    fold_result = {
        "fold": fold_idx,
        "n_train": int(len(train_df)),
        "n_val": int(len(val_df)),
        "n_test": int(len(test_df)),
        "n_params": int(n_params),
        "best_epoch": int(best_epoch),
        "val_loss": round(float(best_val_loss), 4),
        "val_acc": round(float(best_val_acc), 4),
        "test_acc": round(acc, 4),
        "val_test_gap": round(float(best_val_acc - acc), 4),
        "f1_macro": round(f1_m, 4),
        "f1_weighted": round(f1_w, 4),
        "per_class_recall": {e: round(float(rep[e]["recall"]), 4) for e in UNIFIED},
        "test_speakers": sorted(test_df["speaker"].unique().tolist()),
        "val_speakers": sorted(val_df["speaker"].unique().tolist()),
        "y_true": y_true,
        "y_pred": y_pred,
        "elapsed_sec": round(time.perf_counter() - t0, 1),
    }

    if model_name == "decision_level" and hasattr(model, "weights"):
        w = torch.softmax(model.weights.detach().cpu(), dim=0).tolist()
        fold_result["decision_weights"] = {"audio": round(float(w[0]), 4), "visual": round(float(w[1]), 4)}

    return fold_result


def _aggregate_folds(
    model_name: str,
    feature: str,
    split_mode: str,
    n_splits: int,
    seed: int,
    only_with_video: bool,
    fold_results: List[dict],
) -> dict:
    accs = np.array([f["test_acc"] for f in fold_results], dtype=float)
    f1ms = np.array([f["f1_macro"] for f in fold_results], dtype=float)
    f1ws = np.array([f["f1_weighted"] for f in fold_results], dtype=float)
    val_accs = np.array([f["val_acc"] for f in fold_results], dtype=float)
    gaps = np.array([f["val_test_gap"] for f in fold_results], dtype=float)

    y_true_all = [y for f in fold_results for y in f["y_true"]]
    y_pred_all = [y for f in fold_results for y in f["y_pred"]]
    cm = confusion_matrix(y_true_all, y_pred_all, labels=list(range(len(UNIFIED))))
    pooled_rep = classification_report(
        y_true_all, y_pred_all, labels=list(range(len(UNIFIED))),
        target_names=UNIFIED, output_dict=True, zero_division=0,
    )

    per_class_summary = {}
    for e in UNIFIED:
        vals = np.array([f["per_class_recall"][e] for f in fold_results], dtype=float)
        per_class_summary[e] = {
            "recall_mean": round(float(vals.mean()), 4),
            "recall_std": round(float(vals.std(ddof=0)), 4),
            "pooled_precision": round(float(pooled_rep[e]["precision"]), 4),
            "pooled_recall": round(float(pooled_rep[e]["recall"]), 4),
            "pooled_f1": round(float(pooled_rep[e]["f1-score"]), 4),
            "pooled_support": int(pooled_rep[e]["support"]),
        }

    summary = {
        "model": model_name,
        "feature": feature,
        "split_mode": split_mode,
        "n_splits": n_splits,
        "seed": seed,
        "only_with_video": only_with_video,
        "n_params": fold_results[0]["n_params"],
        "n_total_oof": int(len(y_true_all)),
        "accuracy_mean": round(float(accs.mean()), 4),
        "accuracy_std": round(float(accs.std(ddof=0)), 4),
        "f1_macro_mean": round(float(f1ms.mean()), 4),
        "f1_macro_std": round(float(f1ms.std(ddof=0)), 4),
        "f1_weighted_mean": round(float(f1ws.mean()), 4),
        "f1_weighted_std": round(float(f1ws.std(ddof=0)), 4),
        "val_acc_mean": round(float(val_accs.mean()), 4),
        "val_test_gap_mean": round(float(gaps.mean()), 4),
        "pooled_accuracy": round(float(accuracy_score(y_true_all, y_pred_all)), 4),
        "pooled_f1_macro": round(float(f1_score(y_true_all, y_pred_all, average="macro", zero_division=0)), 4),
        "per_class": per_class_summary,
        "confusion_matrix": cm.tolist(),
        "labels": list(UNIFIED),
        "folds": [{k: v for k, v in f.items() if k not in ("y_true", "y_pred")} for f in fold_results],
    }

    if all("decision_weights" in f for f in fold_results):
        wa = np.array([f["decision_weights"]["audio"] for f in fold_results], dtype=float)
        wv = np.array([f["decision_weights"]["visual"] for f in fold_results], dtype=float)
        summary["decision_weights"] = {
            "audio_mean": round(float(wa.mean()), 4),
            "audio_std": round(float(wa.std(ddof=0)), 4),
            "visual_mean": round(float(wv.mean()), 4),
            "visual_std": round(float(wv.std(ddof=0)), 4),
        }

    return summary


def run_cv(
    df: pd.DataFrame,
    model_name: str,
    cfg: dict,
    proc_dir: Path,
    results_dir: Path,
    *,
    feature: str = "mel",
    n_splits: int = 5,
    split_mode: str = "speaker_independent",
    only_with_video: bool = False,
    epochs: Optional[int] = None,
    patience: Optional[int] = None,
    resume: bool = True,
    save_checkpoints: bool = False,
    model_dir: Optional[Path] = None,
) -> dict:
    """Execute k-fold CV for one model and persist JSON + confusion PNG."""
    tc = cfg["training"]
    seed = int(tc["seed"])
    n_epochs = int(epochs if epochs is not None else tc["epochs"])
    n_patience = int(patience if patience is not None else tc["early_stopping_patience"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    work_df = df.copy()
    need_video = only_with_video or model_name == "visual_lstm"
    if need_video:
        has_lm = work_df["video_path"].apply(
            lambda vp: isinstance(vp, str) and (proc_dir / "landmarks" / f"{Path(vp).stem}.npy").exists()
        )
        work_df = work_df[has_lm].reset_index(drop=True)
        if work_df.empty:
            raise RuntimeError(f"No samples with landmarks found in {proc_dir / 'landmarks'}")

    tag_parts = [model_name]
    if feature != "mel":
        tag_parts.append(feature)
    if split_mode != "speaker_independent":
        tag_parts.append(split_mode)
    if only_with_video:
        tag_parts.append("av")
    run_id = "_".join(tag_parts) + f"_{n_splits}fold"

    fold_cache_dir = results_dir / "cv_folds" / run_id
    fold_cache_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    splitter = speaker_independent_kfolds if split_mode == "speaker_independent" else random_kfolds
    splits = list(splitter(work_df, n_splits=n_splits, seed=seed))

    print(
        f"\n=== CV: {run_id} | samples={len(work_df)} | speakers={work_df['speaker'].nunique()} "
        f"| device={device} | epochs={n_epochs} ===",
        flush=True,
    )

    fold_results: List[dict] = []
    for k, (tr_df, va_df, te_df) in enumerate(splits):
        cache_file = fold_cache_dir / f"fold_{k}.json"
        if resume and cache_file.exists():
            res = json.loads(cache_file.read_text())
            print(
                f"  fold {k+1}/{n_splits} [resumed] | acc={res['test_acc']:.4f} "
                f"macro_f1={res['f1_macro']:.4f} happy={res['per_class_recall']['happy']:.2f} "
                f"sad={res['per_class_recall']['sad']:.2f}",
                flush=True,
            )
            fold_results.append(res)
            continue

        ckpt_dest = (
            (model_dir or Path(cfg["output"]["model_dir"])) / "cv" / run_id / f"fold_{k}.pt"
            if save_checkpoints else None
        )
        res = train_and_eval_fold(
            k, tr_df, va_df, te_df, model_name, feature, cfg, proc_dir,
            device, n_epochs, n_patience, seed, ckpt_dest=ckpt_dest,
        )
        cache_file.write_text(json.dumps(res, indent=2))
        extra = ""
        if "decision_weights" in res:
            dw = res["decision_weights"]
            extra = f" | w=[a:{dw['audio']:.2f}, v:{dw['visual']:.2f}]"
        print(
            f"  fold {k+1}/{n_splits} (ep {res['best_epoch']:2d}, {res['elapsed_sec']:5.1f}s) | "
            f"val={res['val_acc']:.4f} test={res['test_acc']:.4f} macro_f1={res['f1_macro']:.4f} | "
            f"happy={res['per_class_recall']['happy']:.2f} sad={res['per_class_recall']['sad']:.2f}{extra}",
            flush=True,
        )
        fold_results.append(res)

    summary = _aggregate_folds(
        model_name, feature, split_mode, n_splits, seed, only_with_video, fold_results
    )

    out_json = results_dir / f"cv_{run_id}.json"
    out_json.write_text(json.dumps(summary, indent=2))

    # Pooled out-of-fold confusion matrix PNG
    cm = np.array(summary["confusion_matrix"])
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=UNIFIED, yticklabels=UNIFIED, ax=ax)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(
        f"{run_id} — Pooled OOF Confusion (n={summary['n_total_oof']}, "
        f"macro-F1={summary['f1_macro_mean']:.3f}±{summary['f1_macro_std']:.3f})"
    )
    fig.tight_layout()
    fig.savefig(results_dir / f"cv_{run_id}_confusion.png", dpi=150)
    plt.close(fig)

    print(
        f"  -> SUMMARY {run_id}: acc={summary['accuracy_mean']:.4f}±{summary['accuracy_std']:.4f} | "
        f"macro_f1={summary['f1_macro_mean']:.4f}±{summary['f1_macro_std']:.4f} | "
        f"happy={summary['per_class']['happy']['recall_mean']:.3f} "
        f"sad={summary['per_class']['sad']['recall_mean']:.3f} | wrote {out_json}",
        flush=True,
    )
    return summary


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Resumable k-fold speaker-independent cross-validation")
    p.add_argument(
        "--models", "--model", dest="models", default="audio_cnn_lstm",
        help=f"comma-separated model names from {ALL_MODELS}",
    )
    p.add_argument("--feature", default="mel", choices=["mel", "mfcc"])
    p.add_argument("--folds", type=int, default=5)
    p.add_argument(
        "--split-mode", default="speaker_independent", choices=["speaker_independent", "random"],
        help="use 'random' ONLY as a speaker-dependent ablation control (ReQ5)",
    )
    p.add_argument(
        "--only-with-video", action="store_true",
        help="restrict to manifest rows with extracted landmarks so unimodal & fusion share identical samples",
    )
    p.add_argument("--epochs", type=int, default=None, help="override cfg.training.epochs")
    p.add_argument("--patience", type=int, default=None, help="override cfg.training.early_stopping_patience")
    p.add_argument("--resume", action="store_true", help="reuse cached per-fold JSON results if present")
    p.add_argument("--save-checkpoints", action="store_true", help="save best checkpoint per fold")
    p.add_argument("--config", default="config/settings.yaml")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    bad = [m for m in models if m not in ALL_MODELS]
    if bad:
        sys.exit(f"Unknown model(s): {bad}. Choose from {ALL_MODELS}")

    proc_dir = Path(cfg["data"]["processed_path"])
    manifest_path = proc_dir / "manifest.csv"
    if not manifest_path.exists():
        sys.exit(f"Missing {manifest_path} — run scripts/preprocess.py first.")
    df = pd.read_csv(manifest_path)

    results_dir = Path(cfg["output"]["results_dir"])
    summaries = []
    for name in models:
        s = run_cv(
            df, name, cfg, proc_dir, results_dir,
            feature=args.feature,
            n_splits=args.folds,
            split_mode=args.split_mode,
            only_with_video=args.only_with_video,
            epochs=args.epochs,
            patience=args.patience,
            resume=args.resume,
            save_checkpoints=args.save_checkpoints,
        )
        summaries.append(s)

    if len(summaries) > 1:
        print("\n" + "=" * 92)
        print(f"  {'model':<16}{'acc (mean±std)':>17}{'macro-F1':>17}{'happy rec':>12}{'sad rec':>12}{'val-test':>11}")
        print("-" * 92)
        for s in summaries:
            print(
                f"  {s['model']:<16}"
                f"{s['accuracy_mean']:.3f} ± {s['accuracy_std']:.3f}    "
                f"{s['f1_macro_mean']:.3f} ± {s['f1_macro_std']:.3f}    "
                f"{s['per_class']['happy']['recall_mean']:>8.3f}    "
                f"{s['per_class']['sad']['recall_mean']:>8.3f}    "
                f"{s['val_test_gap_mean']:>+8.3f}"
            )
        print("=" * 92)
    return 0


if __name__ == "__main__":
    sys.exit(main())
