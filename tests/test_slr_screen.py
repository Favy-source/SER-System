"""
Tests for automated screening.

THE INVARIANT THIS FILE PROTECTS
    The tool must NEVER auto-include. Screening is the reviewer's intellectual
    contribution; a viva panel will ask who made each decision, and "a script"
    is not an acceptable answer. The first test below is the one that matters
    most — everything else is detail.

    Auto-EXCLUSION is allowed only where the criterion can be checked without
    reading the paper, and every exclusion must carry the evidence that caused
    it so it can be audited and overturned.
"""
import pytest

from slr.protocol import SEARCH_STRINGS, YEAR_MAX, YEAR_MIN
from slr.screen import screen_all, screen_one
from slr.sources.base import Record
from slr.dedupe import Merged


def rec(title, abstract="", year=2023, **kw):
    return Record(source="openalex", source_id="W1", title=title,
                  abstract=abstract, year=year, **kw)


def screen(r):
    return screen_one(r, SEARCH_STRINGS, YEAR_MIN, YEAR_MAX)


# ── the load-bearing invariant ─────────────────────────────

def test_the_tool_never_auto_includes():
    """The single most important assertion in the SLR toolkit."""
    candidates = [
        rec("Multimodal emotion recognition with cross-modal attention fusion of speech and facial expression",
            "A transformer for audio-visual fusion."),
        rec("Speech emotion recognition and facial expression recognition",
            "Two-stream model."),
        rec("Emotion recognition for dementia patients in clinical deployment",
            "Privacy and consent are addressed."),
    ]
    for r in candidates:
        s = screen(r)
        assert s.decision in ("auto-exclude", "review")
        assert s.decision != "include"
        assert "include" not in s.decision


def test_a_strong_candidate_still_only_reaches_review():
    r = rec("Multimodal emotion recognition: cross-modal attention fusion of speech and facial expression",
            "We evaluate speaker-independent performance with missing modality and report real-time "
            "latency after quantization on embedded hardware.")
    s = screen(r)
    assert s.decision == "review"
    assert len(s.record.matched_strings) >= 2
    assert s.suggestion, "a reviewable record must carry a suggestion for the human"


# ── IC2: publication window ────────────────────────────────

def test_paper_outside_the_window_is_auto_excluded_with_the_year_as_evidence():
    s = screen(rec("Multimodal emotion recognition with fusion of speech and facial expression",
                   "audio-visual", year=2009))
    assert s.decision == "auto-exclude"
    assert s.criterion == "IC2"
    assert "2009" in s.reason


def test_named_seminal_authors_survive_the_window():
    r = rec("Emotion recognition in human-computer interaction", "affect", year=2004,
            authors=["Carlos Busso", "Shrikanth Narayanan"])
    s = screen(r)
    assert s.criterion != "IC2", "the IC2 seminal allowlist must apply"


def test_a_missing_year_is_flagged_not_excluded():
    r = rec("Multimodal emotion recognition with fusion of speech and facial expression",
            "audio-visual", year=None)
    s = screen(r)
    assert s.decision == "review"
    assert "year_missing" in s.flags


# ── IC5: language ──────────────────────────────────────────

def test_explicitly_non_english_is_auto_excluded():
    r = rec("Reconnaissance multimodale des émotions", "fusion", language="fr")
    s = screen(r)
    assert s.decision == "auto-exclude" and s.criterion == "IC5"


def test_unreported_language_is_flagged_not_excluded():
    """Most Crossref records carry no language field. Excluding on absence would
    silently delete a large slice of the corpus."""
    r = rec("Multimodal emotion recognition with fusion of speech and facial expression",
            "audio-visual", language="")
    s = screen(r)
    assert s.decision == "review"
    assert "language_unreported" in s.flags


# ── EC3: non-human affect and synthesis ────────────────────

def test_non_human_affect_in_the_title_is_auto_excluded():
    r = rec("Multimodal emotion recognition in dairy cattle using audio-visual fusion",
            "We fuse speech and facial features.")
    s = screen(r)
    assert s.decision == "auto-exclude" and s.criterion == "EC3"
    assert "cattle" in s.reason.lower()


def test_animal_terms_in_the_abstract_only_are_flagged_not_excluded():
    """A human-emotion paper may cite animal work in its related work. Excluding
    on an abstract mention would delete valid papers."""
    r = rec("Multimodal emotion recognition with fusion of speech and facial expression",
            "Unlike prior work on cattle welfare, we study human audio-visual affect.")
    s = screen(r)
    assert s.decision == "review"
    assert "non_human_terms_in_abstract" in s.flags


def test_pure_synthesis_with_no_recognition_is_auto_excluded():
    r = rec("Emotional text-to-speech synthesis for multimodal avatars",
            "We generate expressive speech. Audio-visual talking head generation.")
    s = screen(r)
    assert s.decision == "auto-exclude" and s.criterion == "EC3"


def test_synthesis_plus_recognition_is_kept_for_review():
    r = rec("Multimodal emotion recognition with fusion of speech and facial expression",
            "We also compare against emotional TTS baselines and classify affect.")
    s = screen(r)
    assert s.decision == "review"


# ── EC5: non-archival ──────────────────────────────────────

@pytest.mark.parametrize("title", [
    "Erratum: Multimodal emotion recognition",
    "Correction to: Audio-visual fusion for affect",
    "Editorial: the future of affective computing",
    "Front matter",
    "Table of contents",
    "Call for papers: ACII 2026",
])
def test_non_archival_items_are_auto_excluded(title):
    s = screen(rec(title, "multimodal emotion recognition fusion speech facial"))
    assert s.decision == "auto-exclude" and s.criterion == "EC5"


def test_a_real_paper_whose_title_merely_contains_a_stopword_is_not_excluded():
    r = rec("Multimodal emotion recognition: a correction-free fusion of speech and facial cues",
            "audio-visual")
    s = screen(r)
    assert s.decision != "auto-exclude" or s.criterion != "EC5"


# ── the protocol predicate ─────────────────────────────────

def test_a_record_matching_no_search_string_is_excluded_as_off_protocol():
    r = rec("A study of quantum error correction", "Nothing to do with affect.")
    s = screen(r)
    assert s.decision == "auto-exclude" and s.criterion == "SEARCH"


def test_a_citation_found_record_is_not_excluded_for_failing_the_strings():
    """Snowballing is a legitimate second retrieval method (PRISMA 'other
    methods'). Papers found that way were never expected to satisfy a keyword
    string, so failing one is not disqualifying."""
    r = rec("Attention is all you need", "A transformer architecture.")
    r.found_via = ["forward-cite"]
    s = screen(r)
    assert s.decision == "review"
    assert "no_string_match_found_via_citation" in s.flags


# ── advisory flags that shape the human's work ─────────────

def test_a_missing_abstract_is_flagged_and_changes_the_suggestion():
    r = rec("Multimodal emotion recognition with cross-modal attention fusion of speech "
            "and facial expression and audio-visual data", "")
    s = screen(r)
    if s.decision == "review":
        assert "abstract_missing" in s.flags
        assert "full text" in s.suggestion


def test_a_preprint_is_flagged_for_the_IC1_judgement_call():
    r = rec("Multimodal emotion recognition with fusion of speech and facial expression",
            "audio-visual", is_preprint=True)
    s = screen(r)
    assert s.decision == "review"
    assert "preprint_only" in s.flags


def test_every_auto_exclusion_carries_a_criterion_and_a_reason():
    """An exclusion the reviewer cannot audit is an exclusion they cannot
    defend."""
    bad = [rec("Emotion recognition in swine", "multimodal fusion speech facial audio-visual"),
           rec("Erratum: fusion", "multimodal emotion recognition speech facial audio-visual"),
           rec("Multimodal emotion recognition fusion speech facial", "audio-visual", year=1999),
           rec("Quantum cryptography", "unrelated")]
    for r in bad:
        s = screen(r)
        assert s.decision == "auto-exclude"
        assert s.criterion, f"no criterion recorded for {r.title!r}"
        assert s.reason, f"no evidence recorded for {r.title!r}"


# ── batch behaviour ────────────────────────────────────────

def test_screen_all_preserves_merge_provenance():
    m = Merged(record=rec("Multimodal emotion recognition with fusion of speech and "
                          "facial expression", "audio-visual"),
               merged_from=["arxiv:2301.1"], sources=["openalex", "arxiv"])
    out = screen_all([m], SEARCH_STRINGS, YEAR_MIN, YEAR_MAX)
    assert out[0].merged_from == ["arxiv:2301.1"]
    assert out[0].sources == ["openalex", "arxiv"]


# ── screening tiers ────────────────────────────────────────

def _tiered(matched, found_via, decision="review"):
    from slr.pipeline import tier_of
    r = rec("Multimodal emotion recognition with fusion of speech and facial expression",
            "audio-visual")
    r.matched_strings = matched
    r.found_via = found_via
    s = screen_one(r, SEARCH_STRINGS, YEAR_MIN, YEAR_MAX)
    s.decision = decision
    s.record.matched_strings = matched
    s.record.found_via = found_via
    return tier_of(s)


def test_tiers_rank_search_hits_above_citation_only_records():
    assert _tiered(["S1", "S6"], ["search"]) == "T1"
    assert _tiered(["S1"], ["search"]) == "T2"
    assert _tiered(["S1"], ["forward-cite"]) == "T3"
    assert _tiered([], ["forward-cite"]) == "T4"


def test_auto_excluded_records_are_tier_X_and_need_no_screening():
    assert _tiered(["S1"], ["search"], decision="auto-exclude") == "X"


def test_every_tier_has_a_documented_meaning():
    from slr.pipeline import TIERS, tier_of
    for t in ("T1", "T2", "T3", "T4", "X"):
        assert t in TIERS and TIERS[t]
