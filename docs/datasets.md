# Datasets

How the three source corpora are acquired, parsed, mapped onto a shared taxonomy, and split.

- [The three corpora](#the-three-corpora)
- [Directory layout](#directory-layout)
- [Filename grammars](#filename-grammars)
- [The unified manifest schema](#the-unified-manifest-schema)
- [Label mapping](#label-mapping)
- [Speaker-independent splitting](#speaker-independent-splitting)
- [`EmotionDataset`](#emotiondataset)
- [Adding a corpus](#adding-a-corpus)
- [Known issues](#known-issues)

---

## The three corpora

| Corpus | Modality | Speakers | Clips | Emotions | Licence |
|---|---|---|---|---|---|
| **RAVDESS** | audio + video | 24 professional actors (12 M / 12 F) | ~1,440 speech | 8 (neutral, calm, happy, sad, angry, fearful, disgust, surprised) | CC BY-NC-SA 4.0 |
| **CREMA-D** | audio + video | 91 actors, ethnically diverse | ~7,442 | 6 (anger, disgust, fear, happy, neutral, sad) | Open Database Licence, academic use |
| **MSP-IMPROV** | audio | 12 actors (6 dyads) | ~8,400 | 4 primary (angry, happy, sad, neutral) | Academic licence, request required |

Acquisition:

- **RAVDESS** — Zenodo record [1188976](https://zenodo.org/record/1188976). `Audio_Speech_Actors_01-24.zip`
  for audio; the video archives are separate and much larger. Freely downloadable.
- **CREMA-D** — [github.com/CheyneyComputerScience/CREMA-D](https://github.com/CheyneyComputerScience/CREMA-D).
  Audio via the repository; video requires the separate download described there.
- **MSP-IMPROV** — request access from the [UT Dallas MSP lab](https://ecs.utdallas.edu/research/researchlabs/msp-lab/).
  Requires a signed academic licence agreement.

**None of these are redistributed in this repository.** `datasets/RAVDESS/`, `datasets/CREMA-D/`, and
`datasets/MSP-IMPROV/` are gitignored. Comply with each licence; cite the corpora as their authors
specify if you publish.

Why these three: RAVDESS gives clean, balanced, audio-visual data across all six target classes;
CREMA-D adds an order of magnitude more speakers and much greater demographic diversity, which is what
makes speaker-independent evaluation meaningful; MSP-IMPROV adds improvised rather than scripted
speech, which is closer to spontaneous affect even though it is still acted. Together they cover the
axes that matter for the generalisation question — speaker count, demographic range, and elicitation
method — while sharing enough label vocabulary to be merged at all.

All three remain **acted studio recordings**. None is clinical, spontaneous, or Nigerian. That is the
central external-validity limitation of any result this repository produces.

---

## Directory layout

The parsers expect exactly this structure, relative to the paths in
[`config/settings.yaml`](../config/settings.yaml):

```
datasets/
├── RAVDESS/
│   ├── Actor_01/
│   │   ├── 03-01-01-01-01-01-01.wav
│   │   ├── 03-01-01-01-01-01-01.mp4      ← optional; enables the visual stream
│   │   └── …
│   ├── Actor_02/
│   └── … Actor_24/
│
├── CREMA-D/
│   ├── AudioWAV/
│   │   ├── 1001_DFA_ANG_XX.wav
│   │   └── …
│   └── VideoFlash/                        ← optional
│       ├── 1001_DFA_ANG_XX.flv
│       └── …
│
└── MSP-IMPROV/
    ├── Audio/
    │   ├── MSP-IMPROV-S01A-M01-P-FM01.wav
    │   └── …
    └── Evalution.txt                      ← original filename typo, preserved
```

Structural notes:

- **RAVDESS** is parsed with `rglob("*.wav")`, so the `Actor_NN/` nesting is not required — any
  arrangement works as long as filenames follow the grammar.
- **CREMA-D** requires the literal subdirectory names `AudioWAV/` and `VideoFlash/`; the parser globs
  `AudioWAV/*.wav` non-recursively.
- **MSP-IMPROV** requires `Evalution.txt` at the corpus root — note the missing `a`, which is how the
  file ships. `parse_msp_improv` returns an empty DataFrame if it is absent rather than raising.
- Video is optional everywhere. A missing companion video sets `video_path` to `None` and the visual
  tensor is zero-filled at load time.

---

## Filename grammars

### RAVDESS

Seven hyphen-separated numeric fields:

```
03-01-05-01-02-01-12.wav
│  │  │  │  │  │  └── actor        01–24  (odd = male, even = female)
│  │  │  │  │  └───── repetition   01–02
│  │  │  │  └──────── statement    01–02
│  │  │  └─────────── intensity    01 normal, 02 strong
│  │  └────────────── emotion      01–08          ← parsed
│  └───────────────── vocal ch.    01 speech, 02 song
└──────────────────── modality     01 A/V, 02 video-only, 03 audio-only
```

[`parse_ravdess`](../src/datasets.py#L18) reads `parts[2]` for emotion and `parts[6]` for speaker,
requires at least 7 fields, and probes for a sibling `.mp4`:

```python
parts = f.stem.split("-")
if len(parts) < 7: continue
label = emotion_map.get(parts[2])
if label is None: continue          # drops "08" (surprised) and unmapped codes
video = f.with_suffix(".mp4")
speaker = f"ravdess_{parts[6]}"
```

Fields 1 (vocal channel) and 5 (intensity) are **not** filtered. If you download the song archive as
well as speech, sung samples will be silently mixed into a speech model. Filter on `parts[1] == "01"`
if that matters. Intensity is likewise ignored — normal and strong renditions are pooled.

### CREMA-D

Four underscore-separated fields:

```
1001_DFA_ANG_XX.wav
│    │   │   └── intensity   LO, MD, HI, XX (unspecified)
│    │   └────── emotion     ANG DIS FEA HAP NEU SAD   ← parsed
│    └────────── sentence    12 fixed sentence codes
└─────────────── actor       1001–1091                 ← parsed
```

[`parse_cremad`](../src/datasets.py#L38) reads `parts[2]` for emotion, `parts[0]` for speaker, and
looks for `VideoFlash/<stem>.flv`:

```python
parts = f.stem.split("_")
if len(parts) < 3: continue
label = emotion_map.get(parts[2])
speaker = f"cremad_{parts[0]}"
```

Intensity is ignored, so LO/MD/HI variants of the same sentence are pooled.

### MSP-IMPROV

Labels come from a semicolon-delimited text file rather than the filename:

```
; comment lines begin with a semicolon
MSP-IMPROV-S01A-M01-P-FM01 ; S ; A ; 3.5 ; 2.1 ; …
└── field 0: filename stem      │     └── field 2: categorical emotion  ← parsed
                                └──────── field 1: session/type
```

[`parse_msp_improv`](../src/datasets.py#L60):

```python
parts = [p.strip() for p in line.split(";")]
if len(parts) < 3: continue
fname, code = parts[0], parts[2]
label = emotion_map.get(code)
audio = Path(root) / "Audio" / f"{fname}.wav"
if not audio.exists(): continue     # skip labels with no audio on disk
speaker = f"msp_{fname[:6]}"        # ← see known issues
```

Blank lines and `;`-prefixed comments are skipped. Labelled entries whose audio file is missing are
skipped, so a partial download degrades gracefully. `video_path` is always `None` — the audio-only
release is assumed.

> **Field ordering varies between MSP-IMPROV releases.** The docstring says as much: *"Adjust field
> index if your copy uses a different column ordering."* Inspect the first few lines of your
> `Evalution.txt` before trusting `parts[2]`.

---

## The unified manifest schema

All three parsers emit the same five columns, which is the entire reason structurally unrelated corpora
can be concatenated:

| Column | Type | Contents |
|---|---|---|
| `audio_path` | `str` | Absolute or relative path to the `.wav` |
| `video_path` | `str \| None` | Companion video, or `None` |
| `label` | `str` | One of the six unified emotions |
| `speaker` | `str` | Corpus-prefixed speaker id |
| `dataset` | `str` | `"ravdess"` / `"cremad"` / `"msp_improv"` |

[`load_datasets`](../src/datasets.py#L96) concatenates whatever it finds:

```
Parsing datasets...
  ravdess: 1152 samples
  cremad: 7442 samples
  msp: not found at datasets/MSP-IMPROV — skipping
```

and raises only when all three are absent. Partial installations are fully supported.

**Speaker ids are namespaced deliberately.** RAVDESS actor `01` and a hypothetical CREMA-D actor `01`
are different people; without the prefix they would be merged into one split unit, quietly leaking one
person's data across the train/test boundary. `test_parse_ravdess_speaker_prefix` and
`test_parse_cremad_speaker_prefix` assert the prefixes are applied.

The `dataset` column exists for per-corpus error analysis — asking whether cross-corpus training
actually helps, or whether accuracy is just averaging over corpora with different difficulty. Nothing
in the current pipeline uses it; it is there for the analysis notebooks.

`preprocess.py` writes the concatenated manifest to `datasets/processed/manifest.csv`, and `train.py`
reads only that. Parsing happens once.

---

## Label mapping

Target taxonomy — six classes, index order fixed by [`UNIFIED`](../src/datasets.py#L9):

| Index | Label | RAVDESS | CREMA-D | MSP-IMPROV |
|---|---|---|---|---|
| 0 | `neutral` | `01`, `02` (calm) | `NEU` | `N` |
| 1 | `happy` | `03` | `HAP` | `H` |
| 2 | `sad` | `04` | `SAD` | `S` |
| 3 | `angry` | `05` | `ANG` | `A` |
| 4 | `fearful` | `06` | `FEA` | — |
| 5 | `disgust` | `07` | `DIS` | — |
| — | *dropped* | `08` (surprised) | — | all other codes |

Six classes is not an aesthetic choice — it is the largest set all three corpora agree on, and
therefore the ceiling on what cross-corpus training can address.

**Consequences worth being explicit about:**

- `neutral` absorbs RAVDESS `calm`, so it is over-represented and internally more varied than the
  other classes. Expect it to be the most confusable class in any confusion matrix.
- `fearful` and `disgust` come only from RAVDESS and CREMA-D. Adding MSP-IMPROV dilutes them relative
  to the other four — visible as lower macro F1 even when accuracy rises.
- Dropped rather than relabelled: RAVDESS `surprised` samples are discarded. Folding surprise into
  `happy` would inject label noise into a class the model must learn precisely.

The mapping lives in [`config/settings.yaml`](../config/settings.yaml#L27), not in code, so a different
taxonomy is a config change plus a retrain — but see
[configuration.md](configuration.md#two-rules-before-you-edit-anything) on why reordering `UNIFIED`
invalidates every existing checkpoint.

---

## Speaker-independent splitting

[`speaker_independent_split`](../src/datasets.py#L124) partitions **speakers**, not samples:

```python
rng = np.random.default_rng(seed)
speakers = df["speaker"].unique()
rng.shuffle(speakers)
n_test = max(1, int(n * test_frac))
n_val  = max(1, int(n * val_frac))
test_spk  = set(speakers[:n_test])
val_spk   = set(speakers[n_test : n_test + n_val])
train_spk = set(speakers[n_test + n_val :])
```

### Why this is non-negotiable

A random *sample*-level split puts different utterances from the same actor in both train and test.
The model then has a shortcut: identify the speaker, recall which emotions that speaker produced. SER
results in the literature are routinely inflated by exactly this, and cross-corpus comparisons become
meaningless. A speaker-disjoint split forces generalisation to unseen voices — which is the only
version of the question that matters for a system meant to meet new patients.

The guarantee is asserted, not assumed:

```python
def test_split_speakers_are_disjoint():
    # train ∩ val == val ∩ test == train ∩ test == ∅
```

### Properties

| Property | Behaviour |
|---|---|
| Determinism | Same `seed` → same split. `test_split_is_reproducible` asserts it |
| Coverage | Every sample lands in exactly one split. `test_split_covers_all_samples` asserts it |
| Exact sizes | **Not** guaranteed — speakers contribute unequal sample counts, so 0.15 of speakers is only approximately 0.15 of samples |
| Minimum | `max(1, …)` guarantees at least one speaker in val and test even for tiny corpora |
| Stratification | **None.** Class balance across splits is not controlled |

That last row is a real limitation. With 24 RAVDESS speakers, a 15% test fraction is 3 speakers, and 3
actors may not cover all six classes evenly — or at all. Combining corpora mitigates it by raising the
speaker count (91 CREMA-D actors → ~13 test speakers). Stratified speaker sampling that balances class
distribution across splits would be a worthwhile improvement.

`train.py` writes the test split to `datasets/processed/test_split.csv` so `evaluate.py` uses exactly
the same speakers even if the seed or fractions change later — the split is pinned at training time
rather than recomputed.

---

## `EmotionDataset`

[`src/datasets.py`](../src/datasets.py#L150) reads **pre-extracted `.npy` files**, never audio. Feature
extraction happens once in `preprocess.py`; epochs are then cheap.

```python
EmotionDataset(df, processed_dir, modality="audio", feature="mel")
```

| `modality` | Returns |
|---|---|
| `"audio"` | `(audio_tensor, label)` |
| `"visual"` | `(visual_tensor, label)` |
| `"multimodal"` | `(audio_tensor, visual_tensor, label)` |

Loading:

```python
def _load_audio(self, audio_path):
    p = self.proc / self.feature / (Path(audio_path).stem + ".npy")
    t = torch.from_numpy(np.load(p)).float()
    if self.feature == "mel":
        t = t.unsqueeze(0)          # (1, n_mels, T)
    return t

def _load_visual(self, video_path):
    if video_path:
        p = self.proc / "landmarks" / (Path(video_path).stem + ".npy")
        if p.exists():
            return torch.from_numpy(np.load(p)).float()
    return torch.zeros(75, 1404)    # zero-fill when video unavailable
```

Two things to notice:

- **The channel dimension is added only for `"mel"`.** This is
  [known issue #1](../README.md#1---feature-mfcc-crashes-the-cnn-models--confirmed) — MFCC tensors
  arrive at `Conv2d` as 3-D and it raises.
- **Zero-fill is what makes audio-only corpora usable in multimodal training.** MSP-IMPROV has no
  video at all; without the fallback it could not participate. The cost is that a fusion model trained
  on a mixed manifest sees many all-zero visual inputs and may learn to ignore the visual branch
  entirely. Worth checking `decision_level`'s learned weights after training — if `w₁ ≈ 0`, that is
  what happened.

Lookups are keyed on `Path(...).stem`, so two files with the same stem in different directories would
collide. None of the three supported corpora have that problem.

---

## Adding a corpus

**1. Write the parser** in [`src/datasets.py`](../src/datasets.py):

```python
def parse_mycorpus(root: str, emotion_map: dict) -> pd.DataFrame:
    records = []
    for f in sorted(Path(root).rglob("*.wav")):
        code = f.stem.split("_")[1]        # your grammar here
        label = emotion_map.get(code)
        if label is None:                  # unmapped or explicitly null
            continue
        records.append({
            "audio_path": str(f),
            "video_path": None,
            "label":      label,
            "speaker":    f"mycorpus_{f.stem.split('_')[0]}",   # namespace it
            "dataset":    "mycorpus",
        })
    return pd.DataFrame(records)
```

**2. Register it** in [`load_datasets`](../src/datasets.py#L99):

```python
"mycorpus": (root / cfg["data"]["mycorpus_path"], parse_mycorpus, cfg["emotions"]["mycorpus_map"]),
```

**3. Add config keys** — `data.mycorpus_path` and `emotions.mycorpus_map`, mapping anything outside the
unified six to `null`.

**4. Add tests** following the `tmp_path` pattern in `test_datasets.py`:

```python
def test_parse_mycorpus_labels(tmp_path):
    (tmp_path / "spk1_joy_01.wav").touch()
    df = parse_mycorpus(str(tmp_path), {"joy": "happy"})
    assert df.iloc[0]["label"] == "happy"
    assert df.iloc[0]["speaker"].startswith("mycorpus_")
```

The tests only `touch()` empty files — parsers read filenames, never audio content — so they stay fast
and need no fixtures.

**Checklist:** namespace the speaker id; return `None` for `video_path` when there is no video; skip
unmapped labels rather than defaulting them; use `sorted()` for deterministic ordering.

---

## Known issues

### MSP-IMPROV speaker ids collapse to one speaker — confirmed by inspection

```python
speaker = f"msp_{fname[:6]}"
```

Real MSP-IMPROV filenames all begin `MSP-IMPROV-…`, so `fname[:6]` is `"MSP-IM"` for **every file in
the corpus**. All MSP-IMPROV samples become a single split unit and go entirely to train, entirely to
val, or entirely to test depending on the seed. Speaker independence holds trivially, but the split is
badly unbalanced and MSP-IMPROV may be absent from training altogether.

The fix is to parse the real speaker field. In `MSP-IMPROV-S01A-M01-P-FM01`, the `M01` segment is the
speaker:

```python
segs = fname.split("-")
speaker = f"msp_{segs[3]}" if len(segs) > 3 else f"msp_unknown"
```

Verify against your release's naming before relying on the index. The existing test uses the synthetic
stem `MSP-ABC-01` and does not assert on the speaker value, which is why the bug survives the suite —
a regression test asserting distinct speakers for distinct actors should be added alongside the fix.

### RAVDESS song samples are not filtered

`parts[1]` (vocal channel: `01` speech, `02` song) is ignored. If both archives are downloaded, sung
samples enter a speech model silently. Add `if parts[1] != "01": continue` if that is not what you
want.

### Intensity is pooled in both RAVDESS and CREMA-D

Normal and strong (RAVDESS `01`/`02`) and LO/MD/HI/XX (CREMA-D) renditions are treated identically.
Reasonable as a default — more data per class — but it means the model sees a wide range of expression
intensity under one label, and intensity-stratified evaluation is not possible without re-parsing.

### No class stratification across splits

See [Properties](#properties). With few speakers, a test split may under-represent or entirely miss a
class, making per-class F1 unstable across seeds.
