# Results — chapter skeleton

Generated from `slr/protocol.py` v2.1 and `slr/gaps.py`. Re-run `python3 -m slr.results_skeleton` after any protocol change.

**Every table below is empty on purpose.** Filling them requires screening and extraction decisions that are mine to make. A skeleton pre-filled with plausible numbers is the easiest way to end up reporting something nobody counted.

## The thread this chapter has to hold

> The questions drive the search → the extracted data answers the questions → the synthesis reveals the gaps → the gaps justify the framework.

Each section states the extraction column that feeds it. A section with no column feeding it is a question this review cannot answer — better found now than at writing-up.

## Before any table: two rules that invalidate results if broken

1. **Never pool incomparable metrics.** Accuracy, WA, UA/UAR, weighted-F1 and macro-F1 measure different things. A mean across them is meaningless. Report them in separate columns or separate tables.
2. **Never pool incomparable tasks.** Categorical classification, dimensional regression and multi-label prediction do not share a metric space. The `Task Type` column exists to keep CMU-MOSI regression out of the same table as IEMOCAP accuracy.

---

## ReQ1. What multimodal emotion recognition approaches have been proposed for healthcare and caregiving environments?

*Feeds Research Question(s): **RQ1**. Evidence source: search-derived (S1, S4).*

### Approaches proposed for healthcare and caregiving contexts

`extraction column: Healthcare / Caregiving?`

> Count Yes / mentioned only / No. The 'mentioned only' column is the interesting one — it separates papers that TARGET care settings from papers that list healthcare as a possible application in their introduction and never return to it.

| category | n | % of included | notes |
|---|---:|---:|---|
|  |  |  |  |

### Multimodal vs unimodal performance

`extraction column: Unimodal Baseline Compared?`

> Only papers that compared can speak to this. Papers reporting a multimodal number with no unimodal baseline cannot support 'multimodal is better' and must be excluded from that claim, however good the number looks.

| category | n | % of included | notes |
|---|---:|---:|---|
|  |  |  |  |

**Gap chains landing here:** `G1` (c, scope), `G2` (b, open)

---

## ReQ2. Which speech, facial and behavioural features are most commonly used for multimodal emotion recognition?

*Feeds Research Question(s): **RQ2**. Evidence source: search-derived (S1, S6) + extraction (Modalities Used).*

### Modality combinations

`extraction column: Modalities Used`

> Cross-tabulate against Best Accuracy, but do NOT rank across datasets — see the metric-comparability warning below.

| category | n | % of included | notes |
|---|---:|---:|---|
|  |  |  |  |

### Feature representations

`extraction column: Architecture / Model`

| category | n | % of included | notes |
|---|---:|---:|---|
|  |  |  |  |

**Gap chains landing here:** `G4` (c, scope), `G6` (a, open)

---

## ReQ3. Which deep learning architectures and multimodal fusion strategies have demonstrated the best performance?

*Feeds Research Question(s): **RQ2**. Evidence source: search-derived (S1, S6) + extraction (Fusion Strategy, Architecture).*

### Fusion strategies and their reported performance

`extraction column: Fusion Strategy`

> Group by strategy; report the range, not a single best. A single best is a dataset artefact.

| category | n | % of included | notes |
|---|---:|---:|---|
|  |  |  |  |

### Architectures

`extraction column: Architecture / Model`

| category | n | % of included | notes |
|---|---:|---:|---|
|  |  |  |  |

**Gap chains landing here:** `G4` (c, scope), `G6` (a, open)

---

## ReQ4. Which datasets are most frequently used, and how representative are they of real-world healthcare settings?

*Feeds Research Question(s): **RQ1**. Evidence source: extraction-derived (Dataset(s)) + search-derived (S8) for the representativeness clause.*

### Dataset frequency

`extraction column: Dataset(s)`

> The headline count. Preliminary abstract-level signal already shows IEMOCAP dominant — confirm on full texts.

| category | n | % of included | notes |
|---|---:|---:|---|
|  |  |  |  |

### Elicitation: acted vs spontaneous

`extraction column: Dataset(s)`

> Derived from the dataset, not stated per paper: RAVDESS/SAVEE/EMO-DB are acted; IEMOCAP is elicited-improvised; MSP-Podcast and AFEW are in-the-wild. This mapping IS the representativeness argument.

| category | n | % of included | notes |
|---|---:|---:|---|
|  |  |  |  |

### Healthcare representativeness

`extraction column: Dataset(s) x Healthcare / Caregiving?`

> The gap this thesis targets: how many papers claiming healthcare relevance evaluate on a corpus recorded in a care setting? The expected answer is very few, and that is a reportable finding.

| category | n | % of included | notes |
|---|---:|---:|---|
|  |  |  |  |

**Gap chains landing here:** `G1` (c, scope), `G2` (b, open)

---

## ReQ5. What evaluation metrics are commonly used to assess emotion recognition performance?

*Feeds Research Question(s): **RQ1**. Evidence source: extraction-derived (Evaluation Protocol, Metric Type) + search-derived (S9) for the protocol-critique literature.*

### Evaluation protocol reported

`extraction column: Evaluation Protocol`

> THE headline finding candidate. Count speaker-independent / LOSO / k-fold SI / random split / cross-corpus / NOT REPORTED. The NR count is a result in itself.

| category | n | % of included | notes |
|---|---:|---:|---|
|  |  |  |  |

### Metric type

`extraction column: Metric Type`

> Accuracy, WA, UA/UAR, weighted-F1 and macro-F1 are NOT comparable. Any table mixing them is invalid; report them in separate columns.

| category | n | % of included | notes |
|---|---:|---:|---|
|  |  |  |  |

### Performance by protocol

`extraction column: Evaluation Protocol x Best Accuracy (%)`

> If speaker-independent studies report systematically lower accuracy than speaker-dependent ones, that difference is a quantitative contribution. Note: this project's own 66% val vs 55% test gap is between TWO speaker-independent 3-actor splits (speaker variance + val-selection bias), NOT speaker overlap — measuring the speaker-dependent vs speaker-independent delta directly requires a matched random-split baseline.

| category | n | % of included | notes |
|---|---:|---:|---|
|  |  |  |  |

**Gap chains landing here:** `G1` (c, scope), `G2` (b, open)

---

## ReQ6. What challenges remain regarding real-time deployment, computational efficiency, robustness, privacy, interpretability and ethical implementation?

*Feeds Research Question(s): **RQ3**. Evidence source: search-derived (S2, S3, S4, S5, S7).*

### Real-time capability and latency

`extraction column: Latency Reported (ms)`

> Record whether the figure is model-forward or end-to-end. Most papers do not say, and that ambiguity is a finding — see gap G3.

| category | n | % of included | notes |
|---|---:|---:|---|
|  |  |  |  |

### Edge deployment and compression

`extraction column: Edge Hardware Used, Compression`

| category | n | % of included | notes |
|---|---:|---:|---|
|  |  |  |  |

### Robustness

`extraction column: Robustness Tested`

> Noise, occlusion, missing modality, speaker variation — count each.

| category | n | % of included | notes |
|---|---:|---:|---|
|  |  |  |  |

### Ethics and privacy

`extraction column: Ethics / Privacy Discussed?`

> Distinguish papers that DISCUSS privacy from those that IMPLEMENT something (federated learning, on-device processing, differential privacy). The gap is usually between the two.

| category | n | % of included | notes |
|---|---:|---:|---|
|  |  |  |  |

**Gap chains landing here:** `G3` (b, open), `G5` (c, scope)

---

## ReQ7. What research gaps should future multimodal emotion recognition systems address for healthcare and caregiving applications?

*Feeds Research Question(s): **RQ1, RQ2, RQ3**. Evidence source: synthesis-derived — emerges from the Gap Chains sheet, never searched for directly.*

### Synthesis of gaps

`extraction column: (from the Gap Chains sheet)`

> Not searched for directly. Emerges from the chains: GAP -> CAUSE -> METHOD -> RESEARCH QUESTION.

| category | n | % of included | notes |
|---|---:|---:|---|
|  |  |  |  |

**Gap chains landing here:** `G1` (c, scope), `G2` (b, open), `G3` (b, open), `G4` (c, scope), `G5` (c, scope), `G6` (a, open)

---

## Threats to report alongside these results

- **T1 No subscription indexes** — No institutional access to Scopus, Web of Science, IEEE Xplore or ACM DL.
- **T2 English-language only** — IC5 restricts to English; non-English work is excluded and may carry relevant clinical evidence.
- **T3 Publication bias** — Positive results are over-represented in the published record; negative or null fusion results are under-published.
- **T4 Single-reviewer screening** — I perform screening and extraction alone, so I cannot report inter-rater agreement (Cohen's kappa) and cannot quantify selection bias.
- **T5 Incomplete abstract coverage** — OpenAlex lacks abstracts for some older and some Elsevier records.
- **T6 Google Scholar not automatable** — D8 cannot be scripted, so the recall check is manual and not reproducible.
- **T7 Full-text access** — Without subscriptions, some full texts are unobtainable, forcing EC5 exclusions that are access-driven rather than content-driven.
- **T8 Forward-citation coverage varies** — Citation graphs differ between providers; OpenAlex alone will miss some responders, which matters because step 3 of the gap method depends on them.
- **T9 OpenAlex splits one work across several records** — OpenAlex frequently holds a single paper as separate preprint, conference and journal records WITHOUT merging their citation counts, and a DOI resolves to only one of them.
- **T10 Crossref exposes no language field** — `language` is not a selectable Crossref field, so records retrieved from Crossref alone carry no language metadata and cannot be screened against IC5 on that basis.
- **T11 My search scope bounds what I can find at all** — My nine search strings all target emotion recognition.

## Gap chains in full

| ID | type | status | gap | primary RQ |
|---|---|---|---|---|
| G1 | c | scope | The multimodal emotion-recognition literature contains the edge-deployment, real-time-latency and privacy piec | RQ1 |
| G2 | b | open | Reports 90.1% accuracy and 61.5 ms on a Raspberry Pi 4, but states no evaluation protocol: no train/test split | RQ1 |
| G3 | b | open | The 61.5 ms figure is described in the conclusion as 'end-to-end inference latency', but the supporting table  | RQ3 |
| G4 | c | scope | The third modality is physiological (EEG, GSR, heart rate) via the DEAP corpus, which requires body-worn conta | RQ2 |
| G5 | c | scope | Human evaluation is a 10-participant satisfaction survey (responsiveness, adaptability, comfort, scored out of | RQ3 |
| G6 | a | open | Speaker-independent evaluation collapses on positive and low-arousal valence: angry, fearful and disgust reach | RQ2 |
