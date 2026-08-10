"""
Tests for duplicate detection and merging.

WHY THE STAKES ARE HIGH
    "Records removed before screening: duplicates" is a number that goes into
    the PRISMA flow diagram and into the thesis. Two failure modes, both bad:

      UNDER-merging  inflates the corpus and double-counts a paper's evidence in
                     the synthesis — the same finding appears to be replicated
                     when it is one study seen four times.
      OVER-merging   silently DELETES a distinct paper. Nothing in the output
                     records that it happened.

    Over-merging is the more dangerous one because it is invisible, so the tests
    below spend most of their effort on collision cases that must NOT merge.
"""
import pytest

from slr.dedupe import deduplicate
from slr.sources.base import Record


def rec(source, sid, title, year=2023, doi="", preprint=False, abstract="", **kw):
    return Record(source=source, source_id=sid, title=title, year=year,
                  doi=doi, is_preprint=preprint, abstract=abstract, **kw)


# ── pass 1: DOI ────────────────────────────────────────────

def test_same_doi_across_sources_merges():
    recs = [
        rec("openalex", "W1", "Multimodal Emotion Recognition", doi="10.1109/tac.2023.1234"),
        rec("crossref", "C1", "Multimodal emotion recognition", doi="10.1109/TAC.2023.1234"),
        rec("pubmed", "P1", "Multimodal emotion recognition", doi="https://doi.org/10.1109/tac.2023.1234"),
    ]
    merged, removed = deduplicate(recs)
    assert len(merged) == 1
    assert removed == 2
    assert sorted(merged[0].sources) == ["crossref", "openalex", "pubmed"]


def test_doi_normalisation_handles_case_and_url_prefix():
    recs = [rec("openalex", "W1", "A", doi="10.1/ABC"),
            rec("crossref", "C1", "B", doi="https://dx.doi.org/10.1/abc")]
    merged, removed = deduplicate(recs)
    assert removed == 1


# ── pass 2: title + year ───────────────────────────────────

def test_the_real_zenodo_pair_merges_to_one_row():
    """Anchor case, taken from the live pilot.

    Zenodo mints a separate DOI per version, so 10.5281/zenodo.18594074 and
    ...073 are the SAME work with different DOIs and different OpenAlex IDs.
    DOI matching cannot catch this; only title+year can. If this test fails the
    duplicate count in the PRISMA diagram is wrong.
    """
    recs = [
        rec("openalex", "W7128476701", "Multimodal emotion recognition for edge devices",
            year=2026, doi="10.5281/zenodo.18594074"),
        rec("openalex", "W7128505963", "Multimodal emotion recognition for edge devices",
            year=2026, doi="10.5281/zenodo.18594073"),
    ]
    merged, removed = deduplicate(recs)
    assert len(merged) == 1, "the Zenodo version pair must collapse to one work"
    assert removed == 1


def test_preprint_and_published_version_merge_across_a_year_boundary():
    recs = [
        rec("arxiv", "1906.00295", "Multimodal Transformer for Unaligned Multimodal "
            "Language Sequences", year=2019, preprint=True),
        rec("openalex", "W2", "Multimodal Transformer for Unaligned Multimodal "
            "Language Sequences", year=2020, doi="10.18653/v1/p19-1656"),
    ]
    merged, removed = deduplicate(recs)
    assert removed == 1
    # EC4: the peer-reviewed version survives.
    assert merged[0].record.source == "openalex"
    assert merged[0].record.is_preprint is False
    assert merged[0].record.doi == "10.18653/v1/p19-1656"


def test_title_matching_ignores_case_punctuation_and_accents():
    recs = [rec("openalex", "W1", "Emotion Recognition: A Survey of Méthods"),
            rec("crossref", "C1", "emotion recognition - a survey of methods")]
    merged, removed = deduplicate(recs)
    assert removed == 1


# ── the dangerous direction: must NOT merge ────────────────

def test_same_title_but_years_far_apart_do_not_merge():
    """Generic titles genuinely recur. A 2016 and a 2023 paper both called
    'Speech Emotion Recognition Using Deep Learning' are different papers."""
    recs = [rec("openalex", "W1", "Speech Emotion Recognition Using Deep Learning", year=2016),
            rec("openalex", "W2", "Speech Emotion Recognition Using Deep Learning", year=2023)]
    merged, removed = deduplicate(recs)
    assert len(merged) == 2, "papers seven years apart must not be merged"
    assert removed == 0


def test_different_dois_and_different_titles_do_not_merge():
    recs = [rec("openalex", "W1", "Cross-modal attention for emotion recognition",
                doi="10.1/a"),
            rec("openalex", "W2", "Tensor fusion for sentiment analysis", doi="10.1/b")]
    merged, removed = deduplicate(recs)
    assert len(merged) == 2 and removed == 0


def test_very_short_titles_are_not_merged_on_title_alone():
    recs = [rec("openalex", "W1", "Emotion AI", year=2023),
            rec("crossref", "C1", "Emotion AI", year=2023)]
    merged, _ = deduplicate(recs)
    assert len(merged) == 2, "titles under 12 chars are too collision-prone to merge"


# ── merging must not lose information ──────────────────────

def test_merge_takes_the_best_of_every_field():
    title = "Cross-modal attention for multimodal affect"
    a = rec("openalex", "W1", title, doi="", abstract="short")
    a.oa_status = "gold"
    a.matched_strings = ["S1"]
    a.cited_by_count = 40

    b = rec("crossref", "C1", title, doi="10.1/found-here",
            abstract="a considerably longer abstract with more detail")
    b.pdf_url = "http://example.org/p.pdf"
    b.matched_strings = ["S6"]
    b.cited_by_count = 55

    merged, _ = deduplicate([a, b])
    r = merged[0].record
    assert r.doi == "10.1/found-here", "DOI from the record that had one"
    assert r.abstract.startswith("a considerably longer"), "longest abstract wins"
    assert r.oa_status == "gold", "OA status must survive the merge"
    assert r.pdf_url.endswith("p.pdf"), "the only readable PDF must survive"
    assert r.matched_strings == ["S1", "S6"], "matched strings union, not overwrite"
    assert r.cited_by_count == 55


def test_merged_identifiers_are_recorded_not_discarded():
    recs = [rec("openalex", "W1", "A paper about late fusion", doi="10.1/x"),
            rec("arxiv", "2301.00001", "A paper about late fusion", doi="10.1/x", preprint=True)]
    merged, _ = deduplicate(recs)
    assert "arxiv:2301.00001" in merged[0].merged_from, \
        "the absorbed record's identifier must remain auditable"


def test_a_record_seen_by_search_and_by_citation_keeps_both_provenances():
    a = rec("openalex", "W1", "Cross-modal attention networks", doi="10.1/x")
    a.found_via = ["search"]
    b = rec("openalex", "W1", "Cross-modal attention networks", doi="10.1/x")
    b.found_via = ["forward-cite"]
    merged, _ = deduplicate([a, b])
    assert merged[0].record.found_via == ["forward-cite", "search"]


def test_record_with_no_year_can_still_merge_into_a_titled_one():
    recs = [rec("openalex", "W1", "Emotion recognition on embedded devices", year=2022),
            rec("crossref", "C1", "Emotion recognition on embedded devices", year=None)]
    merged, removed = deduplicate(recs)
    assert removed == 1
    assert merged[0].record.year == 2022, "the known year must survive"


# ── counting ───────────────────────────────────────────────

def test_removed_count_always_reconciles_with_the_output_length():
    """PRISMA requires identified - duplicates = screened. If this ever drifts,
    the flow diagram silently stops adding up."""
    recs = [rec("openalex", f"W{i}", f"Paper number {i} about affect", year=2020 + i % 5)
            for i in range(20)]
    recs += [rec("crossref", "C1", "Paper number 3 about affect", year=2023)]
    merged, removed = deduplicate(recs)
    assert len(recs) - removed == len(merged)


def test_empty_input_is_safe():
    merged, removed = deduplicate([])
    assert merged == [] and removed == 0
