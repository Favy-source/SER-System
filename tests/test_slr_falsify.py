"""
Tests for the conjunction-ladder falsification test.

THE ERROR THIS FILE GUARDS AGAINST
    Presenting an absence of evidence as evidence of absence.

    The first version of this module printed "the query works when relaxed, so
    the zero reflects the literature" on a ladder where EVERY rung returned zero
    — i.e. where the query had demonstrably not been shown to work at all. That
    output would have gone straight into a thesis as support for a scope gap it
    did not support. These tests exist so it cannot happen again.
"""
import pytest

from slr import booleanq
from slr.falsify import ladder
from slr.sources.base import Record


def paper(title, abstract=""):
    return Record(source="t", source_id=title[:8], title=title, abstract=abstract)


Q = '(alpha) AND (beta) AND (gamma) AND (delta)'


def test_a_ladder_where_everything_is_zero_is_marked_uninformative():
    """The load-bearing test. An all-zero ladder proves nothing."""
    pool = [paper("completely unrelated text"), paper("nothing here either")]
    r = ladder(booleanq.parse(Q), pool)
    assert r["full_conjunction"]["count"] == 0
    assert r["informative"] is False, \
        "an all-zero ladder must never be reported as informative"
    assert r["binding_clause"] is None, \
        "there is no binding clause when nothing is ever released"


def test_a_ladder_that_releases_papers_is_informative_and_names_the_binder():
    # Three papers have alpha+beta+gamma but no delta.
    pool = [paper(f"alpha beta gamma paper {i}") for i in range(3)]
    pool.append(paper("unrelated"))
    r = ladder(booleanq.parse(Q), pool)
    assert r["full_conjunction"]["count"] == 0
    assert r["informative"] is True
    assert r["binding_clause"]["clause"] == "delta"
    assert r["binding_clause"]["papers_released"] == 3


def test_a_satisfied_conjunction_reports_its_survivors_for_reading():
    """A non-zero full conjunction FALSIFIES the scope gap, so the survivors must
    be surfaced — one real counter-example outweighs any count."""
    pool = [paper("alpha beta gamma delta all present")]
    r = ladder(booleanq.parse(Q), pool)
    assert r["full_conjunction"]["count"] == 1
    assert r["full_conjunction"]["survivors"][0]["title"].startswith("alpha")


def test_auto_depth_stops_at_the_shallowest_rung_that_releases_something():
    # Needs two clauses dropped before anything survives.
    pool = [paper("alpha beta only")]
    r = ladder(booleanq.parse(Q), pool)
    assert r["informative"] is True
    assert r["depth_reached"] == 2, "should stop as soon as a rung is non-zero"


def test_binding_clause_requires_papers_to_actually_be_released():
    pool = [paper("nothing relevant")]
    r = ladder(booleanq.parse(Q), pool)
    assert r["binding_clause"] is None


def test_every_rung_records_which_clauses_were_dropped():
    pool = [paper("alpha beta gamma")]
    r = ladder(booleanq.parse(Q), pool)
    for rung in r["rungs"]:
        assert rung["dropped"], "a rung with no dropped clauses is the full query"
        assert rung["n_clauses"] == 4 - len(rung["dropped"])
