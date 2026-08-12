"""
Gap chains — the intellectual core of the review.

    GAP -> CAUSE -> METHOD -> RESEARCH QUESTION

WHY THIS FILE EXISTS SEPARATELY FROM THE TRACKER
    The tracker's Gap Chains sheet was generated with blank rows waiting to be
    filled in by hand. Hand-filled rows drift: a number changes in an experiment
    and nobody updates the spreadsheet. These chains are data, so the sheet is
    generated from them and every claim carries the evidence that supports it.

THE DISCIPLINE THIS ENCODES
    A research gap is NOT the same as a paper's limitation. Every chain below
    must survive three questions:

      1. Is the gap real, or am I asserting it?  -> `evidence` names what was
         actually run or read.
      2. Did someone already close it?           -> `responders` lists who tried
         and `status` records the answer honestly, including "closed".
      3. Does my method match the CAUSE?         -> `cause_mechanism_match`. A
         method that fixes a different cause than the one producing the gap is
         the most common way a proposal falls apart under questioning.

    Type (c) — scope gaps — carry the most weight for this thesis and are also
    the easiest to overclaim. "M3ER does not run on a Raspberry Pi" is not a
    criticism of M3ER; it never claimed to. It is a field-level gap relative to
    a healthcare/edge/real-time lens, and it must be stated that way.
"""

# Convenience: the papers referenced below, so citations stay consistent.
PAPERS = {
    "MUTH26": ("Mutheeswaran, U., Muralitharan, D., Harshanya, M. et al. (2026). "
               "Emotion-Aware Edge Computing Framework for Next-Gen Human-Machine "
               "Collaboration. ICMCSI 2026. doi:10.1109/ICMCSI67283.2026.11412916"),
    "SENS25": ("Multi-Scale Temporal Fusion Network for Real-Time Multimodal Emotion "
               "Recognition in IoT Environments (2025). Sensors. doi:10.3390/s25165066"),
    "M3ER20": ("Mittal, T., Bhattacharya, U., Chandra, R., Bera, A., Manocha, D. (2020). "
               "M3ER: Multiplicative Multimodal Emotion Recognition. AAAI. "
               "doi:10.1609/aaai.v34i02.5492"),
    "MULT19": ("Tsai, Y.-H. H. et al. (2019). Multimodal Transformer for Unaligned "
               "Multimodal Language Sequences. ACL. doi:10.18653/v1/P19-1656"),
    "FEDCMD24": ("FedCMD: A Federated Cross-modal Knowledge Distillation for Drivers' "
                 "Emotion Recognition (2024). ACM TIST. doi:10.1145/3650040"),
    "OWN": "This project's own measured baseline (results/audio_cnn_lstm_results.json)",
}


GAP_CHAINS = [
    {
        "id": "G1",
        "paper_id": "S7 conjunction ladder",
        "citation": "slr/out/falsification_S7.json (128 clause subsets, pool n=1,062)",
        "statement": (
            "The multimodal emotion-recognition literature contains the edge-deployment, "
            "real-time-latency and privacy pieces, but does not situate them in clinical "
            "or caregiving contexts. No retrieved paper satisfies all seven clauses at "
            "once."),
        "type": "c",
        "cause": "scope",
        "responders": (
            f"NEAREST: {PAPERS['SENS25']} — satisfies every clause EXCEPT clinical "
            "context. Relaxing 'clinical' alone releases exactly this one paper. "
            f"ALSO: {PAPERS['FEDCMD24']} — federated privacy-preserving MER, but for "
            "drivers, not care settings."),
        "status": "scope",
        "method": (
            "Situate the whole stack in a caregiving context: evaluate under the "
            "conditions of that setting rather than porting an IoT/automotive system "
            "and asserting transfer."),
        "cause_mechanism_match": (
            "YES — the cause is scope (nobody has aimed at this setting), and the "
            "method is to aim at it. Note the trap: adding a clinical dataset does NOT "
            "close a scope gap by itself; the evaluation has to reflect the setting."),
        "rq": "RQ1",
        "rq2": "RQ3, RQ4",
        "evidence": (
            "Measured, not asserted. Full 7-clause conjunction returns 0 against a pool "
            "of 1,062 papers; drop 'clinical' -> 1; drop 'compression'+'edge' -> 3. The "
            "ladder is informative because relaxation DOES release papers, so the zero "
            "reflects the corpus rather than a broken query."),
        "caveat": (
            "Bounded by four databases, 2015-2026, and this clause vocabulary. One "
            "genuine counter-example outweighs the count."),
    },
    {
        "id": "G2",
        "paper_id": "MUTH26",
        "citation": PAPERS["MUTH26"],
        "statement": (
            "Reports 90.1% accuracy and 61.5 ms on a Raspberry Pi 4, but states no "
            "evaluation protocol: no train/test split, no subject-independent condition, "
            "no cross-validation. Results are given as per-'Sample ID' rows S1-S10."),
        "type": "b",
        "cause": "design choice",
        "responders": (
            "None found. The paper is recent (2026) and not yet cited. The claim is "
            "therefore unaudited rather than refuted."),
        "status": "open",
        "method": (
            "Report speaker/subject-independent evaluation explicitly, with held-out "
            "identities named, and state the protocol beside every headline number."),
        "cause_mechanism_match": (
            "YES — the cause is a reporting/design choice, and the method is a reporting "
            "and design discipline. This is directly actionable, not aspirational."),
        "rq": "RQ1",
        "rq2": "RQ2",
        "evidence": (
            "Full text read 2026-08-11. Section IV presents Tables I-V; none states a "
            "split. QA6 (evaluation protocol reported) FAILS. Corrects an earlier "
            "abstract-only reading of this project's which recorded 'no named dataset' "
            "— the full text DOES name DEAP, so QA2/QA5 pass."),
        "caveat": (
            "'Sample ID' is not defined in the paper. It may denote subjects, sessions "
            "or trials; the ambiguity is itself the finding."),
    },
    {
        "id": "G3",
        "paper_id": "MUTH26",
        "citation": PAPERS["MUTH26"],
        "statement": (
            "The 61.5 ms figure is described in the conclusion as 'end-to-end inference "
            "latency', but the supporting table measures inference across model "
            "OPTIMISATION levels (baseline / TensorRT / quantisation / combined). The "
            "paper's own preprocessing pipeline — contrast enhancement, Dlib/OpenCV face "
            "detection, landmark localisation — appears in no timing measurement."),
        "type": "b",
        "cause": "design choice",
        "responders": "None.",
        "status": "open",
        "method": (
            "Measure and report acquisition-to-result separately from model forward "
            "pass, and state which one any headline latency refers to."),
        "cause_mechanism_match": (
            "YES — a measurement-boundary problem answered by measuring the boundary."),
        "rq": "RQ3",
        "rq2": "",
        "evidence": (
            f"Full text, Table IV and Conclusion. Corroborated by {PAPERS['OWN']}: on "
            "this project's own stack the model forward pass is 22 ms while the browser "
            "reports 110-155 ms end to end — feature extraction and transport dominate. "
            "A latency claim that excludes them is not comparable to a deployment budget."),
        "caveat": (
            "The paper may have measured end-to-end and reported it under a table about "
            "optimisation levels. Without the timing harness this cannot be settled, so "
            "the finding is 'not demonstrated', not 'false'."),
    },
    {
        "id": "G4",
        "paper_id": "MUTH26",
        "citation": PAPERS["MUTH26"],
        "statement": (
            "The third modality is physiological (EEG, GSR, heart rate) via the DEAP "
            "corpus, which requires body-worn contact sensors. No camera-and-microphone-"
            "only configuration is evaluated."),
        "type": "c",
        "cause": "dataset / benchmark constraint",
        "responders": (
            "DEAP itself is the constraint: it is a laboratory corpus elicited with "
            "music videos and instrumented with EEG/GSR, so any work built on it "
            "inherits contact sensing and lab conditions."),
        "status": "scope",
        "method": (
            "Keep the sensor set to camera and microphone, and take the third stream "
            "from behaviour (pose/gesture) rather than physiology — contactless by "
            "construction."),
        "cause_mechanism_match": (
            "YES — the cause is a dataset/instrumentation constraint and the method "
            "changes the instrumentation. Caution: this is a scope difference, NOT a "
            "criticism. Contact sensors are a legitimate choice; they are simply "
            "unusable where a person cannot be instrumented."),
        "rq": "RQ2",
        "rq2": "RQ4",
        "evidence": (
            "Full text section 3.2 names DEAP explicitly and lists EEG, GSR, HR and "
            "video with valence-arousal ratings."),
        "caveat": (
            "Do not claim contactless sensing is inherently superior. The claim is "
            "narrower and defensible: it is applicable in settings where instrumenting "
            "a person is not possible."),
    },
    {
        "id": "G5",
        "paper_id": "MUTH26",
        "citation": PAPERS["MUTH26"],
        "statement": (
            "Human evaluation is a 10-participant satisfaction survey (responsiveness, "
            "adaptability, comfort, scored out of 10; mean 9.0). No clinical validation, "
            "no care-setting deployment, no patient or caregiver population."),
        "type": "c",
        "cause": "scope",
        "responders": "None in the retrieved corpus — this is the G1 scope gap in miniature.",
        "status": "scope",
        "method": (
            "Treat usability and clinical utility as distinct claims, and do not let a "
            "satisfaction score stand in for evidence of clinical usefulness."),
        "cause_mechanism_match": (
            "PARTIAL — the honest position is that this thesis will not deliver clinical "
            "validation either, within a Master's timeframe and without ethics approval. "
            "What it can deliver is evaluation under care-relevant CONDITIONS. Claiming "
            "more than that is the trap."),
        "rq": "RQ4",
        "rq2": "RQ1",
        "evidence": "Full text Table V and the paragraph following it.",
        "caveat": (
            "This thesis will not deliver clinical validation either, within a "
            "Master's timeframe and without ethics approval. The limitation is "
            "stated about this work before it is stated about theirs."),
    },
    {
        "id": "G6",
        "paper_id": "OWN",
        "citation": PAPERS["OWN"],
        "statement": (
            "Speaker-independent evaluation collapses on positive and low-arousal "
            "valence: angry, fearful and disgust reach 0.88 recall while happy reaches "
            "0.08 and sad 0.12. The model has learned arousal, not valence."),
        "type": "a",
        "cause": "task formulation",
        "responders": (
            f"{PAPERS['M3ER20']} and {PAPERS['MULT19']} both add modalities carrying "
            "valence information (face, text) and report gains — but neither reports "
            "per-class recall under a speaker-independent split, so neither demonstrates "
            "that the valence collapse specifically is what improves."),
        "status": "open",
        "method": (
            "Add the facial stream, then report PER-CLASS recall speaker-independently "
            "before and after, so the claim is 'fusion recovers valence' rather than "
            "'fusion raises the average'."),
        "cause_mechanism_match": (
            "YES — the cause is that the acoustic channel underdetermines valence, and "
            "the method adds a channel that carries it. This is the tightest "
            "cause/mechanism pairing in the whole review and the strongest single "
            "justification for multimodality in this thesis."),
        "rq": "RQ2",
        "rq2": "RQ1",
        "evidence": (
            "results/audio_cnn_lstm_results.json: n=156, held-out actors 16/17/19. "
            "Confusion matrix shows happy predicted angry 10 times of 24 — both "
            "high-arousal, differing only in valence."),
        "caveat": (
            "One split, three held-out speakers, validation-to-test gap of ~11 points. "
            "Five-fold speaker-independent CV is required before any fusion-vs-audio "
            "difference smaller than that gap can be called real."),
    },
]


def by_rq(rq: str):
    return [g for g in GAP_CHAINS if g["rq"] == rq or rq in (g.get("rq2") or "")]


def summary():
    from collections import Counter
    return {
        "total": len(GAP_CHAINS),
        "by_type": dict(Counter(g["type"] for g in GAP_CHAINS)),
        "by_status": dict(Counter(g["status"] for g in GAP_CHAINS)),
        "by_rq": dict(Counter(g["rq"] for g in GAP_CHAINS)),
    }
