"""
Tests for src/datasets.py — parsing, splits, and Dataset class.
"""
import numpy as np
import pandas as pd
import pytest

from src.datasets import (
    EmotionDataset,
    IDX2LABEL,
    LABEL2IDX,
    UNIFIED,
    parse_cremad,
    parse_msp_improv,
    parse_ravdess,
    speaker_independent_split,
)


# ── Label mappings ────────────────────────────────────────


def test_label2idx_invertible():
    for label, idx in LABEL2IDX.items():
        assert IDX2LABEL[idx] == label


def test_idx2label_invertible():
    for idx, label in IDX2LABEL.items():
        assert LABEL2IDX[label] == idx


def test_unified_matches_label2idx():
    assert set(UNIFIED) == set(LABEL2IDX.keys())


def test_unified_has_six_classes():
    assert len(UNIFIED) == 6


# ── RAVDESS filename parsing ──────────────────────────────

RAVDESS_MAP = {
    "01": "neutral", "02": "neutral", "03": "happy", "04": "sad",
    "05": "angry",   "06": "fearful", "07": "disgust", "08": None,
}


def test_parse_ravdess_labels(tmp_path):
    actor = tmp_path / "Actor_01"
    actor.mkdir()
    (actor / "03-01-01-01-01-01-01.wav").touch()  # neutral
    (actor / "03-01-03-01-01-01-01.wav").touch()  # happy
    (actor / "03-01-05-01-01-01-01.wav").touch()  # angry

    df = parse_ravdess(str(tmp_path), RAVDESS_MAP)
    assert set(df["label"]) == {"neutral", "happy", "angry"}


def test_parse_ravdess_drops_null_labels(tmp_path):
    actor = tmp_path / "Actor_01"
    actor.mkdir()
    (actor / "03-01-08-01-01-01-01.wav").touch()  # surprised → None → dropped
    (actor / "03-01-03-01-01-01-01.wav").touch()  # happy → kept

    df = parse_ravdess(str(tmp_path), RAVDESS_MAP)
    assert len(df) == 1
    assert df.iloc[0]["label"] == "happy"


def test_parse_ravdess_speaker_prefix(tmp_path):
    actor = tmp_path / "Actor_05"
    actor.mkdir()
    (actor / "03-01-01-01-01-01-05.wav").touch()

    df = parse_ravdess(str(tmp_path), RAVDESS_MAP)
    assert df.iloc[0]["speaker"].startswith("ravdess_")


def test_parse_ravdess_dataset_column(tmp_path):
    actor = tmp_path / "Actor_01"
    actor.mkdir()
    (actor / "03-01-01-01-01-01-01.wav").touch()

    df = parse_ravdess(str(tmp_path), RAVDESS_MAP)
    assert (df["dataset"] == "ravdess").all()


# ── CREMA-D filename parsing ──────────────────────────────

CREMAD_MAP = {
    "ANG": "angry", "DIS": "disgust", "FEA": "fearful",
    "HAP": "happy", "NEU": "neutral", "SAD": "sad",
}


def test_parse_cremad_labels(tmp_path):
    audio_dir = tmp_path / "AudioWAV"
    audio_dir.mkdir()
    (audio_dir / "1001_DFA_ANG_XX.wav").touch()
    (audio_dir / "1001_DFA_HAP_XX.wav").touch()
    (audio_dir / "1001_DFA_NEU_XX.wav").touch()

    df = parse_cremad(str(tmp_path), CREMAD_MAP)
    assert set(df["label"]) == {"angry", "happy", "neutral"}


def test_parse_cremad_speaker_prefix(tmp_path):
    audio_dir = tmp_path / "AudioWAV"
    audio_dir.mkdir()
    (audio_dir / "1001_DFA_ANG_XX.wav").touch()

    df = parse_cremad(str(tmp_path), CREMAD_MAP)
    assert df.iloc[0]["speaker"].startswith("cremad_")


# ── MSP-IMPROV label parsing ──────────────────────────────

MSP_MAP = {"A": "angry", "H": "happy", "S": "sad", "N": "neutral"}


def test_parse_msp_improv_labels(tmp_path):
    audio_dir = tmp_path / "Audio"
    audio_dir.mkdir()
    (audio_dir / "MSP-ABC-01.wav").touch()
    (audio_dir / "MSP-ABC-02.wav").touch()

    (tmp_path / "Evalution.txt").write_text(
        "; comment\n"
        "MSP-ABC-01 ; S ; A\n"   # angry
        "MSP-ABC-02 ; S ; N\n"   # neutral
    )

    df = parse_msp_improv(str(tmp_path), MSP_MAP)
    assert set(df["label"]) == {"angry", "neutral"}


def test_parse_msp_improv_skips_missing_files(tmp_path):
    audio_dir = tmp_path / "Audio"
    audio_dir.mkdir()
    (audio_dir / "MSP-ABC-01.wav").touch()
    # MSP-ABC-99 does NOT exist on disk

    (tmp_path / "Evalution.txt").write_text(
        "MSP-ABC-01 ; S ; H\n"
        "MSP-ABC-99 ; S ; N\n"
    )

    df = parse_msp_improv(str(tmp_path), MSP_MAP)
    assert len(df) == 1


def test_parse_msp_improv_missing_label_file(tmp_path):
    df = parse_msp_improv(str(tmp_path), MSP_MAP)
    assert len(df) == 0


# ── Speaker-independent split ─────────────────────────────


def _make_df(n_speakers=20, samples_per=5):
    rows = []
    for spk in range(n_speakers):
        for _ in range(samples_per):
            rows.append({
                "audio_path": f"/fake/{spk}.wav",
                "video_path": None,
                "label": "neutral",
                "speaker": f"spk_{spk:02d}",
                "dataset": "test",
            })
    return pd.DataFrame(rows)


def test_split_speakers_are_disjoint():
    df = _make_df(20, 5)
    train, val, test = speaker_independent_split(df, 0.15, 0.15, seed=42)
    assert set(train["speaker"]).isdisjoint(set(val["speaker"]))
    assert set(train["speaker"]).isdisjoint(set(test["speaker"]))
    assert set(val["speaker"]).isdisjoint(set(test["speaker"]))


def test_split_covers_all_samples():
    df = _make_df(20, 5)
    train, val, test = speaker_independent_split(df, 0.15, 0.15, seed=42)
    assert len(train) + len(val) + len(test) == len(df)


def test_split_is_reproducible():
    df = _make_df(20, 5)
    t1, v1, s1 = speaker_independent_split(df, 0.15, 0.15, seed=7)
    t2, v2, s2 = speaker_independent_split(df, 0.15, 0.15, seed=7)
    assert list(t1["speaker"]) == list(t2["speaker"])


def test_split_respects_fractions():
    df = _make_df(40, 5)
    _, val, test = speaker_independent_split(df, 0.15, 0.15, seed=42)
    # Test and val together ≤ 35% of samples (they might be slightly off due to integer rounding)
    assert (len(val) + len(test)) / len(df) < 0.40


# ── EmotionDataset ────────────────────────────────────────


def _setup_ds(tmp_path, labels, modality="audio", feature="mel"):
    mel_dir = tmp_path / "mel"
    mel_dir.mkdir(exist_ok=True)
    rows = []
    for i, label in enumerate(labels):
        stem = f"sample_{i:03d}"
        np.save(mel_dir / f"{stem}.npy", np.zeros((128, 130), dtype=np.float32))
        rows.append({
            "audio_path": f"/fake/{stem}.wav",
            "video_path": None,
            "label": label,
            "speaker": f"spk_{i:02d}",
            "dataset": "test",
        })
    return EmotionDataset(pd.DataFrame(rows), str(tmp_path), modality, feature)


def test_dataset_len():
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as d:
        ds = _setup_ds(pathlib.Path(d), ["neutral", "happy", "angry"])
        assert len(ds) == 3


def test_dataset_audio_mel_shape(tmp_path):
    ds = _setup_ds(tmp_path, ["happy"])
    x, y = ds[0]
    assert x.shape == (1, 128, 130)   # (channel, n_mels, time)


def test_dataset_label_correct(tmp_path):
    ds = _setup_ds(tmp_path, ["angry"])
    _, y = ds[0]
    assert y.item() == LABEL2IDX["angry"]


def test_dataset_all_labels_reachable(tmp_path):
    ds = _setup_ds(tmp_path, UNIFIED)
    returned = {ds[i][1].item() for i in range(len(ds))}
    assert returned == set(range(len(UNIFIED)))


def test_dataset_missing_video_returns_zeros(tmp_path):
    mel_dir = tmp_path / "mel"
    mel_dir.mkdir()
    np.save(mel_dir / "s.npy", np.zeros((128, 130), dtype=np.float32))
    df = pd.DataFrame([{
        "audio_path": "/fake/s.wav", "video_path": None,
        "label": "neutral", "speaker": "spk_01", "dataset": "test",
    }])
    ds = EmotionDataset(df, str(tmp_path), modality="multimodal", feature="mel")
    _, visual, _ = ds[0]
    assert visual.shape == (75, 1404)
    assert visual.sum().item() == 0.0
