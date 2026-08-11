"""
Tests for the interactive screening harness.

WHAT IS AT STAKE
    This tool writes the reviewer's own judgements — the part of the review that
    is genuinely theirs and that an examiner will probe hardest. Three failure
    modes would each corrupt the thesis:

      losing a decision      days of reading vanish and nobody notices which
      fabricating a decision a record gets an outcome the reviewer never gave
      an unexplained exclusion  PRISMA requires reasons; one written months
                                later is a reconstruction, not a record

    So the tests below check persistence, resumability, and that every exclusion
    carries a code and a reason.
"""
import csv
import io
from pathlib import Path

import pytest

from slr import protocol, screen_cli


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Redirect the module's paths at a temp dir — never touch the real review."""
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setattr(screen_cli, "OUT", out)
    monkeypatch.setattr(screen_cli, "SCREENING", out / "screening.csv")
    monkeypatch.setattr(screen_cli, "DECISIONS", out / "decisions.csv")

    rows = []
    for i in range(1, 6):
        rows.append({
            "id": f"R{i:04d}", "tier": "T1", "decision": "review",
            "criterion": "", "reason": "", "suggestion": "", "flags": "",
            "title": f"Multimodal emotion recognition paper {i}",
            "authors": "A Author; B Author", "year": str(2020 + i),
            "venue": "Journal", "venue_type": "journal", "doi": f"10.1/{i}",
            "oa_status": "gold", "pdf_url": "", "cited_by": str(100 - i),
            "sources": "openalex", "merged_from": "", "matched_strings": "S1; S2",
            "found_via": "search", "abstract": f"Abstract number {i}.",
            "my_TA_decision": "", "my_TA_reason": "", "my_fulltext_decision": "",
            "my_EC_code": "", "notes": "",
        })
    with (out / "screening.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return out


def drive(monkeypatch, keys):
    """Feed keystrokes to the loop's input()."""
    it = iter(keys)
    monkeypatch.setattr(screen_cli, "ask", lambda prompt: next(it, "q"))


def decisions(out):
    p = out / "decisions.csv"
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ── persistence ────────────────────────────────────────────

def test_an_include_is_written_with_its_note(workspace, monkeypatch, capsys):
    drive(monkeypatch, ["i", "matters for ReQ2", "q"])
    screen_cli.run()
    rows = decisions(workspace)
    assert len(rows) == 1
    assert rows[0]["decision"] == "include"
    assert rows[0]["note"] == "matters for ReQ2"
    assert rows[0]["id"] == "R0001"
    assert rows[0]["decided_at"], "a decision with no timestamp is not auditable"


def test_an_exclusion_records_a_code_and_a_reason(workspace, monkeypatch, capsys):
    drive(monkeypatch, ["e", "EC2", "unimodal, no comparative value", "q"])
    screen_cli.run()
    rows = decisions(workspace)
    assert rows[0]["decision"] == "exclude"
    assert rows[0]["ec_code"] == "EC2"
    assert rows[0]["reason"] == "unimodal, no comparative value"


def test_an_invalid_exclusion_code_is_rejected_until_valid(workspace, monkeypatch, capsys):
    drive(monkeypatch, ["e", "NONSENSE", "EC3", "non-human affect", "q"])
    screen_cli.run()
    rows = decisions(workspace)
    assert len(rows) == 1
    assert rows[0]["ec_code"] == "EC3", "a code outside the protocol must not be stored"


def test_an_empty_exclusion_reason_is_refused(workspace, monkeypatch, capsys):
    """PRISMA reports exclusion reasons. A blank one is not a reason."""
    drive(monkeypatch, ["e", "EC1", "", "", "no empirical evaluation", "q"])
    screen_cli.run()
    rows = decisions(workspace)
    assert rows[0]["reason"] == "no empirical evaluation"


def test_maybe_captures_what_would_settle_it(workspace, monkeypatch, capsys):
    drive(monkeypatch, ["m", "need the full text", "q"])
    screen_cli.run()
    assert decisions(workspace)[0]["decision"] == "maybe"
    assert decisions(workspace)[0]["note"] == "need the full text"


# ── resumability ───────────────────────────────────────────

def test_a_skipped_record_records_no_decision(workspace, monkeypatch, capsys):
    drive(monkeypatch, ["s", "q"])
    screen_cli.run()
    assert decisions(workspace) == [], "skip must not invent an outcome"


def test_resuming_does_not_re_present_decided_records(workspace, monkeypatch, capsys):
    drive(monkeypatch, ["i", "", "i", "", "q"])
    screen_cli.run()
    assert len(decisions(workspace)) == 2

    drive(monkeypatch, ["i", "", "q"])
    screen_cli.run()
    rows = decisions(workspace)
    assert len(rows) == 3
    assert [r["id"] for r in rows] == ["R0001", "R0002", "R0003"], \
        "resume must continue past what was already decided, not redo it"


def test_decisions_survive_quitting_mid_sitting(workspace, monkeypatch, capsys):
    """Days of reading must not depend on finishing the queue."""
    drive(monkeypatch, ["i", "kept", "q"])
    screen_cli.run()
    assert (workspace / "decisions.csv").exists()
    assert decisions(workspace)[0]["note"] == "kept"


def test_quitting_immediately_writes_nothing(workspace, monkeypatch, capsys):
    drive(monkeypatch, ["q"])
    screen_cli.run()
    assert decisions(workspace) == []


# ── the tool must not decide ───────────────────────────────

def test_no_decision_is_ever_recorded_without_a_keystroke(workspace, monkeypatch, capsys):
    """Every stored row must trace to something the reviewer typed."""
    drive(monkeypatch, ["s", "s", "s", "s", "s", "q"])
    screen_cli.run()
    assert decisions(workspace) == []


def test_unrecognised_input_does_not_record_anything(workspace, monkeypatch, capsys):
    drive(monkeypatch, ["x", "zzz", "q"])
    screen_cli.run()
    assert decisions(workspace) == []


def test_every_exclusion_code_offered_is_a_real_protocol_code(workspace):
    for code in protocol.EXCLUSION:
        assert code.startswith("EC")


# ── ordering ───────────────────────────────────────────────

def test_records_are_presented_highest_tier_and_most_cited_first(workspace, monkeypatch, capsys):
    drive(monkeypatch, ["i", "", "q"])
    screen_cli.run()
    # R0001 has cited_by 99, the highest in the fixture.
    assert decisions(workspace)[0]["id"] == "R0001"


def test_tier_filter_restricts_the_queue(workspace, monkeypatch, capsys):
    drive(monkeypatch, ["i", "", "q"])
    screen_cli.run({"T4"})          # fixture has no T4 records
    assert decisions(workspace) == []
