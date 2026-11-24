"""
Training script.

Usage:
    python scripts/train.py --model audio_cnn_lstm
    python scripts/train.py --model attention --feature mel

Model choices: audio_cnn | audio_cnn_lstm | visual_lstm |
               feature_level | decision_level | attention
"""
import sys
from contextlib import nullcontext
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import yaml
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.tensorboard import SummaryWriter
from sklearn.utils.class_weight import compute_class_weight
from tqdm import tqdm

from src.datasets import (
    EmotionDataset, LABEL2IDX, UNIFIED,
    speaker_independent_split,
)
from src.models.builder import build_model, is_multimodal


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="audio_cnn_lstm",
                   choices=["audio_cnn", "audio_cnn_lstm", "visual_lstm",
                            "feature_level", "decision_level", "attention"])
    p.add_argument("--feature", default="mel", choices=["mel", "mfcc"])
    p.add_argument("--config", default="config/settings.yaml")
    return p.parse_args()


def run_epoch(model, loader, criterion, optimizer, scaler, device, train, multimodal):
    model.train(train)
    total_loss = correct = total = 0

    for batch in tqdm(loader, desc="train" if train else "val  ", leave=False):
        if multimodal:
            xa, xv, y = batch[0].to(device), batch[1].to(device), batch[2].to(device)
        else:
            xa, y = batch[0].to(device), batch[1].to(device)
            xv = None

        amp_ctx = torch.autocast("cuda") if scaler else nullcontext()
        with torch.set_grad_enabled(train), amp_ctx:
            logits = model(xa, xv) if multimodal else model(xa)
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

    return total_loss / total, correct / total


def main():
    args = parse_args()
    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    tc = cfg["training"]
    torch.manual_seed(tc["seed"])
    np.random.seed(tc["seed"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device} | Model: {args.model} | Feature: {args.feature}")

    proc = Path(cfg["data"]["processed_path"])
    df = pd.read_csv(proc / "manifest.csv")

    multi = is_multimodal(args.model)
    modality = "multimodal" if multi else ("visual" if args.model == "visual_lstm" else "audio")

    if modality == "visual":
        has_lm = df["video_path"].apply(
            lambda vp: isinstance(vp, str) and (proc / "landmarks" / f"{Path(vp).stem}.npy").exists()
        )
        dropped = int((~has_lm).sum())
        if dropped:
            print(f"Filtered out {dropped} samples without extracted landmarks for visual_lstm")
        df = df[has_lm].reset_index(drop=True)
        if df.empty:
            raise RuntimeError("No samples with extracted landmarks available for visual_lstm.")

    train_df, val_df, test_df = speaker_independent_split(
        df, tc["val_split"], tc["test_split"], tc["seed"]
    )
    print(f"Split: {len(train_df)} train / {len(val_df)} val / {len(test_df)} test (speaker-independent)")
    # Save test split up front so an interrupted run never leaves a stale split.
    test_df.to_csv(proc / "test_split.csv", index=False)

    def make_loader(split_df, shuffle):
        ds = EmotionDataset(split_df, str(proc), modality, args.feature,
                            max_frames=cfg["visual"]["max_frames"])
        return DataLoader(
            ds, batch_size=tc["batch_size"], shuffle=shuffle,
            num_workers=tc["num_workers"], pin_memory=tc["pin_memory"],
        )

    train_loader = make_loader(train_df, True)
    val_loader   = make_loader(val_df,   False)

    num_classes = len(UNIFIED)
    model = build_model(args.model, cfg, num_classes, args.feature).to(device)
    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Parameters: {n_params:,}")

    # Class-weighted loss for label imbalance across datasets; tolerate corpora
    # (e.g. MSP-IMPROV alone) that cover only a subset of the 6 unified classes.
    labels = train_df["label"].map(LABEL2IDX).values
    present = np.unique(labels)
    present_weights = compute_class_weight("balanced", classes=present, y=labels)
    weights = np.ones(num_classes, dtype=np.float32)
    weights[present] = present_weights
    criterion = nn.CrossEntropyLoss(
        weight=torch.tensor(weights, dtype=torch.float32).to(device)
    )

    optimizer = AdamW(model.parameters(), lr=tc["learning_rate"], weight_decay=tc["weight_decay"])
    scheduler = CosineAnnealingLR(optimizer, T_max=tc["epochs"])
    scaler    = torch.amp.GradScaler("cuda") if tc["amp"] and device.type == "cuda" else None

    tag = args.model if args.feature == "mel" else f"{args.model}_{args.feature}"
    out_dir = Path(cfg["output"]["model_dir"])
    out_dir.mkdir(exist_ok=True)
    ckpt_path = out_dir / f"{tag}_best.pt"
    writer = SummaryWriter(log_dir=f"{cfg['output']['log_dir']}/{tag}")

    best_val_loss = float("inf")
    patience_ctr  = 0

    for epoch in range(1, tc["epochs"] + 1):
        tr_loss, tr_acc = run_epoch(
            model, train_loader, criterion, optimizer, scaler, device, True, multi
        )
        vl_loss, vl_acc = run_epoch(
            model, val_loader, criterion, None, scaler, device, False, multi
        )
        scheduler.step()

        writer.add_scalars("loss", {"train": tr_loss, "val": vl_loss}, epoch)
        writer.add_scalars("acc",  {"train": tr_acc,  "val": vl_acc},  epoch)
        print(
            f"Epoch {epoch:3d} | "
            f"train loss {tr_loss:.4f} acc {tr_acc:.3f} | "
            f"val loss {vl_loss:.4f} acc {vl_acc:.3f}"
        )

        if vl_loss < best_val_loss:
            best_val_loss = vl_loss
            patience_ctr  = 0
            torch.save({
                "epoch": epoch,
                "model": model.state_dict(),
                "val_loss": vl_loss,
                "val_acc":  vl_acc,
                "model_name": args.model,
                "feature": args.feature,
                "cfg": cfg,
            }, ckpt_path)
            print(f"  [saved] val_acc={vl_acc:.3f}")
        else:
            patience_ctr += 1
            if patience_ctr >= tc["early_stopping_patience"]:
                print(f"Early stopping at epoch {epoch}")
                break

    writer.close()
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    print(f"\nBest val accuracy: {ckpt['val_acc']:.4f} | Checkpoint: {ckpt_path}")


if __name__ == "__main__":
    main()
