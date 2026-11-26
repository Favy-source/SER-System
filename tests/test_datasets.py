"""
Tests for src/datasets.py — parsing, splits, and Dataset class.
"""
import numpy as np
from pathlib import Path
import pandas as pd
import pytest

from src.constants import LANDMARK_DIM
from src.datasets import (
    EmotionDataset,
    IDX2LABEL,
    LABEL2IDX,
    UNIFIED,
    msp_speaker,
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


# ── MSP-IMPROV speaker extraction ─────────────────────────
#
# The previous implementation used fname[:6], which is the literal string
# "MSP-IM" for every file in the real corpus — collapsing all ~8400 samples
# into one split unit. These tests use real-format stems, which the earlier
# synthetic "MSP-ABC-01" fixtures did not.

REAL_STEMS = {
    "MSP-IMPROV-S01A-M01-P-FM01": "M01",
    "MSP-IMPROV-S01A-F01-S-FF01": "F01",
    "MSP-IMPROV-S04B-M04-R-FM12": "M04",
    "MSP-IMPROV-S06A-F06-T-FF03": "F06",
}


@pytest.mark.parametrize("stem,expected", list(REAL_STEMS.items()))
def test_msp_speaker_extracts_actor_field(stem, expected):
    assert msp_speaker(stem) == expected


def test_msp_speaker_distinguishes_actors():
    """The core regression: distinct actors must yield distinct ids."""
    assert len({msp_speaker(s) for s in REAL_STEMS}) == len(REAL_STEMS)


def test_msp_speaker_ignores_session_and_take_fields():
    """S01A is a session, FM01/FF01 are takes — neither is the actor."""
    spk = msp_speaker("MSP-IMPROV-S01A-M01-P-FM01")
    assert spk not in {"S01A", "FM01", "P", "MSP", "IMPROV"}
    assert spk == "M01"


def test_msp_speaker_same_actor_across_sessions_is_one_id():
    """Over-merging is safe; splitting one actor across units would leak."""
    a = msp_speaker("MSP-IMPROV-S01A-M01-P-FM01")
    b = msp_speaker("MSP-IMPROV-S01B-M01-R-FM07")
    assert a == b == "M01"


def test_msp_speaker_unrecognised_returns_none():
    assert msp_speaker("some_other_naming_01") is None
    assert msp_speaker("") is None


def test_parse_msp_improv_speakers_are_distinct(tmp_path):
    """Through the parser, on a real-format synthetic corpus."""
    audio_dir = tmp_path / "Audio"
    audio_dir.mkdir()
    for stem in REAL_STEMS:
        (audio_dir / f"{stem}.wav").touch()
    (tmp_path / "Evalution.txt").write_text(
        "".join(f"{stem} ; S ; A\n" for stem in REAL_STEMS)
    )

    df = parse_msp_improv(str(tmp_path), MSP_MAP)
    assert len(df) == len(REAL_STEMS)
    assert set(df["speaker"]) == {f"msp_{a}" for a in REAL_STEMS.values()}
    assert df["speaker"].nunique() == len(REAL_STEMS)


def test_parse_msp_improv_unrecognised_stem_buckets_together(tmp_path):
    """Unparseable stems share one id rather than becoming per-file speakers."""
    audio_dir = tmp_path / "Audio"
    audio_dir.mkdir()
    for stem in ("odd_name_a", "odd_name_b"):
        (audio_dir / f"{stem}.wav").touch()
    (tmp_path / "Evalution.txt").write_text(
        "odd_name_a ; S ; A\nodd_name_b ; S ; H\n"
    )

    df = parse_msp_improv(str(tmp_path), MSP_MAP)
    assert set(df["speaker"]) == {"msp_unknown"}


def test_msp_speakers_survive_the_split(tmp_path):
    """End of the chain: distinct actors must reach distinct split units.

    With the old fname[:6] behaviour every MSP sample landed in one unit, so
    the corpus went entirely to train, or entirely to test, by seed.
    """
    audio_dir = tmp_path / "Audio"
    audio_dir.mkdir()
    stems = [f"MSP-IMPROV-S0{i//2+1}A-{'MF'[i%2]}0{i//2+1}-P-FM0{i}"
             for i in range(12)]
    for stem in stems:
        (audio_dir / f"{stem}.wav").touch()
    (tmp_path / "Evalution.txt").write_text(
        "".join(f"{s} ; S ; {'AHSN'[i % 4]}\n" for i, s in enumerate(stems))
    )

    df = parse_msp_improv(str(tmp_path), MSP_MAP)
    assert df["speaker"].nunique() > 1, "all MSP samples collapsed to one speaker"

    train, val, test = speaker_independent_split(df, 0.15, 0.15, seed=42)
    assert len(train) and len(val) and len(test), (
        "a single split received every MSP sample"
    )


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
    assert visual.shape == (75, LANDMARK_DIM)
    assert visual.sum().item() == 0.0


def test_split_handles_pandas_extension_string_dtype():
    """The split must be safe with a pandas-backed string column.

    Every other split test builds its DataFrame from Python str objects, so
    .unique() returns an ndarray and numpy shuffles it happily. Real corpora go
    through pd.DataFrame(records), which on modern pandas yields a StringArray —
    and numpy warns that shuffling one "may contain duplicates". A duplicate
    would put one speaker in two splits and void the speaker-independence
    guarantee silently.
    """
    df = pd.DataFrame({
        "audio_path": [f"/f/{i}.wav" for i in range(60)],
        "video_path": [None] * 60,
        "label": [UNIFIED[i % 6] for i in range(60)],
        "speaker": pd.array([f"spk_{i % 20:02d}" for i in range(60)], dtype="string"),
        "dataset": ["t"] * 60,
    })
    assert str(df["speaker"].dtype) in ("string", "str"), "fixture must use the extension dtype"

    train, val, test = speaker_independent_split(df, 0.15, 0.15, seed=7)

    s_tr, s_va, s_te = (set(x["speaker"]) for x in (train, val, test))
    assert len(s_tr | s_va | s_te) == 20, "speakers were lost or duplicated"
    assert not (s_tr & s_va) and not (s_va & s_te) and not (s_tr & s_te)
    assert len(train) + len(val) + len(test) == len(df)


def test_split_is_reproducible_with_extension_dtype():
    df = pd.DataFrame({
        "audio_path": [f"/f/{i}.wav" for i in range(40)],
        "video_path": [None] * 40,
        "label": [UNIFIED[i % 6] for i in range(40)],
        "speaker": pd.array([f"s{i % 10}" for i in range(40)], dtype="string"),
        "dataset": ["t"] * 40,
    })
    a = speaker_independent_split(df, 0.15, 0.15, seed=3)
    b = speaker_independent_split(df, 0.15, 0.15, seed=3)
    for x, y in zip(a, b):
        assert set(x["speaker"]) == set(y["speaker"])


# ── RAVDESS video pairing ─────────────────────────────────
#
# Field 1 of a RAVDESS filename is the MODALITY: 01 = audio-visual,
# 02 = video-only, 03 = audio-only. So audio is `03-...wav` and its video
# counterpart is `01-...mp4` — a DIFFERENT stem. The parser previously used
# wav.with_suffix(".mp4"), which looks for `03-...mp4`; no RAVDESS release
# contains such a file, so the visual stream was never found even with the video
# archives fully downloaded, and every sample silently got a zero-filled face.


def test_ravdess_video_for_maps_audio_to_av_modality(tmp_path):
    from src.datasets import ravdess_video_for
    wav = tmp_path / "03-01-05-01-02-01-12.wav"
    wav.touch()
    vid = tmp_path / "01-01-05-01-02-01-12.mp4"      # 01 = audio-visual
    vid.touch()
    assert ravdess_video_for(wav) == vid


def test_ravdess_video_for_falls_back_to_video_only_modality(tmp_path):
    from src.datasets import ravdess_video_for
    wav = tmp_path / "03-01-03-01-01-01-07.wav"
    wav.touch()
    vid = tmp_path / "02-01-03-01-01-01-07.mp4"      # 02 = video-only
    vid.touch()
    assert ravdess_video_for(wav) == vid


def test_ravdess_video_for_prefers_audio_visual_over_video_only(tmp_path):
    from src.datasets import ravdess_video_for
    wav = tmp_path / "03-01-04-01-01-01-02.wav"
    wav.touch()
    (tmp_path / "01-01-04-01-01-01-02.mp4").touch()
    (tmp_path / "02-01-04-01-01-01-02.mp4").touch()
    assert ravdess_video_for(wav).name.startswith("01-")


def test_ravdess_video_for_none_when_absent(tmp_path):
    from src.datasets import ravdess_video_for
    wav = tmp_path / "03-01-05-01-02-01-12.wav"
    wav.touch()
    assert ravdess_video_for(wav) is None


def test_ravdess_video_for_does_not_use_the_wav_stem(tmp_path):
    """The old bug: a same-stem .mp4 is NOT what RAVDESS ships."""
    from src.datasets import ravdess_video_for
    wav = tmp_path / "03-01-05-01-02-01-12.wav"
    wav.touch()
    (tmp_path / "03-01-05-01-02-01-12.mp4").touch()   # this never exists in RAVDESS
    assert ravdess_video_for(wav) is None, "must not match the audio-only modality"


def test_parse_ravdess_finds_video_with_correct_modality(tmp_path):
    actor = tmp_path / "Actor_12"
    actor.mkdir()
    (actor / "03-01-05-01-02-01-12.wav").touch()
    (actor / "01-01-05-01-02-01-12.mp4").touch()

    df = parse_ravdess(str(tmp_path), RAVDESS_MAP)
    assert len(df) == 1
    assert df.iloc[0]["video_path"] is not None, "video was not paired to the audio"
    assert Path(df.iloc[0]["video_path"]).name == "01-01-05-01-02-01-12.mp4"


# ── Speaker-independent k-fold CV ─────────────────────────


def test_kfolds_every_fold_is_strictly_speaker_disjoint():
    from src.datasets import speaker_independent_kfolds
    df = _make_df(24, 4)
    folds = list(speaker_independent_kfolds(df, n_splits=5, seed=42))
    assert len(folds) == 5

    seen_test_speakers = []
    for train, val, test in folds:
        s_tr, s_va, s_te = set(train["speaker"]), set(val["speaker"]), set(test["speaker"])
        assert s_tr and s_va and s_te
        assert s_tr.isdisjoint(s_va)
        assert s_tr.isdisjoint(s_te)
        assert s_va.isdisjoint(s_te)
        assert len(train) + len(val) + len(test) == len(df)
        seen_test_speakers.extend(s_te)

    # Every speaker is evaluated in the held-out test split exactly once.
    assert len(seen_test_speakers) == 24
    assert set(seen_test_speakers) == set(df["speaker"])


def test_kfolds_is_reproducible_and_validates_inputs():
    from src.datasets import speaker_independent_kfolds
    df = _make_df(15, 3)
    a = [set(te["speaker"]) for _, _, te in speaker_independent_kfolds(df, n_splits=5, seed=9)]
    b = [set(te["speaker"]) for _, _, te in speaker_independent_kfolds(df, n_splits=5, seed=9)]
    assert a == b

    with pytest.raises(ValueError, match="n_splits"):
        list(speaker_independent_kfolds(df, n_splits=2))
    with pytest.raises(ValueError, match="unique speakers"):
        list(speaker_independent_kfolds(_make_df(3, 4), n_splits=5))


def test_random_kfolds_covers_every_sample_once():
    from src.datasets import random_kfolds
    df = _make_df(10, 6)
    folds = list(random_kfolds(df, n_splits=5, seed=42))
    assert len(folds) == 5
    assert sum(len(te) for _, _, te in folds) == len(df)
