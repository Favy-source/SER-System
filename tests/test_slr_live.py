"""
Live API contract tests.   pytest -m network

WHY THESE EXIST, IN THIS PROJECT SPECIFICALLY
    Three separate bugs in this codebase shared one shape: a test constructed
    its own inputs, so it verified the CONSUMER but never the producer-consumer
    contract. Mocked tests passed while the real thing was broken —
    `mp.solutions` had been deleted from MediaPipe, uvicorn had no WebSocket
    implementation, and a visual window was read before it was refreshed.

    Every test above this file builds its own Record objects. So every one of
    them would still pass if OpenAlex renamed `abstract_inverted_index`
    tomorrow, or if arXiv changed its Atom namespace. These tests are the ones
    that would fail — and the SLR's whole evidence base depends on the four
    adapters actually parsing what the four APIs actually send.

    They are marked `network` so the offline suite stays fast, and they use the
    disk cache, so after the first run they cost nothing.
"""
import pytest

from slr import booleanq, citations, protocol
from slr.dedupe import deduplicate
from slr.sources import arxiv, crossref, openalex
from slr.sources import pubmed as pubmed_src

pytestmark = pytest.mark.network

Y0, Y1 = protocol.YEAR_MIN, protocol.YEAR_MAX


# ── each adapter parses what its API actually returns ──────

def test_openalex_returns_populated_records():
    got = list(openalex.search(booleanq.to_openalex(
        '"speech emotion recognition" AND "facial expression recognition"'),
        Y0, Y1, max_records=25))
    assert got, "OpenAlex returned nothing for a query known to have hits"
    assert all(r.title for r in got), "a record with no title cannot be screened"
    assert sum(1 for r in got if r.year) >= len(got) * 0.9
    # Abstract reconstruction is the single most fragile piece of parsing in the
    # toolkit: it depends on an undocumented inverted-index format.
    with_abs = [r for r in got if r.abstract]
    assert with_abs, "no abstracts reconstructed — the inverted index format changed"
    assert any(len(r.abstract.split()) > 30 for r in with_abs), \
        "abstracts reconstructed but implausibly short"
    assert any(r.doi for r in got)


def test_openalex_abstract_reconstruction_produces_real_prose():
    r = openalex.by_doi("10.1609/aaai.v34i02.5492")     # M3ER
    assert r is not None and r.abstract
    words = r.abstract.lower().split()
    assert len(words) > 50
    # Word order must be right, not just the bag of words.
    assert "emotion" in words or "emotions" in words


def test_crossref_returns_populated_records():
    got = list(crossref.search("speech emotion recognition facial expression",
                               Y0, Y1, max_records=25))
    assert got
    assert all(r.title for r in got)
    assert all(r.doi for r in got), "Crossref is the DOI authority; a DOI is mandatory"


def test_pubmed_two_step_esearch_efetch_round_trip():
    q = booleanq.to_pubmed('("emotion recognition") AND (multimodal)')
    ids = pubmed_src.esearch(q, Y0, Y1, max_records=15)
    assert ids, "esearch returned no PMIDs"
    got = list(pubmed_src.efetch(ids))
    assert got, "efetch parsed nothing from the XML NCBI returned"
    assert all(r.title for r in got)
    assert any(r.abstract for r in got)
    assert any(r.doi for r in got)
    assert all(r.year for r in got), "PubMed date parsing failed"


def test_arxiv_atom_parsing():
    got = list(arxiv.search(booleanq.to_arxiv('"speech emotion recognition"'),
                            Y0, Y1, max_records=20))
    assert got, "arXiv Atom feed parsed to nothing"
    assert all(r.title and r.abstract for r in got), \
        "arXiv always supplies both a title and a summary"
    assert all(r.year for r in got)
    assert all(r.source_id for r in got)


def test_arxiv_word_decomposition_beats_phrase_quoting():
    """The measured defect that justified the design: quoted phrases lose ~99%
    of arXiv hits. If arXiv ever fixes its tokenizer this test will start
    failing, which is the signal to simplify to_arxiv()."""
    phrase = arxiv.count('all:"speech emotion recognition" AND '
                         'all:"facial expression recognition"', Y0, Y1)
    words = arxiv.count(booleanq.to_arxiv(
        '"speech emotion recognition" AND "facial expression recognition"'), Y0, Y1)
    assert words > phrase * 10, \
        f"word decomposition ({words}) should vastly out-recall phrases ({phrase})"


# ── the dedupe anchor, end to end against live data ────────

def test_the_zenodo_version_pair_merges_using_live_records():
    a = openalex.by_doi("10.5281/zenodo.18594074")
    b = openalex.by_doi("10.5281/zenodo.18594073")
    if a is None or b is None:
        pytest.skip("Zenodo anchor records not currently in OpenAlex")
    assert a.source_id != b.source_id and a.norm_doi() != b.norm_doi(), \
        "the anchor is only meaningful if the two records really are distinct rows"
    merged, removed = deduplicate([a, b])
    assert removed == 1 and len(merged) == 1


# ── citation traversal ─────────────────────────────────────

def test_openalex_splits_M3ER_across_records_and_siblings_finds_them_all():
    """Threat T9, asserted rather than assumed.

    If OpenAlex ever merges these records this test will fail, which is the
    signal that the sibling fan-out is no longer needed — not a regression.
    """
    doi_record = openalex.by_doi("10.1609/aaai.v34i02.5492")
    assert doi_record is not None
    sibs = openalex.siblings(doi_record)
    assert len(sibs) > 1, "expected M3ER to exist as several OpenAlex records"
    best = max(s.cited_by_count for s in sibs)
    assert best > doi_record.cited_by_count * 5, (
        f"the DOI record reports {doi_record.cited_by_count} citations but a sibling "
        f"reports {best} — this gap is exactly what T9 documents")


def test_forward_citation_from_M3ER_surfaces_known_responders():
    """Method step 3: a gap is pinned by finding who responded to it.

    M3ER's forward citations must include the papers the teaching document names
    as responders. If they do not, the traversal is broken and every type-(b)
    gap claim in the review rests on nothing.
    """
    seed, citing = citations.forward("10.1609/aaai.v34i02.5492", Y0, Y1, max_records=400)
    assert seed is not None, "M3ER did not resolve in OpenAlex"
    # Must reflect the fullest sibling record, not the sparse DOI one (T9).
    assert seed.cited_by_count > 100, \
        f"seed reports only {seed.cited_by_count} citations — sibling fan-out failed"
    assert len(citing) > 100, f"only {len(citing)} forward citations found"

    titles = " || ".join(r.title.lower() for r in citing)
    # The missing-modality sub-literature (ReQ6, string S5) is the clearest
    # type-(b) responder cluster, so at least one must surface. Matched on stems
    # because the real titles say "Missing Modalities" and "Incomplete Modality",
    # not the singular forms S5 happens to use.
    assert any(k in titles for k in ("missing modalit", "incomplete modalit",
                                     "incomplete multimodal", "modality dropout",
                                     "absent modalit")), \
        "no missing-modality responder found — forward traversal looks broken"
    assert all(r.found_via == ["forward-cite"] for r in citing)


def test_backward_citation_returns_the_seeds_in_window_references():
    """Backward snowballing from a 2020 seed mostly yields PRE-window work.

    M3ER's first 12 references are from 1995-2013 and are all correctly dropped
    by IC2. The cap must therefore cover the full reference list, or backward
    traversal returns nothing and looks broken when it is merely mis-called.
    """
    seed, _ = citations.forward("10.1609/aaai.v34i02.5492", Y0, Y1, max_records=1)
    assert seed and seed.referenced_works, "OpenAlex returned no referenced_works"
    refs = citations.backward(seed, Y0, Y1, max_records=len(seed.referenced_works))
    assert refs, "backward traversal returned nothing across the full reference list"
    assert all(r.found_via == ["backward-cite"] for r in refs)
    assert all(Y0 <= r.year <= Y1 for r in refs), "IC2 window not applied"
    assert len(refs) < len(seed.referenced_works), \
        "expected some references to fall outside the window"


@pytest.mark.parametrize("doi,label", protocol.SNOWBALL_SEEDS)
def test_every_snowball_seed_resolves(doi, label):
    """A seed that does not resolve is a silent hole in the citation analysis."""
    assert openalex.by_doi(doi) is not None, f"seed did not resolve: {label} ({doi})"


# ── recall anchor ──────────────────────────────────────────

# If the protocol's own strings cannot retrieve the papers the proposal already
# cites, the strings are too narrow and the search is not fit for purpose. This
# is the review's calibration check, and it is the test most likely to catch a
# genuinely bad protocol edit.
KNOWN_WORKS = [
    ("10.3390/s23125475",        "Mamieva 2023 — attention fusion, speech+face"),
    ("10.3390/s21144913",        "Xie 2021 — transformer cross-modality fusion"),
    ("10.3390/e25101440",        "Lian 2023 — survey of multimodal ER"),
    ("10.18653/v1/P19-1656",     "Tsai 2019 — MulT"),
    ("10.1609/aaai.v34i02.5492", "Mittal 2020 — M3ER"),
]


@pytest.mark.parametrize("doi,label", KNOWN_WORKS)
def test_known_relevant_work_satisfies_at_least_one_protocol_string(doi, label):
    r = openalex.by_doi(doi)
    if r is None:
        pytest.skip(f"{label} not resolvable")
    hits = [s["id"] for s in protocol.SEARCH_STRINGS
            if booleanq.matches(s["string"], r.title, r.abstract)]
    assert hits, (f"{label} satisfies NO protocol search string — the strings are "
                  f"too narrow.\n  title: {r.title}\n  abstract: {r.abstract[:200]}")


def test_arxiv_pagination_does_not_stop_short_of_total_results():
    """Regression: an empty page mid-result-set used to end pagination.

    Two pipeline runs differed by ~2,000 records with no errors logged because
    arXiv served transient empty pages and the loop accepted them as the end.
    Retrieval that silently under-collects leaves no trace in the output, which
    makes it the worst possible failure mode for a systematic review.
    """
    from slr.sources.base import SourceError
    q = booleanq.to_arxiv('"speech emotion recognition"')
    try:
        total = arxiv.count(q, Y0, Y1)
        got = list(arxiv.search(q, Y0, Y1, max_records=250))
    except SourceError as e:
        # A 429 means the test could not RUN, which is not the same as passing.
        # Skipping says so out loud rather than reporting a green tick.
        if "429" in str(e):
            pytest.skip(f"arXiv rate-limited this run, test not executed: {e}")
        raise
    assert total > 250, "need a multi-page result set to exercise pagination"
    assert len(got) >= 250, \
        f"pagination stopped at {len(got)} of an available {total}"
    assert len({r.source_id for r in got}) == len(got), "paged records repeated"
