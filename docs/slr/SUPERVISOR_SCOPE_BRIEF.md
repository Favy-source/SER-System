# Master's Research Scope & SLR Update — Brief for Dr. Kanesaraj

**Candidate:** Nwachukwu Chinemerem Favour  
**Programme:** MMU Master of Computing (by Research) — 18-Month Schedule  
**Supervisors:** Assoc. Prof. Ts. Dr. R. Kanesaraj Ramasamy · Assoc. Prof. Dr. Wan Noorshahida Binti Mohd Isa  
**Working Title:** *Real-Time Facial and Speech Emotion Recognition for Healthcare and Caregiving Support*  
**Protocol Version:** v2.1 (updated `2026-11-24`, Amendment `A2` logged before manual screening)

---

## 1. Revised Master's Scope (2 Problem Statements · 3 Objectives)

Following our last consultation, the Master's scope is narrowed to a focused **Computer Science architectural contribution on one primary modality (facial expression)**, keeping **speech as a fixed secondary parameter**, and deferring Raspberry Pi / IoT deployment and behavioural streams to the PhD continuation.

### Problem Statements
- **PS1 — Generalisation & Architectural Capacity in Facial Emotion Recognition:** Existing facial and audio-visual emotion recognition models report inflated accuracy under subject-dependent splits and struggle to generalise across unseen subjects, occlusion, and subtle valence distinctions (observed directly in my own speaker-independent audio baseline: `angry`/`fearful`/`disgust` 87.5% recall vs `happy` 8.3% and `sad` 12.5%).
- **PS2 — Privacy-Preserving & Real-Time Multimodal Integration for Care Settings:** While vocal cues complement facial expression, current multimodal systems rely on heavy joint models or raw video/contact sensors that lack privacy-by-design safeguards and verified end-to-end latency for healthcare and caregiving environments.

### Research Objectives & Target Scopus Publications
| Objective | Core Activity | Target Scopus Output |
|---|---|---|
| **OB1** | Conduct a Kitchenham & Charters (2007) / PRISMA 2020 systematic review of facial and audio-visual emotion recognition architectures, datasets, evaluation protocols, and healthcare deployment gaps. | **Paper 1:** Executable PRISMA 2020 SLR |
| **OB2** | Design and modify a **hybrid facial emotion recognition architecture** (CNN + BiLSTM / attention) using privacy-preserving facial representations, with speech integrated as a fixed secondary input. | **Paper 2:** Modified Visual-Primary Hybrid Architecture |
| **OB3** | Evaluate rigorously via **5-fold subject-independent CV**, cross-corpus testing, noise/occlusion robustness, and end-to-end latency in a live web prototype (ready for pilot testing with your India mental-health collaborators / Malaysian hospitals). | **Paper 3:** Robust Evaluation & Healthcare Pilot |

### Explicitly Deferred to PhD Continuation (**PS3**)
- Embedded **IoT / Raspberry Pi** deployment and model compression (quantisation, pruning, distillation) — exploratory practice in the IoT lab after March, full contribution in PhD.
- Dedicated **speech-branch** architectural optimisation.
- Third contactless modality: **behavioural / body language** (gait and gesture, aligned with Dr. Wan Noorshahida).

---

## 2. Systematic Literature Review — Current Status

- **Protocol & Tracker:** `slr/out/SLR_Tracker_v2.xlsx` (8 sheets, generated directly from `slr/protocol.py` v2.1) and `slr/out/SLR_Working_Data.xlsx`.
- **PRISMA Snapshot (4 open APIs: OpenAlex, Crossref, PubMed, arXiv + 5-seed snowballing, 2015–2026):**
  - **2,526** records identified (`1,577` database + `949` citation traversal) → **466** duplicates merged → **2,060** unique → **31** mechanically auto-excluded (wrong year/language/non-human/errata) → **2,029** awaiting human screening.
  - Prioritised into reading tiers: **T1 = 277** (matches 2+ search strings), T2 = 947, T3 = 138, T4 = 667.
  - **Open-access recovery:** `79%` of T1 (`220/277`) already have verified OA links; **57 T1 DOIs** remain paywalled (`docs/slr/paper_request_T1_dois.txt` & `Papers_to_download_T1.xlsx`).
- **Falsification Check (S7 conjunction ladder, pool `n = 1,062`):** Full 7-clause conjunction returns **0** papers; relaxing *clinical/healthcare* alone releases **1** paper (*Sensors*, 2025, `10.3390/s25165066`), showing the gap is real and specifically clinical.
- **Next SLR Action:** Screen T1 manually via `python3 -m slr.screen_cli --tier T1` (starting with the 6 papers reporting both speaker-dependent and speaker-independent splits and the 6 at the edge+healthcare intersection in `docs/slr/READING_LIST.md`).

---

## 3. Prototype & Baseline Readiness

- **Working end-to-end real-time system:** FastAPI + WebSocket backend + React frontend with browser-side MediaPipe FaceLandmarker (**only 468 landmark coordinates leave the browser — no raw video transmitted**).
- **Audio baseline measured (RAVDESS, speaker-independent, 3 held-out actors):** `55.1%` accuracy, `0.489` macro-F1, `21.7 ms` CPU model forward / `~110–155 ms` end-to-end.
- **Visual data nearly ready:** `1,144 / 1,248` RAVDESS landmark sequences already extracted (2 actors remaining), after which I will run 5-fold subject-independent CV comparing audio baseline, standard `VisualLSTM`, fixed audio+visual fusion, and my modified hybrid visual CNN+BiLSTM architecture (plus CREMA-D for cross-corpus validation).

---

## 4. Three Decisions / Requests for Today's Meeting

1. **Scope sign-off:** Confirm the 2 Problem Statements, 3 Objectives, and Vision-primary / Speech-secondary boundary above (with RPi + behavioural deferred to PhD).
2. **Visual input representation for OB2:** Confirm whether to build the modified CNN+BiLSTM hybrid on **privacy-preserving facial landmarks/geometric graphs** (no raw face pixels leave the client — strongest healthcare ethics story) or **cropped facial ROI images** (or compare both on RAVDESS & CREMA-D).
3. **Scopus / IEEE Xplore access:** Request faculty/library access (or help retrieving the **57 paywalled T1 DOIs** in `docs/slr/Papers_to_download_T1.xlsx`) and a Scopus recall check to close Threat `T1` before submitting Paper 1.

*(Note on my earlier ORCID draft: it was an early conceptual write-up drafted before I built the speaker-independent evaluation protocol, so I do not want to submit it as-is. I plan to target **Paper 1 (this SLR)** as my first Scopus submission, then publish **Paper 2** once the 5-fold modified visual + audio experiments are complete.)*
