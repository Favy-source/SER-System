"""
Automated screening — MECHANICAL CRITERIA ONLY.

THE HARD RULE
    This module NEVER produces an "include" decision. It produces exactly two
    outcomes:

        auto-exclude   the record fails a criterion that can be checked without
                       reading it (wrong year, wrong language, an erratum)
        review         everything else, carrying a SUGGESTION and the flags
                       behind it

    Screening is my intellectual contribution and an examiner will
    ask who made each call. A tool that auto-included would make the review
    indefensible, and would also be the single easiest thing for a viva panel to
    attack. So the machine removes only what is mechanically impossible to keep,
    and hands everything else over with its reasoning shown.

    Every auto-exclusion records the criterion code AND the evidence that
    triggered it, so any decision can be audited and overturned by hand.

WHAT IS DELIBERATELY *NOT* AUTOMATED
    IC3 (addresses a Review Question), IC4 (reports empirical results), EC1, and
    EC2 (unimodal with no comparative value) all require judgement about what a
    paper actually does. They are surfaced as suggestions and left open.
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional

from . import booleanq
from .sources.base import Record

# ── mechanical signals ─────────────────────────────────────

# EC3, first clause: non-human affect. These terms in a TITLE are decisive; the
# same words in an abstract are not (a human-emotion paper may mention animal
# studies in its related work), so the title is checked and the abstract only
# contributes a flag.
NON_HUMAN = re.compile(
    r"\b(cattle|dairy cow|bovine|swine|porcine|piglet|poultry|chicken|broiler|"
    r"canine|feline|equine|murine|rodent|mice|mouse|rat|zebrafish|primate|"
    r"macaque|livestock|animal welfare|veterinar)\w*", re.I)

# EC3, second clause: synthesis/generation rather than recognition.
SYNTHESIS_ONLY = re.compile(
    r"\b(speech synthesis|text[- ]to[- ]speech|expressive tts|emotional tts|"
    r"voice conversion|talking head|face generation|face synthesis|"
    r"image generation|avatar generation|facial reenactment)\b", re.I)
RECOGNITION = re.compile(
    r"\b(recogni[sz]|classif|detect|predict|estimat|assess|analys|analyz)\w*", re.I)

# EC5: non-archival or non-research items.
NON_ARCHIVAL = re.compile(
    r"^\s*(erratum|corrigendum|correction to|retraction|editorial|preface|"
    r"foreword|front matter|back matter|table of contents|author index|"
    r"subject index|list of reviewers|call for papers|message from the|"
    r"welcome (message|from)|committee|proceedings of the)\b", re.I)

# IC2's named seminal exceptions — retrieved regardless of the date window.
SEMINAL = re.compile(r"\b(busso|ekman|picard)\b", re.I)


@dataclass
class Screened:
    record: Record
    decision: str                                   # auto-exclude | review
    criterion: str = ""                             # IC2 / IC5 / EC3 / EC5 / SEARCH
    reason: str = ""                                # the evidence, verbatim where possible
    suggestion: str = ""                            # for 'review' rows only
    flags: List[str] = field(default_factory=list)  # advisory, never decisive
    merged_from: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)


def match_strings(rec: Record, strings: List[dict]) -> List[str]:
    """Which protocol search strings does this record actually satisfy?

    The API queries are deliberately broader than the protocol, so this is where
    the protocol is really enforced. Returns the string IDs, e.g. ["S1", "S6"].
    """
    hits = []
    for s in strings:
        try:
            if booleanq.matches(s["string"], rec.title, rec.abstract):
                hits.append(s["id"])
        except ValueError:
            continue        # a malformed string is a protocol bug, not a record bug
    return hits


def screen_one(rec: Record, strings: List[dict],
               year_from: int, year_to: int) -> Screened:
    flags: List[str] = []
    title = rec.title or ""
    haystack = f"{title}\n{rec.abstract or ''}"

    rec.matched_strings = sorted(set(rec.matched_strings) | set(match_strings(rec, strings)))
    found_by_citation = any(v.endswith("-cite") for v in rec.found_via)

    # ── EC5: non-archival item ──
    if NON_ARCHIVAL.match(title):
        return Screened(rec, "auto-exclude", "EC5",
                        f'Non-archival item: title begins "{title[:60]}"')

    # ── IC2: publication window ──
    if rec.year is None:
        flags.append("year_missing")
    elif not (year_from <= rec.year <= year_to):
        if SEMINAL.search(" ".join(rec.authors)):
            flags.append(f"seminal_exception_pre_{year_from}")
        else:
            return Screened(rec, "auto-exclude", "IC2",
                            f"Published {rec.year}, outside {year_from}-{year_to}")

    # ── IC5: English ──
    lang = (rec.language or "").lower()
    if lang and not lang.startswith(("en", "eng")):
        return Screened(rec, "auto-exclude", "IC5",
                        f'Language reported as "{rec.language}"')
    if not lang:
        flags.append("language_unreported")

    # ── EC3: non-human affect ──
    m = NON_HUMAN.search(title)
    if m:
        return Screened(rec, "auto-exclude", "EC3",
                        f'Non-human affect indicated in title: "{m.group(0)}"')
    if NON_HUMAN.search(rec.abstract or ""):
        flags.append("non_human_terms_in_abstract")

    # ── EC3: synthesis without recognition ──
    syn = SYNTHESIS_ONLY.search(haystack)
    if syn and not RECOGNITION.search(haystack):
        return Screened(rec, "auto-exclude", "EC3",
                        f'Generation/synthesis only, no recognition term: "{syn.group(0)}"')
    if syn:
        flags.append("synthesis_terms_present")

    # ── the protocol predicate itself ──
    if not rec.matched_strings:
        if found_by_citation:
            # Legitimately retrieved by a different method (step 3), so failing
            # the string is not disqualifying — but I should know.
            flags.append("no_string_match_found_via_citation")
        else:
            return Screened(rec, "auto-exclude", "SEARCH",
                            "Retrieved by API relevance but satisfies no protocol "
                            "search string on title+abstract")

    # ── advisory flags that shape the suggestion ──
    if not (rec.abstract or "").strip():
        flags.append("abstract_missing")
    if rec.is_preprint:
        flags.append("preprint_only")          # IC1 judgement call
    if rec.venue_type == "":
        flags.append("venue_type_unknown")     # IC1 judgement call
    if not rec.oa_status and not rec.pdf_url:
        flags.append("access_unknown")         # IC5 "full text accessible"

    return Screened(rec, "review", suggestion=_suggest(rec, flags), flags=flags)


def _suggest(rec: Record, flags: List[str]) -> str:
    """A hint for the human screener. Explicitly NOT a decision."""
    if "abstract_missing" in flags:
        return "retrieve full text before deciding — screened on title only"
    if "preprint_only" in flags:
        return "preprint: check for a published version, else judge against IC1"
    if "non_human_terms_in_abstract" in flags or "synthesis_terms_present" in flags:
        return "check EC3 by hand — borderline terms present"
    if len(rec.matched_strings) >= 2:
        return "strong candidate: satisfies multiple protocol strings"
    return "read title+abstract and apply IC3/IC4"


def screen_all(merged, strings: List[dict],
               year_from: int, year_to: int) -> List[Screened]:
    out = []
    for m in merged:
        s = screen_one(m.record, strings, year_from, year_to)
        s.merged_from = m.merged_from
        s.sources = m.sources
        out.append(s)
    return out
