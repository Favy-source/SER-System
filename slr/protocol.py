"""
SLR protocol — the single source of truth.

Every other module in slr/ and the generated tracker read from here. Nothing is
restated by hand, so the protocol cannot drift from the tooling that executes it.

TERMINOLOGY, used consistently across this package:
  Review Question   (ReQ1..ReQ7)  what the SLR asks of the LITERATURE.
                                  Descriptive and analytical, never
                                  hypothesis-testing.
  Research Question (RQ1..RQ4)    what the THESIS answers experimentally.

The handwritten notebook is the authority. Where the typed proposal differs, the
notebook wins.

Standards, deliberately kept apart:
  Kitchenham & Charters (2007)  governs how the review is CONDUCTED
  PRISMA 2020                   governs how the review is REPORTED
"""

VERSION = "2.0"
PROTOCOL_DATE = "2026-08-10"

TITLE = ("Real-Time Multimodal Speech and Facial Emotion Recognition "
         "for Healthcare and Caregiving Support")
CANDIDATE = "Nwachukwu Chinemerem Favour"
PROGRAMME = "MMU Master of Computing (by Research) — application P2602387"
SUPERVISOR = "Assoc. Prof. Ts. Dr. R. Kanesaraj Ramasamy"
CO_SUPERVISOR = "Assoc. Prof. Dr. Wan Noorshahida Binti Mohd Isa"


# ---------------------------------------------------------------------------
# The inclusion test
# ---------------------------------------------------------------------------
# Every included paper either SUPPORTS or CHALLENGES this sentence. If it does
# neither, it is Background or it is out. This is the most useful screening
# heuristic in the protocol, which is why it sits at the top of the tracker.

CENTRAL_THESIS = (
    "Multimodal emotion recognition has achieved impressive accuracy, but current "
    "systems remain insufficient for real-world healthcare and caregiving deployment "
    "due to limitations in dataset realism, real-time performance, computational "
    "efficiency, privacy, and ethical implementation."
)

GOLDEN_THREAD = (
    "The questions drive the search → the extracted data answers the questions → "
    "the synthesis reveals the gaps → the gaps justify the framework."
)

SLR_OBJECTIVE = (
    "To systematically review existing multimodal speech and facial emotion recognition "
    "techniques for healthcare and caregiving applications, identifying prevailing "
    "methodologies, datasets, fusion strategies, evaluation metrics, deployment "
    "approaches and research gaps that inform the design of a real-time, privacy-aware "
    "and resource-efficient emotion recognition framework."
)

WHY_NOT_AN_EXISTING_SURVEY = (
    "Surveys of multimodal emotion recognition exist, but they treat fusion accuracy, "
    "edge deployment, and healthcare ethics as SEPARATE literatures. This review's "
    "contribution is the intersection of the three."
)


# ---------------------------------------------------------------------------
# Review Questions — handwritten notebook, Step 3
# ---------------------------------------------------------------------------

REVIEW_QUESTIONS = {
    "ReQ1": "What multimodal emotion recognition approaches have been proposed for "
            "healthcare and caregiving environments?",
    "ReQ2": "Which speech, facial and behavioural features are most commonly used for "
            "multimodal emotion recognition?",
    "ReQ3": "Which deep learning architectures and multimodal fusion strategies have "
            "demonstrated the best performance?",
    "ReQ4": "Which datasets are most frequently used, and how representative are they "
            "of real-world healthcare settings?",
    "ReQ5": "What evaluation metrics are commonly used to assess emotion recognition "
            "performance?",
    "ReQ6": "What challenges remain regarding real-time deployment, computational "
            "efficiency, robustness, privacy, interpretability and ethical "
            "implementation?",
    "ReQ7": "What research gaps should future multimodal emotion recognition systems "
            "address for healthcare and caregiving applications?",
}


# ---------------------------------------------------------------------------
# Research Questions — proposal. Answered by the thesis, not by the review.
# ---------------------------------------------------------------------------

RESEARCH_QUESTIONS = {
    "RQ1": "Can multimodal emotion recognition consistently outperform unimodal "
           "baselines in realistic healthcare environments, including under conditions "
           "of noise, occlusion, and speaker variation?",
    "RQ2": "Which combination of speech, facial, and behavioural features and which "
           "fusion strategy yields the most accurate and robust emotion classification "
           "across diverse clinical conditions?",
    "RQ3": "How can a multimodal affective computing system achieve real-time, "
           "low-latency inference on resource-constrained or edge devices without "
           "unacceptable accuracy loss?",
    "RQ4": "What ethical and privacy-by-design principles must govern the development "
           "and deployment of emotion-sensing systems in healthcare settings, and how "
           "should they be operationalised in the framework architecture?",
}

# Review Question -> Research Question. Each gap maps to exactly ONE primary
# Research Question (M3ER rule); a gap that maps to none means either the RQ set
# is incomplete or the gap is out of scope — resolve it, never leave it dangling.
#
# ReQ4 and ReQ5 land on RQ1 rather than being demoted to "methodology", because
# RQ1 already contains both clauses they interrogate: "realistic healthcare
# environments" (representativeness) and "speaker variation" (protocol).
REQ_TO_RQ = {
    "ReQ1": ["RQ1"],
    "ReQ2": ["RQ2"],
    "ReQ3": ["RQ2"],
    "ReQ4": ["RQ1"],   # dataset representativeness -> "realistic environments"
    "ReQ5": ["RQ1"],   # evaluation protocol        -> "speaker variation"
    "ReQ6": ["RQ3", "RQ4"],
    "ReQ7": ["RQ1", "RQ2", "RQ3", "RQ4"],   # synthesis; feeds all four
}

REQ_TO_RQ_NOTE = (
    "ReQ6 spans RQ3 and RQ4. Optional tidy: split into ReQ6a "
    "(deployment/efficiency/robustness -> RQ3) and ReQ6b "
    "(privacy/ethics/interpretability -> RQ4) so every gap maps to exactly one "
    "Research Question without ambiguity."
)


# ---------------------------------------------------------------------------
# Scope — what the review includes and excludes, stated before searching
# ---------------------------------------------------------------------------

SCOPE_IN = [
    "Multimodal (two or more modalities) emotion or affect recognition",
    "Unimodal speech or facial emotion recognition, as baselines or foundations",
    "Fusion strategies: feature-level, decision-level, attention/cross-modal, tensor, hybrid",
    "Model compression and edge deployment of affect-recognition models",
    "Healthcare, clinical and caregiving applications of affect sensing",
    "Ethics, privacy-by-design and regulatory analysis of affect sensing in health contexts",
    "Publication window 2015-2026, plus the named seminal exceptions below",
]

SCOPE_OUT = [
    "Emotion generation or synthesis with no recognition component",
    "Non-human affect (animal, synthetic agents as subjects)",
    "Text-only sentiment analysis with no audio or visual stream",
    "Affect sensing with no bearing on deployment, robustness, or healthcare relevance",
    "Non-English publications; inaccessible full text",
]

# IC2 exceptions — retrieved regardless of date because the field's vocabulary
# depends on them.
SEMINAL_ALLOWLIST = [
    ("Busso", 2004, "IEMOCAP lineage / multimodal affect analysis"),
    ("Ekman", None, "basic emotion taxonomy underpinning every discrete label set"),
    ("Picard", None, "Affective Computing — founds the field"),
]

YEAR_MIN = 2015
YEAR_MAX = 2026

YEAR_WINDOW_RATIONALE = (
    "2015-2026 is retained rather than narrowed to 2020-2026. A 2020 cutoff would "
    "exclude Zadeh et al. 2017 (Tensor Fusion Network — a worked example in this "
    "tracker), Tsai et al. 2019 (MulT — the primary responder in the M3ER gap "
    "analysis), Lim et al. 2016, and Livingstone & Russo 2018 (RAVDESS — the corpus "
    "used in the accompanying implementation). Excluding the works this research "
    "already cites, and the dataset it already uses, would be incoherent. Recency is "
    "instead DEMONSTRATED by stratifying the synthesis 2015-2019 vs 2020-2026. For "
    "ReQ6 (edge deployment) pre-2020 hardware and runtimes are largely obsolete; that "
    "is a reason to weight recent work in the synthesis, not to exclude at screening."
)


# ---------------------------------------------------------------------------
# Inclusion / Exclusion criteria
# ---------------------------------------------------------------------------

INCLUSION = {
    "IC1": "Peer-reviewed journal or conference paper, OR a high-citation / "
           "high-relevance preprint (preprints are flagged and down-weighted in QA)",
    "IC2": f"Published {YEAR_MIN}-{YEAR_MAX}, plus the named seminal pre-{YEAR_MIN} "
           "exceptions (Busso 2004; Ekman; Picard), retrieved regardless of date",
    "IC3": "Addresses at least one Review Question: multimodal or unimodal emotion "
           "recognition, fusion strategy, compression / edge deployment, or "
           "healthcare and ethics of affect sensing",
    "IC4": "Reports empirical results (quantitative metrics), OR is a substantive "
           "review, regulatory or ethics analysis relevant to ReQ6/ReQ7",
    "IC5": "Uses at least one recognised modality (speech, face, text, physiological, "
           "behavioural/skeletal); English language; full text accessible",
}

EXCLUSION = {
    "EC1": "No empirical evaluation AND not a review, position or regulatory analysis",
    "EC2": "Purely unimodal with no comparative or foundational value to the Review "
           "Questions (unimodal baselines are retained)",
    "EC3": "Non-human affect, or emotion synthesis/generation only (no recognition)",
    "EC4": "Duplicate or superseded version — keep the peer-reviewed version of a "
           "preprint/published pair, recording the preprint as a merged alias",
    "EC5": "Inaccessible full text, non-English, editorial, abstract-only, or "
           "non-archival workshop note without results",
}


# ---------------------------------------------------------------------------
# Quality assessment — score each 0 / 0.5 / 1. High quality = >= 7/10.
# ---------------------------------------------------------------------------

QUALITY = {
    "QA1":  "Research aims / questions clearly stated?",
    "QA2":  "Datasets clearly described (size, modalities, labels, splits)?",
    "QA3":  "Model / fusion architecture reproducibly described?",
    "QA4":  "Baselines and comparison methods appropriate?",
    "QA5":  "Evaluation metrics appropriate and clearly defined (accuracy, weighted-F1, "
            "UAR, MAE, correlation)?",
    "QA6":  "Evaluation protocol sound (train/val/test separation, cross-validation, "
            "SPEAKER-INDEPENDENCE)?",
    "QA7":  "Robustness / generalisation tested (noise, occlusion, missing modality, "
            "cross-dataset)?",
    "QA8":  "Latency / compute / memory reported? (critical for ReQ6 -> RQ3)",
    "QA9":  "Limitations and threats to validity discussed?",
    "QA10": "Code / data available for reproducibility?",
}
QA_HIGH_QUALITY_THRESHOLD = 7.0


# ---------------------------------------------------------------------------
# Databases — the free, programmatic, reproducible set.
# ---------------------------------------------------------------------------
# No institutional access to Scopus, Web of Science, IEEE Xplore or ACM DL. That
# is stated plainly as a threat to validity (T1) rather than hedged. The
# substitution is defensible: queries here are executed as code against open
# APIs, so the filter is inspectable and anyone can re-run the review exactly —
# which a subscription index does not permit.

DATABASES = {
    "D1": ("OpenAlex", "Primary spine. ~250M works; indexes IEEE/ACM/Springer/Elsevier "
                       "metadata. Provides abstracts, open-access status, citation counts, "
                       "and the forward/backward citation graph used for gap analysis."),
    "D2": ("Crossref", "DOI authority and venue normalisation."),
    "D3": ("PubMed (E-utilities)", "Healthcare and clinical angle — ReQ1, ReQ6. Free."),
    "D4": ("arXiv", "Preprints. Flagged and down-weighted per IC1; superseded by the "
                    "published version per EC4."),
    "D5": ("DBLP", "Computer-science venue coverage (ICMI, ICASSP, FG, ACII)."),
    "D6": ("Semantic Scholar", "Optional. Free API key required; widens forward-citation "
                               "coverage beyond OpenAlex alone."),
    "D7": ("Snowballing", "Backward and forward citation traversal from seed papers "
                          "(M3ER, MulT, TFN, Mamieva 2023, Xie 2021, Lian 2023). "
                          "Implements step 3 of the gap-analysis method."),
    "D8": ("Google Scholar", "Manual recall check ONLY. Cannot be automated and is not "
                             "reproducible, so it is not a primary database."),
}


# ---------------------------------------------------------------------------
# Search strings, each tagged with the Review Question it serves
# ---------------------------------------------------------------------------

SEARCH_STRINGS = [
    {
        "id": "S1",
        "serves": ["ReQ1", "ReQ2", "ReQ3"],
        "purpose": "Primary string — fusion and performance",
        # Topic clause widened at the pilot stage — see AMENDMENTS["A1"]. The
        # original three phrases missed MulT (Tsai et al. 2019), a named primary
        # responder in the gap analysis, because its abstract says "multimodal
        # human language" and never "emotion recognition".
        "string": '("emotion recognition" OR "affect recognition" OR "sentiment analysis" '
                  'OR "affective computing" OR "emotion classification" '
                  'OR "emotion detection" OR "emotion prediction" '
                  'OR "multimodal language" OR "affect detection") '
                  'AND (multimodal OR "multi-modal" OR audiovisual OR "audio-visual") '
                  'AND (fusion OR "cross-modal attention" OR transformer OR "tensor fusion" '
                  'OR "late fusion" OR "early fusion") '
                  'AND (speech OR facial OR "facial expression" OR prosod* OR gesture OR skeletal)',
    },
    {
        "id": "S2",
        "serves": ["ReQ6"],
        "purpose": "Robustness refinement",
        "string": '("emotion recognition" OR "affect recognition") AND (multimodal OR "multi-modal") '
                  'AND (noise OR occlusion OR "missing modality" OR robust* OR "speaker variation")',
    },
    {
        "id": "S3",
        "serves": ["ReQ6"],
        "purpose": "Edge deployment and compression",
        "string": '("emotion recognition" OR "affective computing" OR "speech emotion" '
                  'OR "facial expression") AND (quantiz* OR quantis* OR pruning '
                  'OR "knowledge distillation" OR "model compression" OR TinyML OR "edge" '
                  'OR "on-device") AND ("Raspberry Pi" OR "Jetson" OR embedded OR "real-time" '
                  'OR latency OR inference)',
    },
    {
        "id": "S4",
        "serves": ["ReQ1", "ReQ6"],
        "purpose": "Healthcare context and ethics (PubMed-oriented)",
        "string": '("affective computing" OR "emotion recognition" OR "emotion AI") '
                  'AND (healthcare OR clinical OR patient OR elderly OR dementia '
                  'OR "mental health" OR "pain assessment" OR caregiving) '
                  'AND (deployment OR pilot OR monitoring OR ethics OR privacy '
                  'OR "privacy-by-design" OR consent OR GDPR OR "AI Act")',
    },
    {
        "id": "S5",
        "serves": ["ReQ6"],
        "purpose": "Missing-modality sub-literature",
        "string": '("multimodal emotion recognition") AND ("missing modality" '
                  'OR "modality dropout" OR "incomplete multimodal")',
    },
    {
        "id": "S6",
        "serves": ["ReQ2", "ReQ3"],
        "purpose": "Tight speech + face intersection",
        "string": '("speech emotion recognition") AND ("facial expression recognition")',
    },
    {
        "id": "S8",
        "serves": ["ReQ4"],
        "purpose": "Dataset representativeness — the second clause of ReQ4, 'how "
                   "representative are they of real-world healthcare settings?'. Targets "
                   "the benchmark-validity literature rather than papers that merely USE "
                   "a dataset.",
        "string": '("emotion recognition" OR "affective computing" OR "affect recognition") '
                  'AND (dataset OR corpus OR benchmark) '
                  'AND (acted OR spontaneous OR "in-the-wild" OR naturalistic '
                  'OR "ecological validity" OR bias OR representativeness '
                  'OR generalis* OR generaliz*)',
    },
    {
        "id": "S9",
        "serves": ["ReQ5"],
        "purpose": "Evaluation protocol and metric critique — ReQ5. This is the string "
                   "that can produce an ORIGINAL quantitative finding: how many studies "
                   "actually evaluate speaker-independently, and how much reported "
                   "performance depends on that choice.",
        "string": '("speech emotion recognition" OR "emotion recognition" '
                  'OR "affect recognition") '
                  'AND ("speaker-independent" OR "speaker independent" OR "speaker-dependent" '
                  'OR "cross-corpus" OR "leave-one-speaker-out" OR LOSO '
                  'OR "unweighted average recall" OR UAR OR "evaluation protocol" '
                  'OR reproducib*)',
    },
    {
        "id": "S7",
        "serves": ["ReQ6", "ReQ7"],
        "purpose": "Falsification test — does the paper that would close RQ3/RQ4 exist? "
                   "Run as a relaxed conjunction ladder, dropping one clause at a time, "
                   "so the UNOCCUPIED combination is identified rather than a bare zero.",
        "string": '(multimodal OR "three modalit*" OR trimodal) AND ("emotion recognition") '
                  'AND (compress* OR quantiz* OR distill* OR prun*) '
                  'AND ("Raspberry Pi" OR Jetson OR edge OR "on-device") '
                  'AND (latency OR "real-time" OR ms) '
                  'AND (clinical OR patient OR caregiving OR healthcare) '
                  'AND (privacy OR federated OR "differential privacy")',
    },
]

# How each Review Question is answered. Search-derived questions need a string;
# extraction-derived ones are answered from every included paper regardless of how
# it was found. Recording this stops ReQ4/ReQ5 looking like search oversights.
REQ_EVIDENCE_SOURCE = {
    "ReQ1": "search-derived (S1, S4)",
    "ReQ2": "search-derived (S1, S6) + extraction (Modalities Used)",
    "ReQ3": "search-derived (S1, S6) + extraction (Fusion Strategy, Architecture)",
    "ReQ4": "extraction-derived (Dataset(s)) + search-derived (S8) for the "
            "representativeness clause",
    "ReQ5": "extraction-derived (Evaluation Protocol, Metric Type) + search-derived "
            "(S9) for the protocol-critique literature",
    "ReQ6": "search-derived (S2, S3, S4, S5, S7)",
    "ReQ7": "synthesis-derived — emerges from the Gap Chains sheet, never searched for "
            "directly",
}


# Seeds for D7 snowballing. M3ER is the worked teaching example; its known
# responders (MulT, MMIN, GCNet) double as the citation-traversal test.
SNOWBALL_SEEDS = [
    ("10.1609/aaai.v34i02.5492", "M3ER (Mittal et al., AAAI 2020) — teaching example"),
    ("10.18653/v1/P19-1656",     "MulT (Tsai et al., ACL 2019) — responder to GAP A"),
    ("10.3390/s23125475",        "Mamieva et al. 2023 — attention fusion, speech+face"),
    ("10.3390/s21144913",        "Xie et al. 2021 — transformer cross-modality fusion"),
    ("10.3390/e25101440",        "Lian et al. 2023 — survey of multimodal ER"),
]


# ---------------------------------------------------------------------------
# Gap analysis vocabulary — the taught method
# ---------------------------------------------------------------------------
# "A research gap is not the same as a paper's limitation."
# Chain: GAP -> CAUSE -> METHOD -> RESEARCH QUESTION

GAP_TYPES = {
    "a": "Author-stated — a limitation or future-work item the authors themselves flag. "
         "Trustworthy (they know their method) but somewhat self-serving (they frame it "
         "as easy to fix). Quote verbatim.",
    "b": "Attributed by later papers — a limitation that follow-up work pins on the "
         "study, usually by proposing a fix. Attribute the critique to the RESPONDER, "
         "not to the original authors.",
    "c": "Scope gap — something the paper never claimed to do, but which falls inside "
         "THIS review's healthcare / edge / real-time lens. Report as a scope gap, never "
         "as a failure. Criticising a paper for not doing what it never set out to do is "
         "a rookie move; reframing it as a field-level scope gap is the intellectual core "
         "of the justification.",
}

GAP_CAUSES = [
    "design choice",
    "dataset / benchmark constraint",
    "task formulation",
    "scope",
]

GAP_STATUS = {
    "closed": "Adequately solved by later work. Useful for background and history, not "
              "for justifying new research.",
    "open":   "No adequate solution exists. This is where a contribution lives.",
    "scope":  "Never attempted by the paper, but relevant to this review's lens.",
}

CAUSE_TO_MECHANISM_RULE = (
    "Match the CAUSE of the gap to the MECHANISM of the candidate method. If a gap "
    "exists because a fusion rule cannot model cross-modal interaction, the best-suited "
    "fix is a method whose mechanism IS cross-modal interaction. If a gap exists because "
    "a method assumes modalities co-occur, the best-suited fix reconstructs missing "
    "modalities. This cause-to-mechanism matching is the heart of good gap analysis."
)

# Six prompt questions applied to every paper.
GAP_METHOD_STEPS = [
    "1. What did it NOT do? Quote the authors' own limitations / future-work verbatim.",
    "2. WHY did that gap happen? Classify the cause (design choice, dataset/benchmark "
    "constraint, task formulation, or scope). The cause determines the best-suited fix.",
    "3. WHO fixed it, if anyone? Forward-citation search. For each responder record "
    "method + dataset + result. Attribute the critique to the responder.",
    "4. Is it still OPEN? closed = adequately solved; open = no adequate solution; "
    "scope = never attempted but relevant to this review.",
    "5. Which Research Question does it touch? Map to exactly one primary (secondary "
    "allowed). No mapping means the RQ set is incomplete or the gap is out of scope.",
    "6. Cause-to-mechanism check: does the candidate method's mechanism directly attack "
    "the gap's cause? If not, keep looking.",
]


# ---------------------------------------------------------------------------
# Extraction schema
# ---------------------------------------------------------------------------
# One row per INCLUDED paper. Every column filled; write 'NR' when a paper does
# not report something — the PATTERN OF NRs IS ITSELF A FINDING, and is what
# demonstrates the gap rather than asserting it.

EXTRACTION_COLUMNS = [
    ("ID",                          10, "EX1, EX2, ..."),
    ("Citation (Author, Year)",     22, ""),
    ("Title",                       46, ""),
    ("DOI",                         26, ""),
    ("Venue",                       22, ""),
    ("Venue Type",                  12, "journal / conference / preprint / thesis"),
    ("Year",                         7, ""),
    ("OA Status",                   10, "gold / green / hybrid / closed"),
    ("Modalities Used",             20, "speech / facial / text / physiological / behavioural"),
    ("Task Type",                   18, "categorical emotion / sentiment regression / "
                                        "dimensional / multi-label  -- NEVER pool these"),
    ("Fusion Strategy",             20, "feature-level / decision-level / cross-modal "
                                        "attention / tensor / hybrid / n-a"),
    ("Architecture / Model",        26, ""),
    ("Dataset(s)",                  24, ""),
    ("Emotion Classes",             16, ""),
    ("Evaluation Protocol",         20, "random split / speaker-independent / LOSO / "
                                        "k-fold SI / cross-corpus / NR"),
    ("Metric Type",                 16, "accuracy / WA / UA(UAR) / weighted-F1 / macro-F1"),
    ("Best Accuracy (%)",           12, ""),
    ("Best Weighted F1",            12, ""),
    ("Unimodal Baseline Compared?", 14, "Yes / No / NR"),
    ("Robustness Tested",           20, "noise / occlusion / missing modality / "
                                        "cross-dataset / No / NR"),
    ("Real-Time Capable?",          12, "claimed Yes / No / NR"),
    ("Latency Reported (ms)",       14, "value, and whether END-TO-END or model-forward only"),
    ("Model Size / Params",         14, ""),
    ("Edge Hardware Used",          16, "Raspberry Pi / Jetson / MCU / none / NR"),
    ("Compression",                 16, "pruning / quantisation / distillation / none / NR"),
    ("Healthcare / Caregiving?",    14, "Yes / mentioned only / No"),
    ("Ethics / Privacy Discussed?", 14, "Yes / No"),
    ("Author-Stated Limitations",   40, "VERBATIM quote — gap-method step 1"),
    ("Supports or Challenges?",     16, "supports / challenges / background  "
                                        "-- the central-thesis inclusion test"),
    ("Relevant ReQs",               14, "ReQ1..ReQ7"),
    ("Key Findings (1-2 lines)",    40, ""),
    ("QA Score (/10)",              10, f">= {QA_HIGH_QUALITY_THRESHOLD} = high quality"),
]

GAP_CHAIN_COLUMNS = [
    ("Gap ID",                  10, "G1, G2, ..."),
    ("Paper ID",                10, "links to Data Extraction ID"),
    ("Citation",                20, ""),
    ("Gap Statement",           44, "plain language first, then academic framing"),
    ("Gap Type",                12, "a = author-stated / b = pinned by later papers / "
                                    "c = SCOPE GAP relative to this review"),
    ("Cause",                   22, " / ".join(GAP_CAUSES)),
    ("Responders (paper + method + dataset + result)", 46, "forward-citation search — step 3"),
    ("Status",                  12, "closed / open / scope"),
    ("Best-Suited Method",      32, "cause-to-mechanism match"),
    ("Cause<->Mechanism match?", 14, "Yes / No — does the fix attack the CAUSE?"),
    ("Primary Research Question", 14, "exactly ONE of RQ1..RQ4"),
    ("Secondary RQ",            12, "optional"),
    ("Notes",                   30, ""),
]


# ---------------------------------------------------------------------------
# Protocol amendments
# ---------------------------------------------------------------------------
# Kitchenham & Charters require the protocol to be piloted before execution and
# any change to be RECORDED with its trigger and rationale. An unrecorded change
# to a search string is indistinguishable from fitting the protocol to a corpus
# you have already seen, which is the failure a reviewer will look hardest for.
#
# Each amendment below was triggered by an automated calibration test, not by
# reading results — the recall-anchor tests in tests/test_slr_live.py assert that
# works already cited in the proposal are retrievable by the protocol's own
# strings. A failure there means the strings are too narrow, and it fires before
# any screening decision is made.

AMENDMENTS = [
    {
        "id": "A1",
        "date": "2026-08-10",
        "stage": "pilot, before any screening decision",
        "target": "S1, topic clause",
        "trigger": ("Recall anchor failed: MulT (Tsai et al., ACL 2019) — a named "
                    "primary responder in the gap analysis and an existing "
                    "reference of the proposal — satisfied clauses 2, 3 and 4 of "
                    "S1 but failed clause 1."),
        "cause": ("The topic clause was locked to three exact phrases. MulT's "
                  "title and abstract describe the task as 'multimodal human "
                  "language' and never use 'emotion recognition', 'affect "
                  "recognition' or 'sentiment analysis', despite being evaluated "
                  "on IEMOCAP and CMU-MOSI."),
        "change": ("Added the field's other established task names to the S1 topic "
                   "clause: 'affective computing', 'emotion classification', "
                   "'emotion detection', 'emotion prediction', 'affect detection', "
                   "and 'multimodal language'."),
        "rationale": ("These are synonyms already in use in this literature, not "
                      "terms reverse-engineered from one paper. Widening a topic "
                      "clause lowers precision and raises recall; for a review "
                      "whose central claim is about what the field has NOT done, "
                      "a false negative is far more damaging than a false "
                      "positive, because an over-retrieved paper is discarded at "
                      "screening while a missed one is invisible."),
        "effect_on_prior_work": "None — no screening had been performed.",
    },
]


# ---------------------------------------------------------------------------
# Threats to validity — required by the method, and this review has real ones
# ---------------------------------------------------------------------------

THREATS = [
    ("T1", "No subscription indexes",
     "No institutional access to Scopus, Web of Science, IEEE Xplore or ACM DL. No "
     "subscription-index recall baseline can be reported.",
     "Free sources with wide metadata coverage (OpenAlex indexes IEEE/ACM/Springer/"
     "Elsevier records). Queries executed as inspectable code, so the review is exactly "
     "reproducible — which a subscription index does not permit."),
    ("T2", "English-language only",
     "IC5 restricts to English; non-English work is excluded and may carry relevant "
     "clinical evidence.", "Stated as a limitation. Not mitigated."),
    ("T3", "Publication bias",
     "Positive results are over-represented in the published record; negative or null "
     "fusion results are under-published.",
     "Preprints (D4) are searched, which surfaces some unpublished negative results."),
    ("T4", "Single-reviewer screening",
     "One reviewer performs screening and extraction, so no inter-rater agreement "
     "(Cohen's kappa) can be reported and selection bias cannot be quantified.",
     "Mechanical criteria are applied by code with a recorded reason per decision, so "
     "the deterministic part of screening is auditable and repeatable. Judgement calls "
     "remain single-reviewer and are declared as such."),
    ("T5", "Incomplete abstract coverage",
     "OpenAlex lacks abstracts for some older and some Elsevier records.",
     "Records without abstracts are SURFACED for title-only screening, never silently "
     "dropped. Their count is reported."),
    ("T6", "Google Scholar not automatable",
     "D8 cannot be scripted, so the recall check is manual and not reproducible.",
     "Used only as a supplementary recall check, never as a primary source; its "
     "contribution is reported separately."),
    ("T7", "Full-text access",
     "Without subscriptions, some full texts are unobtainable, forcing EC5 exclusions "
     "that are access-driven rather than content-driven.",
     "Open-access status is recorded per record and exports are sorted by "
     "retrievability. Author contact is used for key papers. EC5-by-access exclusions "
     "are counted and reported separately from EC5-by-content."),
    ("T8", "Forward-citation coverage varies",
     "Citation graphs differ between providers; OpenAlex alone will miss some responders, "
     "which matters because step 3 of the gap method depends on them.",
     "Snowballing (D7) supplements automated traversal; a Semantic Scholar key (D6) "
     "would widen coverage further."),

    ("T9", "OpenAlex splits one work across several records",
     "OpenAlex frequently holds a single paper as separate preprint, conference and "
     "journal records WITHOUT merging their citation counts, and a DOI resolves to only "
     "one of them. Measured on M3ER (Mittal et al., AAAI 2020): the AAAI DOI resolves to "
     "a record with 21 citations, while the same paper also exists as a record with 256. "
     "Seeding forward-citation traversal from the DOI alone would therefore reach 21 of "
     "278 citing papers — missing 92% of the responders — and would leave no trace of the "
     "loss in the output. Any snowballing that starts from a DOI alone is unsound.",
     "citations.forward() fans out to every OpenAlex record sharing the seed's normalised "
     "title (openalex.siblings()) and unions their citing sets, de-duplicating by OpenAlex "
     "ID. The number of records found per seed is reported in prisma.json so the fan-out "
     "is auditable. Detected by an automated calibration test, not by inspection."),

    ("T10", "Crossref exposes no language field",
     "`language` is not a selectable Crossref field, so records retrieved from Crossref "
     "alone carry no language metadata and cannot be screened against IC5 on that basis.",
     "IC5 language screening EXCLUDES only on an explicit non-English value; absence is "
     "flagged `language_unreported` and left to manual screening. Crossref records that "
     "merge with an OpenAlex or PubMed record inherit a language. The count of records "
     "screened without language metadata is reported in prisma.json."),
]


# ---------------------------------------------------------------------------
# Traps — the errors that separate a weak SLR from a strong one, each with the
# structural guard that prevents it in this tracker.
# ---------------------------------------------------------------------------

TRAPS = [
    ("Reading before the protocol is locked",
     "Biases the corpus toward what you already believe.",
     "This Protocol sheet is version-stamped and dated. Lock it before searching."),
    ("Paper-by-paper summary instead of synthesis",
     "'Paper A did X, Paper B did Y' is summarising, not synthesising.",
     "The Synthesis sheet is REVIEW-QUESTION-shaped, not paper-shaped. It forces "
     "patterns, contradictions and trends across studies."),
    ("Asserting the gap instead of demonstrating it",
     "The whole justification collapses if the gap is claimed rather than evidenced.",
     "Gap Chains requires RESPONDERS and a STATUS for every gap. A gap with no "
     "forward-citation search behind it is not yet a gap."),
    ("Conflating a limitation with a gap",
     "A limitation belongs to one paper; a gap belongs to the field.",
     "The Gap Type column forces a / b / c, and 'c' names scope gaps explicitly."),
    ("Comparing incomparable metrics",
     "Accuracy vs UAR on imbalanced data, or sentiment regression vs categorical "
     "emotion, are not comparable.",
     "Task Type and Metric Type are mandatory extraction columns, and the synthesis "
     "stratifies rather than pools."),
    ("Background confused with Results",
     "Background explains concepts; Results synthesise evidence thematically.",
     "Separate concerns: the Protocol sheet holds concepts, the Synthesis sheet holds "
     "evidence, one block per Review Question."),
    ("Scope too broad or too narrow",
     "Too broad and you drown; too narrow and the corpus is thin.",
     "Explicit SCOPE IN / SCOPE OUT lists on the Protocol sheet, fixed before searching."),
]


# ---------------------------------------------------------------------------
# Workflow — Kitchenham's three phases
# ---------------------------------------------------------------------------

WORKFLOW = [
    ("PLAN", "S1", "Establish the need; fix the Review Questions; write this protocol. "
                   "Writing the protocol BEFORE searching is the single move that makes "
                   "the review systematic."),
    ("PLAN", "S2", "Lock scope, IC/EC, QA instrument and extraction schema. No reading yet."),
    ("CONDUCT", "S3", "Run each search string on each source. Log every run in Search Log "
                      "with date and hit count."),
    ("CONDUCT", "S4", "Import all records into Screening. Dedupe: DOI exact -> normalised "
                      "title + year -> preprint/published pairing (EC4)."),
    ("CONDUCT", "S5", "Title/abstract screen: Include / Exclude / Maybe. When in doubt at "
                      "this stage, keep it in."),
    ("CONDUCT", "S6", "Full-text screen on survivors: final Include/Exclude with an EC "
                      "reason code. Record access-driven exclusions separately (T7)."),
    ("CONDUCT", "S7", "Quality-appraise every included study with QA1-QA10."),
    ("CONDUCT", "S8", "Extract every included paper into Data Extraction — one row, every "
                      "column filled, 'NR' where not reported."),
    ("CONDUCT", "S9", "Build Gap Chains: apply the six prompt questions per paper. "
                      "Forward-citation search is mandatory for step 3."),
    ("REPORT", "S10", "Synthesis auto-counts by Review Question. These counts ARE the gap "
                      "analysis — the gap emerges from the numbers rather than being asserted."),
    ("REPORT", "S11", "PRISMA Flow auto-computes the diagram numbers."),
    ("REPORT", "S12", "Write Results thematically, ONE SECTION PER REVIEW QUESTION, then "
                      "Discussion, Research Gaps, Future Directions. Record Threats to "
                      "Validity."),
]


def orphaned_review_questions():
    """Every Review Question must map to at least one Research Question."""
    return [q for q in REVIEW_QUESTIONS if not REQ_TO_RQ.get(q)]


def review_questions_for(rq: str):
    """Which Review Questions feed a given Research Question."""
    return [req for req, rqs in REQ_TO_RQ.items() if rq in rqs]


def strings_for(req: str):
    """Which search strings serve a given Review Question."""
    return [s["id"] for s in SEARCH_STRINGS if req in s["serves"]]
