"""
Tests for the Boolean predicate that defines the review corpus.

WHY THESE MATTER MORE THAN THEY LOOK
    matches() is the only thing standing between "everything the API felt like
    returning" and "the corpus the protocol actually specifies". If it silently
    over-matches, the review includes papers it cannot justify; if it silently
    under-matches, the review MISSES papers and no one will ever know, because
    absence leaves no trace in the output.

    So each protocol string gets both a positive fixture and a NEAR-MISS fixture
    that must fail — a paper that looks right but breaks exactly one clause.
"""
import re

import pytest

from slr import booleanq, protocol

S = {s["id"]: s["string"] for s in protocol.SEARCH_STRINGS}


# ── parser ─────────────────────────────────────────────────

def test_precedence_not_binds_tighter_than_and_than_or():
    ast = booleanq.parse('a OR b AND c')
    assert isinstance(ast, booleanq.Or)
    assert isinstance(ast.children[1], booleanq.And)


def test_parentheses_override_precedence():
    ast = booleanq.parse('(a OR b) AND c')
    assert isinstance(ast, booleanq.And)


def test_adjacent_terms_are_an_implicit_and():
    assert booleanq.matches('"emotion recognition" multimodal',
                            "Multimodal emotion recognition", "")
    assert not booleanq.matches('"emotion recognition" multimodal',
                                "Emotion recognition from speech", "")


def test_phrase_matches_across_hyphen_and_space():
    q = '"audio-visual"'
    for variant in ["Audio-visual fusion", "audio visual fusion"]:
        assert booleanq.matches(q, variant, ""), variant


def test_word_boundaries_are_respected():
    # "fusion" must not be matched by "confusion" — this is the single most
    # likely source of silent false positives in the whole review.
    assert not booleanq.matches("fusion", "A confusion matrix analysis", "")
    assert booleanq.matches("fusion", "Late fusion of modalities", "")


def test_wildcard_is_a_prefix_match_not_a_substring_match():
    assert booleanq.matches("robust*", "Robustness of the model", "")
    assert booleanq.matches("robust*", "A robust approach", "")
    assert not booleanq.matches("robust*", "The arobust approach", "")


def test_not_excludes():
    q = '"emotion recognition" AND NOT cattle'
    assert booleanq.matches(q, "Emotion recognition in humans", "")
    assert not booleanq.matches(q, "Emotion recognition in cattle", "")


def test_abstract_is_searched_as_well_as_title():
    assert booleanq.matches('"missing modality"', "A fusion method",
                            "We handle the missing modality case.")


def test_malformed_query_raises_rather_than_silently_matching_nothing():
    with pytest.raises(ValueError):
        booleanq.parse("(unbalanced AND paren")


# ── every protocol string parses ───────────────────────────

@pytest.mark.parametrize("sid", list(S))
def test_every_protocol_string_parses(sid):
    ast = booleanq.parse(S[sid])
    assert booleanq.terms(ast), f"{sid} produced no terms"


# ── positives and near-misses, per string ──────────────────

POSITIVE = {
    "S1": ("Multimodal emotion recognition with cross-modal attention",
           "We propose a transformer for audio-visual fusion of speech and facial cues."),
    "S2": ("Robust multimodal emotion recognition under missing modality",
           "We evaluate affect recognition with occlusion and noise."),
    "S3": ("Efficient speech emotion recognition on the edge",
           "Quantization and knowledge distillation give real-time inference on a Raspberry Pi."),
    "S4": ("Affective computing for dementia caregiving",
           "A clinical deployment study of emotion recognition with privacy-by-design and consent."),
    "S5": ("Multimodal emotion recognition with modality dropout",
           "We address the missing modality problem."),
    "S6": ("Joint speech emotion recognition and facial expression recognition",
           "A two-stream model."),
    "S8": ("On the ecological validity of emotion recognition benchmarks",
           "We compare acted and spontaneous corpora and show dataset bias."),
    "S9": ("Speaker-independent evaluation of speech emotion recognition",
           "We report unweighted average recall under leave-one-speaker-out."),
}

# Each near-miss breaks exactly ONE clause of its string and must be rejected.
NEAR_MISS = {
    "S1": ("Speech emotion recognition with a CNN",
           "A unimodal audio model. No fusion of any kind.",
           "no multimodal clause"),
    "S2": ("Multimodal emotion recognition with attention",
           "We report accuracy on IEMOCAP.",
           "no robustness clause"),
    "S3": ("Speech emotion recognition with a transformer",
           "We report accuracy on RAVDESS.",
           "no compression or deployment clause"),
    "S4": ("Emotion recognition for video retrieval",
           "We index consumer video.",
           "no healthcare clause"),
    "S5": ("Multimodal emotion recognition with tensor fusion",
           "All modalities are present.",
           "no missing-modality clause"),
    "S6": ("Speech emotion recognition with spectrograms",
           "Audio only.",
           "no facial expression recognition"),
    "S8": ("Emotion recognition with a new architecture",
           "We beat the state of the art.",
           "no dataset-validity clause"),
    "S9": ("Emotion recognition with a deep network",
           "We report accuracy on a random split.",
           "no evaluation-protocol clause"),
}


@pytest.mark.parametrize("sid", sorted(POSITIVE))
def test_positive_fixture_matches(sid):
    title, abstract = POSITIVE[sid]
    assert booleanq.matches(S[sid], title, abstract), \
        f"{sid} failed to match a paper it must include"


@pytest.mark.parametrize("sid", sorted(NEAR_MISS))
def test_near_miss_is_rejected(sid):
    title, abstract, why = NEAR_MISS[sid]
    assert not booleanq.matches(S[sid], title, abstract), \
        f"{sid} wrongly matched a near-miss ({why}) — the string is too loose"


# ── wildcard coverage ──────────────────────────────────────

def test_every_wildcard_in_the_protocol_has_an_explicit_expansion():
    """OpenAlex and arXiv have no truncation operator, so an unexpanded stem
    becomes a term that matches NOTHING — silently deleting an alternative from
    the protocol. This test fails the moment a new wildcard is added to a search
    string without a matching expansion entry."""
    used = set()
    for s in protocol.SEARCH_STRINGS:
        used |= {m.lower() for m in re.findall(r"\b(\w+)\*", s["string"])}
    missing = used - set(booleanq.WILDCARD_EXPANSIONS)
    assert not missing, f"wildcard stems with no expansion: {sorted(missing)}"


def test_wildcard_expansions_actually_start_with_their_stem():
    for stem, forms in booleanq.WILDCARD_EXPANSIONS.items():
        for f in forms:
            assert f.lower().startswith(stem), f"{f!r} is not a form of {stem!r}"


# ── per-API translations ───────────────────────────────────

@pytest.mark.parametrize("sid", list(S))
def test_openalex_translation_is_balanced_and_expands_wildcards(sid):
    q = booleanq.to_openalex(S[sid])
    assert q.count("(") == q.count(")"), f"{sid}: unbalanced parentheses"
    assert "*" not in q, f"{sid}: OpenAlex has no wildcard operator"


@pytest.mark.parametrize("sid", list(S))
def test_pubmed_translation_tags_every_term_with_tiab(sid):
    q = booleanq.to_pubmed(S[sid])
    assert q.count("(") == q.count(")")
    # Every leaf term must carry a field tag, or PubMed silently searches all
    # fields including author and affiliation, which would wreck precision.
    n_terms = len(booleanq.terms(booleanq.parse(S[sid])))
    assert q.count("[tiab]") == n_terms


@pytest.mark.parametrize("sid", list(S))
def test_arxiv_translation_decomposes_phrases_into_words(sid):
    q = booleanq.to_arxiv(S[sid])
    assert q.count("(") == q.count(")")
    assert "*" not in q
    # Phrase quoting is what loses ~99% of arXiv hits; assert we never emit it.
    assert '"' not in q, f"{sid}: quoted phrase leaked into an arXiv query"
    assert "all:" in q


def test_arxiv_phrase_decomposition_drops_stopwords():
    q = booleanq.to_arxiv('"in-the-wild"')
    assert "all:the" not in q and "all:in" not in q
    assert "all:wild" in q


def test_crossref_query_is_a_bag_of_words_not_a_boolean():
    q = booleanq.api_query(S["S1"])
    assert "AND" not in q and "OR" not in q and "(" not in q


# ── performance contract ───────────────────────────────────

def test_parse_is_memoised():
    """Screening evaluates every record against every string. An un-cached parse
    meant ~316,000 regex compilations for a 1,757-record corpus and turned the
    screening pass into a run that outlived a 15-minute timeout."""
    booleanq._parse_cached.cache_clear()
    q = S["S1"]
    for _ in range(50):
        booleanq.matches(q, "Multimodal emotion recognition", "audio-visual fusion")
    info = booleanq._parse_cached.cache_info()
    assert info.misses == 1, "the string should be parsed exactly once"
    assert info.hits == 49


def test_screening_a_realistic_corpus_stays_fast():
    """A guard on the whole predicate path, not just the parser."""
    import time
    titles = ["Multimodal emotion recognition with cross-modal attention"] * 400
    abstract = "We fuse speech and facial expression features and report latency. " * 6
    t0 = time.time()
    for t in titles:
        for s in protocol.SEARCH_STRINGS:
            booleanq.matches(s["string"], t, abstract)
    elapsed = time.time() - t0
    assert elapsed < 5.0, f"400 records x {len(protocol.SEARCH_STRINGS)} strings took {elapsed:.1f}s"


def test_cached_asts_are_not_mutated_by_evaluation():
    """Memoisation is only safe because matching never mutates the AST."""
    a = booleanq.parse(S["S6"])
    b = booleanq.parse(S["S6"])
    assert a is b, "same string should yield the same cached AST"
    before = repr(a)
    booleanq.matches(S["S6"], "Speech emotion recognition", "facial expression recognition")
    assert repr(a) == before
