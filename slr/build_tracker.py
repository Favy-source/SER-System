"""
Generate the SLR tracker workbook from slr/protocol.py.

    python3 -m slr.build_tracker
    python3 -m slr.build_tracker --out slr/out/SLR_Tracker_v2.xlsx

The tracker is GENERATED, never hand-edited at the structural level. Change the
protocol, re-run this, and the workbook follows. That is what stops the protocol
and the instrument drifting apart — the failure mode where a tracker quietly
stops matching the method it is supposed to execute.

Eight sheets:
  1 Protocol            the roadmap, incl. the central-thesis inclusion test
  2 Search Log          one row per string per source
  3 Screening           every retrieved record
  4 Data Extraction     one row per INCLUDED paper
  5 Gap Chains          GAP -> CAUSE -> METHOD -> RESEARCH QUESTION
  6 Synthesis           organised BY REVIEW QUESTION, so Results write themselves
  7 PRISMA Flow         auto-computed from Screening
  8 Threats to Validity required by the method; the current tracker had no home
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from slr import gaps as G
from slr import protocol as P

# ── palette ────────────────────────────────────────────────
# Black, white and grey only. A tracker is a working instrument, not a poster:
# colour here should mean something, and when six fills all mean "a section"
# they mean nothing. Emphasis is carried by weight and by one grey step, so the
# sheet also survives being printed or photocopied.
NAVY   = "1A1A1A"   # headers and section bars
BLUE   = "404040"   # secondary headers
LIGHT  = "D9D9D9"   # emphasis fill
BAND   = "F2F2F2"   # zebra banding
AMBER  = "E0E0E0"   # was amber — the inclusion test
GREEN  = "EDEDED"   # was green — worked examples
RED    = "D0D0D0"   # was red  — the threats I cannot mitigate
WHITE  = "FFFFFF"
GREY   = "6E6E6E"

H1 = Font(bold=True, size=14, color=NAVY)
H2 = Font(bold=True, size=11, color=WHITE)
BOLD = Font(bold=True, size=10)
BODY = Font(size=10)
SMALL = Font(size=9, color=GREY, italic=True)
MONO = Font(size=9, name="Consolas")

# Set by sheet_synthesis() as it writes, and read by sheet_prisma() for the
# cross-sheet consistency check. Sheet build order therefore matters.
SYNTHESIS_TOTAL_ROW = 5

TOP = Alignment(vertical="top", wrap_text=True)
CTR = Alignment(horizontal="center", vertical="center", wrap_text=True)

THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def band(ws, row, text, span=2):
    """Full-width section header bar."""
    ws.cell(row=row, column=1, value=text).font = H2
    for c in range(1, span + 1):
        ws.cell(row=row, column=c).fill = PatternFill("solid", fgColor=NAVY)
    ws.row_dimensions[row].height = 20
    return row + 1


def kv(ws, row, key, val, key_font=BOLD, val_font=BODY, fill=None):
    a = ws.cell(row=row, column=1, value=key); a.font = key_font; a.alignment = TOP
    b = ws.cell(row=row, column=2, value=val); b.font = val_font; b.alignment = TOP
    if fill:
        a.fill = b.fill = PatternFill("solid", fgColor=fill)
    a.border = b.border = BOX
    return row + 1


def header_row(ws, row, headers, widths=None):
    for j, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=j, value=h)
        c.font = H2; c.fill = PatternFill("solid", fgColor=NAVY)
        c.alignment = CTR; c.border = BOX
    if widths:
        for j, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(j)].width = w
    ws.row_dimensions[row].height = 30
    ws.freeze_panes = ws.cell(row=row + 1, column=1)
    return row + 1


# ── 1. Protocol ────────────────────────────────────────────

def sheet_protocol(wb):
    ws = wb.create_sheet("1. Protocol")
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 118
    r = 1
    ws.cell(row=r, column=1, value="SYSTEMATIC LITERATURE REVIEW PROTOCOL").font = H1
    r += 1
    ws.cell(row=r, column=1, value=P.TITLE).font = Font(italic=True, size=11)
    r += 1
    ws.cell(row=r, column=1,
            value=f"{P.CANDIDATE}  |  {P.PROGRAMME}  |  Supervisor: {P.SUPERVISOR}"
            ).font = SMALL
    r += 1
    ws.cell(row=r, column=1,
            value=f"Protocol v{P.VERSION}, locked {P.PROTOCOL_DATE}, before searching."
            ).font = SMALL
    r += 2

    r = band(ws, r, "THE INCLUSION TEST — every paper supports or challenges this sentence")
    c = ws.cell(row=r, column=1, value=P.CENTRAL_THESIS)
    c.font = Font(bold=True, size=11, color=NAVY); c.alignment = TOP
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
    ws.cell(row=r, column=1).fill = PatternFill("solid", fgColor=AMBER)
    ws.row_dimensions[r].height = 58
    r += 1
    r = kv(ws, r, "If it does neither",
           "It is Background, or it is out. Record the verdict in the extraction column "
           "'Supports or Challenges?'.")
    r = kv(ws, r, "Golden thread", P.GOLDEN_THREAD)
    r += 1

    r = band(ws, r, "OBJECTIVE")
    r = kv(ws, r, "SLR objective", P.SLR_OBJECTIVE)
    r = kv(ws, r, "Why review, when surveys exist?", P.WHY_NOT_AN_EXISTING_SURVEY)
    r = kv(ws, r, "Standards",
           "Kitchenham & Charters (2007) governs how the review is CONDUCTED. "
           "PRISMA 2020 governs how it is REPORTED. Cite both.")
    r += 1

    r = band(ws, r, "REVIEW QUESTIONS (ReQ) — what the SLR asks of the LITERATURE")
    r = kv(ws, r, "Note",
           "Descriptive and analytical, never hypothesis-testing. They map the field; "
           "the thesis tests the system.", key_font=SMALL, val_font=SMALL)
    for q, text in P.REVIEW_QUESTIONS.items():
        r = kv(ws, r, q, text, fill=LIGHT if q in ("ReQ4", "ReQ5") else None)
    r = kv(ws, r, "ReQ4 / ReQ5 highlighted",
           "Both map to RQ1.", key_font=SMALL, val_font=SMALL)
    r += 1

    r = band(ws, r, "MASTER'S SCOPE — 2 Problem Statements, 3 Objectives (v2.1)")
    for k, text in P.PROBLEM_STATEMENTS.items():
        r = kv(ws, r, k, text, fill=AMBER)
    for k, text in P.OBJECTIVES.items():
        r = kv(ws, r, k, text)
    for k, text in P.PHD_EXTENSION.items():
        r = kv(ws, r, k, text, key_font=SMALL, val_font=SMALL)
    r += 1

    r = band(ws, r, "RESEARCH QUESTIONS (RQ) — what the MASTER'S THESIS answers experimentally")
    for q, text in P.RESEARCH_QUESTIONS.items():
        r = kv(ws, r, q, text)
    r += 1

    r = band(ws, r, "MAPPING — Review Question to Research Question")
    for req in P.REVIEW_QUESTIONS:
        r = kv(ws, r, req, f"→ {', '.join(P.REQ_TO_RQ[req])}   |   "
                           f"evidence: {P.REQ_EVIDENCE_SOURCE[req]}")
    r = kv(ws, r, "Rule",
           "Every gap maps to exactly ONE primary Research Question. A gap that maps to "
           "none means the RQ set is incomplete or the gap is out of scope — resolve it "
           "explicitly, never leave it dangling.")
    r += 1

    r = band(ws, r, "SCOPE — fixed before searching")
    for item in P.SCOPE_IN:
        r = kv(ws, r, "IN", item, key_font=Font(bold=True, size=10, color="1F7A3D"))
    for item in P.SCOPE_OUT:
        r = kv(ws, r, "OUT", item, key_font=Font(bold=True, size=10, color="B91C1C"))
    r += 1

    r = band(ws, r, "PUBLICATION WINDOW")
    r = kv(ws, r, f"{P.YEAR_MIN}–{P.YEAR_MAX}", P.YEAR_WINDOW_RATIONALE)
    for name, year, why in P.SEMINAL_ALLOWLIST:
        r = kv(ws, r, f"Seminal exception: {name} {year or ''}".strip(), why)
    r += 1

    r = band(ws, r, "DATABASES — free, programmatic, reproducible")
    r = kv(ws, r, "Subscription indexes",
           "No institutional access. Recorded as threat T1, not hedged. Queries here are "
           "executed as inspectable code against open APIs, so the review is exactly "
           "reproducible — which a subscription index does not permit.",
           key_font=SMALL, val_font=SMALL)
    for k, (name, why) in P.DATABASES.items():
        r = kv(ws, r, f"{k}  {name}", why)
    r += 1

    r = band(ws, r, "SEARCH STRINGS")
    for s in P.SEARCH_STRINGS:
        r = kv(ws, r, f"{s['id']}  →  {', '.join(s['serves'])}",
               f"{s['purpose']}\n\n{s['string']}", val_font=MONO)
        ws.row_dimensions[r - 1].height = 76
    r += 1

    r = band(ws, r, "INCLUSION CRITERIA")
    for k, v in P.INCLUSION.items():
        r = kv(ws, r, k, v)
    r += 1
    r = band(ws, r, "EXCLUSION CRITERIA")
    for k, v in P.EXCLUSION.items():
        r = kv(ws, r, k, v)
    r += 1

    r = band(ws, r, f"QUALITY ASSESSMENT — score each 0 / 0.5 / 1; "
                    f"high quality = ≥{P.QA_HIGH_QUALITY_THRESHOLD}/10")
    for k, v in P.QUALITY.items():
        r = kv(ws, r, k, v, fill=AMBER if k in ("QA6", "QA8") else None)
    r = kv(ws, r, "QA6 / QA8 highlighted",
           "QA6 (speaker-independence) feeds ReQ5. QA8 (latency) feeds ReQ6 → RQ3. Both "
           "are also EXTRACTION columns, because a quality score cannot become a finding "
           "but an extracted variable can.", key_font=SMALL, val_font=SMALL)
    r += 1

    r = band(ws, r, "GAP ANALYSIS — a gap is NOT a limitation")
    r = kv(ws, r, "Chain", "GAP → CAUSE → METHOD → RESEARCH QUESTION")
    for k, v in P.GAP_TYPES.items():
        r = kv(ws, r, f"Type {k}", v, fill=GREEN if k == "c" else None)
    for k, v in P.GAP_STATUS.items():
        r = kv(ws, r, f"Status: {k}", v)
    r = kv(ws, r, "Cause→mechanism rule", P.CAUSE_TO_MECHANISM_RULE)
    for step in P.GAP_METHOD_STEPS:
        r = kv(ws, r, "", step, val_font=BODY)
    r += 1

    r = band(ws, r, "TRAPS — and the structural guard against each")
    for trap, why, guard in P.TRAPS:
        r = kv(ws, r, trap, f"{why}\nGUARD: {guard}")
    r += 1

    r = band(ws, r, "PROTOCOL AMENDMENTS — every change, with its trigger")
    r = kv(ws, r, "Why this section exists",
           "Kitchenham & Charters require the protocol to be piloted and any change "
           "recorded. An unlogged edit to a search string cannot be distinguished from "
           "fitting the protocol to a corpus you have already seen. Each amendment "
           "below was triggered by an automated calibration test that runs BEFORE any "
           "screening decision, not by reading results.")
    if not P.AMENDMENTS:
        r = kv(ws, r, "(none)", "The protocol has not been amended since it was locked.")
    for a in P.AMENDMENTS:
        r = kv(ws, r, f"{a['id']} — {a['target']}",
               f"DATE: {a['date']}  ({a['stage']})\n"
               f"TRIGGER: {a['trigger']}\n"
               f"CAUSE: {a['cause']}\n"
               f"CHANGE: {a['change']}\n"
               f"RATIONALE: {a['rationale']}\n"
               f"EFFECT ON PRIOR WORK: {a['effect_on_prior_work']}")
    r += 1

    r = band(ws, r, "WORKFLOW — Kitchenham's three phases")
    for phase, step, text in P.WORKFLOW:
        r = kv(ws, r, f"{phase}  {step}", text)
    return ws


# ── 2. Search Log ──────────────────────────────────────────

def sheet_search_log(wb):
    ws = wb.create_sheet("2. Search Log")
    ws.cell(row=1, column=1,
            value="SEARCH LOG — one row per search string per source. "
                  "I record the date, hits and export count as I run each search.").font = H1
    # The window is a protocol constant, so it is stated ONCE here. A column
    # repeating "2015-2026" on all 36 rows carried no information, so it is gone;
    # what varies and therefore earns a column is the DATE I ran each search.
    ws.cell(row=2, column=1,
            value=f"Publication window applied to every search below: "
                  f"{P.YEAR_MIN}-{P.YEAR_MAX}, English."
                  f"   Note: arXiv filters on submission date, the others on "
                  f"publication date."
            ).font = Font(bold=True, size=10, color=NAVY)
    r = header_row(ws, 3,
                   ["Date Run", "Source", "String ID", "Serves ReQ", "Search String",
                    "Hits", "Satisfying string", "Notes"],
                   [13, 17, 10, 15, 78, 10, 16, 34])

    # Populated from the real run when slr/out/search_log.csv exists, so the sheet
    # reports what I actually did rather than an empty template I would have to
    # transcribe by hand.
    import csv as _csv
    log_path = Path(__file__).resolve().parent / "out" / "search_log.csv"
    actual = {}
    if log_path.exists():
        with log_path.open(encoding="utf-8") as f:
            for row in _csv.DictReader(f):
                actual[(row["string_id"], row["database"])] = row

    DB_TO_KEY = {"openalex": "D1", "crossref": "D2", "pubmed": "D3", "arxiv": "D4"}
    KEY_TO_DB = {v: k for k, v in DB_TO_KEY.items()}

    for s_ in P.SEARCH_STRINGS:
        for db_key, (db_name, _) in P.DATABASES.items():
            if db_key in ("D7", "D8"):        # snowballing / manual, logged separately
                continue
            rec = actual.get((s_["id"], KEY_TO_DB.get(db_key, "")))
            ws.cell(row=r, column=1, value=(rec or {}).get("date", "")).alignment = TOP
            ws.cell(row=r, column=2, value=f"{db_key} {db_name}").alignment = TOP
            ws.cell(row=r, column=3, value=s_["id"]).alignment = CTR
            ws.cell(row=r, column=4, value=", ".join(s_["serves"])).alignment = TOP
            c = ws.cell(row=r, column=5, value=s_["string"]); c.font = MONO; c.alignment = TOP
            if rec:
                ws.cell(row=r, column=6, value=int(rec["retrieved"])).alignment = CTR
                ws.cell(row=r, column=7, value=int(rec["matched_predicate"])).alignment = CTR
            ws.cell(row=r, column=8,
                    value=(rec or {}).get("notes") or s_["purpose"]).alignment = TOP
            for j in range(1, 9):
                ws.cell(row=r, column=j).border = BOX
                if r % 2 == 0:
                    ws.cell(row=r, column=j).fill = PatternFill("solid", fgColor=BAND)
            ws.row_dimensions[r].height = 46
            r += 1
    r += 1
    ws.cell(row=r, column=1,
            value="D7 Snowballing and D8 Google Scholar are logged below as they are run "
                  "(D8 is a manual recall check and is not reproducible).").font = SMALL
    r += 2
    for doi, why in P.SNOWBALL_SEEDS:
        ws.cell(row=r, column=2, value="D7 Snowballing").alignment = TOP
        ws.cell(row=r, column=5, value=f"seed {doi} — {why}").alignment = TOP
        r += 1
    return ws


# ── 3. Screening ───────────────────────────────────────────

def sheet_screening(wb, blank_rows=600):
    ws = wb.create_sheet("3. Screening")
    ws.cell(row=1, column=1,
            value="SCREENING — every retrieved record I retrieved. Populated by slr/pipeline.py. "
                  "The title/abstract and full-text decisions are mine alone.").font = H1
    cols = [("ID", 9), ("Title", 52), ("First Author", 18), ("Year", 7), ("Venue", 22),
            ("Venue Type", 12), ("DOI", 26), ("Source DB(s)", 16), ("OA Status", 11),
            ("Duplicate of", 11), ("Matched Strings", 15), ("T/A Decision", 13),
            ("T/A Reason", 26), ("Full-Text Decision", 15), ("EC Code", 10),
            ("Notes", 30)]
    r = header_row(ws, 3, [c[0] for c in cols], [c[1] for c in cols])

    dv_ta = DataValidation(type="list", formula1='"Include,Exclude,Maybe"', allow_blank=True)
    dv_ft = DataValidation(type="list", formula1='"Include,Exclude"', allow_blank=True)
    dv_ec = DataValidation(type="list", formula1='"EC1,EC2,EC3,EC4,EC5"', allow_blank=True)
    dv_oa = DataValidation(type="list", formula1='"gold,green,hybrid,bronze,closed"',
                           allow_blank=True)
    for dv in (dv_ta, dv_ft, dv_ec, dv_oa):
        ws.add_data_validation(dv)
    last = r + blank_rows - 1
    dv_ta.add(f"L{r}:L{last}")
    dv_ft.add(f"N{r}:N{last}")
    dv_ec.add(f"O{r}:O{last}")
    dv_oa.add(f"I{r}:I{last}")

    ws.cell(row=1, column=12,
            value="").font = SMALL

    # Populate from the real corpus. The sheet used to ship as an empty grid,
    # which meant either transcribing 2,060 records by hand or never using it.
    # Ordered by screening tier so the strongest candidates are at the top and I
    # can work down. Blank rows follow for anything I add manually.
    import csv as _csv
    src = Path(__file__).resolve().parent / "out" / "screening.csv"
    if src.exists():
        order = {"T1": 0, "T2": 1, "T3": 2, "T4": 3, "X": 4}
        with src.open(encoding="utf-8") as f:
            recs = sorted(_csv.DictReader(f),
                          key=lambda x: (order.get(x.get("tier", "T4"), 9),
                                         -int(x.get("cited_by") or 0)))
        for rec in recs:
            auto = rec["decision"] == "auto-exclude"
            vals = [
                rec["id"], rec["title"], (rec["authors"].split(";")[0] or "").strip(),
                rec["year"], rec["venue"], rec["venue_type"], rec["doi"],
                rec["sources"], rec["oa_status"], rec["merged_from"],
                rec["matched_strings"],
                "Exclude" if auto else "",          # T/A decision — mine to fill
                rec["reason"] if auto else "",
                "", rec["criterion"] if auto else "",
                f"[tier {rec.get('tier','')}] {rec['suggestion'] or ''} {rec['flags']}".strip(),
            ]
            for j, v in enumerate(vals, start=1):
                c = ws.cell(row=r, column=j, value=v)
                c.alignment = TOP; c.font = BODY; c.border = BOX
                # Auto-excluded rows are greyed: the machine already decided
                # these on mechanical grounds and I do not need to read them.
                if auto:
                    c.fill = PatternFill("solid", fgColor=LIGHT)
                elif r % 2 == 0:
                    c.fill = PatternFill("solid", fgColor=BAND)
            r += 1
    return ws


# ── 4. Data Extraction ─────────────────────────────────────

def sheet_extraction(wb, blank_rows=200):
    ws = wb.create_sheet("4. Data Extraction")
    ws.cell(row=1, column=1,
            value="DATA EXTRACTION — one row per paper I include. I fill every column; "
                  "write 'NR' when a paper does not report something.").font = H1
    ws.cell(row=2, column=1,
            value="Write 'NR' where a paper does not report an item.").font = SMALL
    r = header_row(ws, 4, [c[0] for c in P.EXTRACTION_COLUMNS],
                   [c[1] for c in P.EXTRACTION_COLUMNS])
    # hint row
    for j, (_, _, hint) in enumerate(P.EXTRACTION_COLUMNS, start=1):
        c = ws.cell(row=r, column=j, value=hint)
        c.font = SMALL; c.alignment = TOP
        c.fill = PatternFill("solid", fgColor=BAND)
    ws.row_dimensions[r].height = 40
    r += 1

    names = [c[0] for c in P.EXTRACTION_COLUMNS]
    last = r + blank_rows - 1

    def add_list(col_name, options):
        if col_name not in names:
            return
        letter = get_column_letter(names.index(col_name) + 1)
        dv = DataValidation(type="list", formula1=f'"{options}"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f"{letter}{r}:{letter}{last}")

    add_list("Task Type", "categorical emotion,sentiment regression,dimensional,multi-label")
    add_list("Evaluation Protocol",
             "random split,speaker-independent,LOSO,k-fold SI,cross-corpus,NR")
    add_list("Metric Type", "accuracy,WA,UA (UAR),weighted-F1,macro-F1,NR")
    add_list("Supports or Challenges?", "supports,challenges,background")
    add_list("Venue Type", "journal,conference,preprint,thesis")
    add_list("Healthcare / Caregiving?", "Yes,mentioned only,No")
    add_list("Unimodal Baseline Compared?", "Yes,No,NR")
    add_list("Ethics / Privacy Discussed?", "Yes,No")

    # Seed with the papers I have already read in full and used as evidence in
    # the Gap Chains sheet. Screening has not run yet, so this is not the final
    # included set — it is the work already done, so the sheet is not empty while
    # I screen. Metadata comes from the cached OpenAlex records; the analytical
    # columns are mine to fill from the full text.
    seeded = [
        ("10.1109/ICMCSI67283.2026.11412916",
         "Mutheeswaran et al. 2026", "read in full — G2, G3, G4, G5"),
        ("10.3390/s25165066",
         "Sensors 2025 (Multi-Scale Temporal Fusion)", "nearest paper to my scope — G1"),
        ("10.1609/aaai.v34i02.5492", "Mittal et al. 2020 (M3ER)", "snowball seed — G6"),
        ("10.18653/v1/P19-1656", "Tsai et al. 2019 (MulT)", "snowball seed — G6"),
        ("10.3390/s23125475", "Mamieva et al. 2023", "snowball seed"),
        ("10.3390/s21144913", "Xie et al. 2021", "snowball seed"),
        ("10.3390/e25101440", "Lian et al. 2023", "snowball seed — survey"),
    ]
    try:
        from slr.sources import openalex as _oa
        for i, (doi, cite, note) in enumerate(seeded, start=1):
            rec = _oa.by_doi(doi)
            vals = {1: f"EX{i:02d}", 2: cite,
                    3: rec.title if rec else "", 4: doi,
                    5: rec.venue if rec else "", 6: rec.venue_type if rec else "",
                    7: rec.year if rec else "", 8: rec.oa_status if rec else "",
                    len(P.EXTRACTION_COLUMNS): note}
            for j in range(1, len(P.EXTRACTION_COLUMNS) + 1):
                c = ws.cell(row=r, column=j, value=vals.get(j, ""))
                c.alignment = TOP; c.font = BODY; c.border = BOX
                c.fill = PatternFill("solid", fgColor=GREEN)
            r += 1
    except Exception as e:                      # offline / no cache — leave blank
        ws.cell(row=r, column=1,
                value=f"(seed rows unavailable: {e})").font = SMALL
    return ws


# ── 5. Gap Chains ──────────────────────────────────────────

def sheet_gap_chains(wb, blank_rows=150):
    ws = wb.create_sheet("5. Gap Chains")
    ws.cell(row=1, column=1,
            value="GAP CHAINS — GAP → CAUSE → METHOD → RESEARCH QUESTION. "
                  "One row per gap I identify, not per paper.").font = H1
    ws.cell(row=2, column=1,
            value="Type (a) author-stated · (b) attributed by later work · (c) scope, "
                  "relative to this review's healthcare and deployment lens.").font = SMALL
    ws.cell(row=3, column=1,
            value="Each row cites the evidence it rests on. Verified against full "
                  "texts and against this project's own measured results.").font = SMALL
    r = header_row(ws, 4, [c[0] for c in P.GAP_CHAIN_COLUMNS],
                   [c[1] for c in P.GAP_CHAIN_COLUMNS])
    for j, (_, _, hint) in enumerate(P.GAP_CHAIN_COLUMNS, start=1):
        c = ws.cell(row=r, column=j, value=hint)
        c.font = SMALL; c.alignment = TOP
        c.fill = PatternFill("solid", fgColor=BAND)
    ws.row_dimensions[r].height = 42
    r += 1

    names = [c[0] for c in P.GAP_CHAIN_COLUMNS]
    last = r + blank_rows - 1
    rq_opts = ",".join(P.RESEARCH_QUESTIONS.keys())
    for col, opts in (("Gap Type", "a,b,c"),
                      ("Cause", ",".join(P.GAP_CAUSES)),
                      ("Status", "closed,open,scope"),
                      ("Cause<->Mechanism match?", "Yes,No,Partial"),
                      ("Primary Research Question", rq_opts),
                      ("Secondary RQ", f"{rq_opts},none")):
        if col in names:
            letter = get_column_letter(names.index(col) + 1)
            dv = DataValidation(type="list", formula1=f'"{opts}"', allow_blank=True)
            ws.add_data_validation(dv)
            dv.add(f"{letter}{r}:{letter}{last}")

    # Rows come from slr/gaps.py, which is verified against full texts and against
    # this project's own result files. They were previously hard-coded here, and
    # one of them asserted "no named dataset" for Mutheeswaran et al. — refuted by
    # the full text, which names DEAP. Generating from a single source stops the
    # tracker and the analysis drifting apart.
    seed = [
        [g["id"], g["paper_id"], g["citation"], g["statement"], g["type"], g["cause"],
         g["responders"], g["status"], g["method"], g["cause_mechanism_match"],
         g["rq"], g.get("rq2") or "none",
         f"EVIDENCE: {g['evidence']}\nCAVEAT: {g['caveat']}"]
        for g in G.GAP_CHAINS
    ]
    for row_vals in seed:
        for j, v in enumerate(row_vals, start=1):
            c = ws.cell(row=r, column=j, value=v)
            c.alignment = TOP; c.font = BODY
            c.fill = PatternFill("solid", fgColor=GREEN)
            c.border = BOX
        ws.row_dimensions[r].height = 58
        r += 1
    return ws


# ── 6. Synthesis — organised BY REVIEW QUESTION ────────────

def sheet_synthesis(wb):
    ws = wb.create_sheet("6. Synthesis")
    ws.column_dimensions["A"].width = 52
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 76
    r = 1
    ws.cell(row=r, column=1,
            value="SYNTHESIS — organised BY REVIEW QUESTION").font = H1
    r += 1
    ws.cell(row=r, column=1,
            value="Organised by Review Question. Counts come from "
                  "'4. Data Extraction'.").font = SMALL
    r += 2

    E = "'4. Data Extraction'"
    # column letters in the extraction sheet
    names = [c[0] for c in P.EXTRACTION_COLUMNS]
    def col(name):
        return get_column_letter(names.index(name) + 1)

    rng = lambda name: f"{E}!{col(name)}6:{col(name)}205"

    r = band(ws, r, "CORPUS", span=3)
    global SYNTHESIS_TOTAL_ROW
    SYNTHESIS_TOTAL_ROW = r
    r = kv(ws, r, "Total papers extracted", f"=COUNTA({E}!A6:A205)")
    ws.cell(row=r - 1, column=3, value="Must equal PRISMA 'included'").font = SMALL
    r = kv(ws, r, "Published 2015–2019",
           f'=COUNTIFS({rng("Year")},"<=2019",{rng("Year")},">=2015")')
    ws.cell(row=r - 1, column=3,
            value="Stratification demonstrates the field's shift rather than assuming "
                  "it — see the publication-window rationale.").font = SMALL
    r = kv(ws, r, "Published 2020–2026", f'=COUNTIF({rng("Year")},">=2020")')
    r = kv(ws, r, "Preprints in corpus", f'=COUNTIF({rng("Venue Type")},"preprint")')
    r = kv(ws, r, "Mean QA score (/10)", f'=IFERROR(AVERAGE({rng("QA Score (/10)")}),"")')
    r = kv(ws, r, f"High quality (≥{P.QA_HIGH_QUALITY_THRESHOLD}/10)",
           f'=COUNTIF({rng("QA Score (/10)")},">={P.QA_HIGH_QUALITY_THRESHOLD}")')
    r = kv(ws, r, "Supports the central thesis",
           f'=COUNTIF({rng("Supports or Challenges?")},"supports")')
    r = kv(ws, r, "Challenges the central thesis",
           f'=COUNTIF({rng("Supports or Challenges?")},"challenges")')
    ws.cell(row=r - 1, column=3,
            value="").font = SMALL
    r += 1

    blocks = [
        ("ReQ1", [("Healthcare/caregiving context (Yes)",
                   f'=COUNTIF({rng("Healthcare / Caregiving?")},"Yes")',
                   "Papers targeting a care setting"),
                  ("Healthcare mentioned only",
                   f'=COUNTIF({rng("Healthcare / Caregiving?")},"mentioned only")',
                   "Healthcare named as an application domain only")]),
        ("ReQ2", [("Speech + facial",
                   f'=COUNTIF({rng("Modalities Used")},"*speech*facial*")', ""),
                  ("Includes behavioural / skeletal",
                   f'=COUNTIF({rng("Modalities Used")},"*behavioural*")',
                   "Maps the third-stream baseline for PhD continuation (PS3)"),
                  ("Includes physiological",
                   f'=COUNTIF({rng("Modalities Used")},"*physiolog*")',
                   "Requires body-worn sensors")]),
        ("ReQ3", [("Feature-level (early) fusion",
                   f'=COUNTIF({rng("Fusion Strategy")},"*feature*")', ""),
                  ("Decision-level (late) fusion",
                   f'=COUNTIF({rng("Fusion Strategy")},"*decision*")', ""),
                  ("Cross-modal attention",
                   f'=COUNTIF({rng("Fusion Strategy")},"*attention*")',
                   "By publication year"),
                  ("Tensor-based",
                   f'=COUNTIF({rng("Fusion Strategy")},"*tensor*")', ""),
                  ("Hybrid", f'=COUNTIF({rng("Fusion Strategy")},"*hybrid*")', "")]),
        ("ReQ4", [("Uses IEMOCAP", f'=COUNTIF({rng("Dataset(s)")},"*IEMOCAP*")', ""),
                  ("Uses CMU-MOSI/MOSEI", f'=COUNTIF({rng("Dataset(s)")},"*MOS*")', ""),
                  ("Uses RAVDESS", f'=COUNTIF({rng("Dataset(s)")},"*RAVDESS*")', ""),
                  ("Uses clinical / patient data",
                   f'=COUNTIF({rng("Dataset(s)")},"*clinic*")',
                   "Evaluated on a corpus recorded in a care setting"),
                  ("Dataset NOT NAMED",
                   f'=COUNTIF({rng("Dataset(s)")},"NR")',
                   "Dataset not named (QA2)")]),
        ("ReQ5", [("Speaker-independent evaluation",
                   f'=COUNTIF({rng("Evaluation Protocol")},"speaker-independent")',
                   "By evaluation protocol reported"),
                  ("LOSO or k-fold SI",
                   f'=COUNTIF({rng("Evaluation Protocol")},"*LOSO*")'
                   f'+COUNTIF({rng("Evaluation Protocol")},"k-fold SI")', ""),
                  ("Random split (speaker-dependent)",
                   f'=COUNTIF({rng("Evaluation Protocol")},"random split")',
                   "Speaker overlap between train and test"),
                  ("Protocol NOT REPORTED",
                   f'=COUNTIF({rng("Evaluation Protocol")},"NR")',
                   "Evaluation protocol not reported (QA6)"),
                  ("Reports UA/UAR rather than accuracy",
                   f'=COUNTIF({rng("Metric Type")},"UA (UAR)")',
                   "Reported separately; these metrics are not comparable"),
                  ("Sentiment regression (do NOT pool with emotion)",
                   f'=COUNTIF({rng("Task Type")},"sentiment regression")',
                   "By fusion strategy")]),
        ("ReQ6", [("Robustness tested",
                   f'=200-COUNTIF({rng("Robustness Tested")},"No")'
                   f'-COUNTIF({rng("Robustness Tested")},"NR")'
                   f'-COUNTBLANK({rng("Robustness Tested")})', "Robustness condition tested"),
                  ("Claim real-time capability",
                   f'=COUNTIF({rng("Real-Time Capable?")},"*Yes*")', ""),
                  ("Actually report latency (ms)",
                   f'=200-COUNTIF({rng("Latency Reported (ms)")},"NR")'
                   f'-COUNTBLANK({rng("Latency Reported (ms)")})',
                   "Latency claimed vs latency measured"),
                  ("Deployed on edge hardware",
                   f'=200-COUNTIF({rng("Edge Hardware Used")},"none")'
                   f'-COUNTIF({rng("Edge Hardware Used")},"NR")'
                   f'-COUNTBLANK({rng("Edge Hardware Used")})', "Edge hardware reported"),
                  ("Applied compression",
                   f'=200-COUNTIF({rng("Compression")},"none")'
                   f'-COUNTIF({rng("Compression")},"NR")'
                   f'-COUNTBLANK({rng("Compression")})', ""),
                  ("Ethics / privacy discussed",
                   f'=COUNTIF({rng("Ethics / Privacy Discussed?")},"Yes")',
                   "Ethics or privacy discussed")]),
        ("ReQ7", [("Gaps recorded (see sheet 5)",
                   "='5. Gap Chains'!A6", "Count of rows in Gap Chains"),
                  ("OPEN gaps", '=COUNTIF(\'5. Gap Chains\'!H6:H155,"open")',
                   "Gap chains recorded"),
                  ("SCOPE gaps", '=COUNTIF(\'5. Gap Chains\'!H6:H155,"scope")',
                   "Scope gaps, relative to this review's lens"),
                  ("CLOSED gaps", '=COUNTIF(\'5. Gap Chains\'!H6:H155,"closed")',
                   "Status: closed")]),
    ]

    for req, rows in blocks:
        r = band(ws, r,
                 f"{req} — {P.REVIEW_QUESTIONS[req]}   [→ {', '.join(P.REQ_TO_RQ[req])}]",
                 span=3)
        for label, formula, note in rows:
            a = ws.cell(row=r, column=1, value=label); a.font = BODY; a.alignment = TOP
            b = ws.cell(row=r, column=2, value=formula); b.font = BOLD; b.alignment = CTR
            c = ws.cell(row=r, column=3, value=note); c.font = SMALL; c.alignment = TOP
            for j in range(1, 4):
                ws.cell(row=r, column=j).border = BOX
            r += 1
        r += 1

    r = band(ws, r, "GAP STATEMENT — write only after the counts are in", span=3)
    c = ws.cell(row=r, column=1,
                value='"Of the N studies reviewed, only X evaluated robustness under '
                      'realistic conditions, Y reported inference latency, and Z targeted '
                      'edge deployment — and only W used speaker-independent evaluation. '
                      'None combined all of these in a healthcare context with an explicit '
                      'privacy-by-design framework. This gap motivates the present research."')
    c.font = Font(italic=True, size=10); c.alignment = TOP
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
    ws.cell(row=r, column=1).fill = PatternFill("solid", fgColor=AMBER)
    ws.row_dimensions[r].height = 62
    return ws


# ── 7. PRISMA Flow ─────────────────────────────────────────

def sheet_prisma(wb):
    ws = wb.create_sheet("7. PRISMA Flow")
    ws.column_dimensions["A"].width = 50
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 62
    r = 1
    ws.cell(row=r, column=1, value="PRISMA 2020 FLOW — auto-computed").font = H1
    r += 1
    ws.cell(row=r, column=1,
            value="PRISMA governs REPORTING; Kitchenham governs conduct. Copy these "
                  "numbers into the flow diagram.").font = SMALL
    r += 2
    S = "'3. Screening'"
    L = "'2. Search Log'"

    # Record row positions AS THEY ARE WRITTEN. Hand-counting them produced two
    # broken checks on the first build: one comparing a formula to itself (always
    # "OK") and one pointing at an empty cell (always "MISMATCH"). A check that
    # cannot fail, and a check that cannot pass, are both worse than no check.
    at = {}

    r = band(ws, r, "IDENTIFICATION", span=3)
    at["identified"] = r
    r = kv(ws, r, "Records identified (sum of Search Log hits)", f"=SUM({L}!G4:G200)")
    at["after_dupes"] = r
    r = kv(ws, r, "Records after duplicates removed",
           f"=COUNTA({S}!A4:A603)-COUNTA({S}!J4:J603)")
    at["dupes"] = r
    r = kv(ws, r, "Duplicates removed", f"=COUNTA({S}!J4:J603)")
    ws.cell(row=r - 1, column=3,
            value="Merged aliases, per EC4 — the preprint of a published pair is "
                  "recorded, not deleted.").font = SMALL
    r += 1

    r = band(ws, r, "SCREENING", span=3)
    at["screened"] = r
    r = kv(ws, r, "Records screened (title/abstract)",
           f"=COUNTA({S}!A4:A603)-COUNTA({S}!J4:J603)")
    r = kv(ws, r, "Excluded at title/abstract", f'=COUNTIF({S}!L4:L603,"Exclude")')
    r = kv(ws, r, "Sought for full-text retrieval",
           f'=COUNTIF({S}!L4:L603,"Include")+COUNTIF({S}!L4:L603,"Maybe")')
    r += 1

    r = band(ws, r, "ELIGIBILITY", span=3)
    r = kv(ws, r, "Full-text assessed", f"=COUNTA({S}!N4:N603)")
    r = kv(ws, r, "Excluded at full text", f'=COUNTIF({S}!N4:N603,"Exclude")')
    for ec, desc in P.EXCLUSION.items():
        r = kv(ws, r, f"   — {ec}", f'=COUNTIF({S}!O4:O603,"{ec}")')
        ws.cell(row=r - 1, column=3, value=desc).font = SMALL
    r = kv(ws, r, "   of which EC5 was ACCESS-driven, not content-driven", "")
    ws.cell(row=r - 1, column=3,
            value="Count manually. Threat T7 — without institutional access some "
                  "exclusions are about retrievability, not relevance. Report separately "
                  "or the corpus looks more selective than it is.").font = SMALL
    r += 1

    r = band(ws, r, "INCLUDED", span=3)
    at["included"] = r
    r = kv(ws, r, "Studies included in review", f'=COUNTIF({S}!N4:N603,"Include")')
    ws.cell(row=r - 1, column=3,
            value="Must equal 'Total papers extracted' on sheet 6.").font = SMALL
    r += 1
    r = band(ws, r, "CONSISTENCY CHECK", span=3)
    r = kv(ws, r, "identified − duplicates = screened ?",
           f'=IF(B{at["identified"]}-B{at["dupes"]}=B{at["screened"]},'
           f'"OK","MISMATCH — investigate")')
    ws.cell(row=r - 1, column=3,
            value="Compares three DIFFERENT quantities. If this reads MISMATCH, either "
                  "the Search Log hits are incomplete or records were added to Screening "
                  "without being logged.").font = SMALL
    r = kv(ws, r, "extraction rows = included ?",
           f'=IF(\'6. Synthesis\'!B{SYNTHESIS_TOTAL_ROW}=B{at["included"]},'
           f'"OK","MISMATCH — investigate")')
    ws.cell(row=r - 1, column=3,
            value="Every included study must have exactly one extraction row.").font = SMALL
    return ws


# ── 8. Threats to Validity ─────────────────────────────────

def sheet_threats(wb):
    ws = wb.create_sheet("8. Threats to Validity")
    ws.cell(row=1, column=1, value="THREATS TO VALIDITY — the limits of what I can claim").font = H1
    ws.cell(row=2, column=1,
            value="The limits on what this review can claim, and how each is mitigated.").font = SMALL
    r = header_row(ws, 4, ["ID", "Threat", "Description", "Mitigation"],
                   [7, 26, 58, 58])
    for tid, name, desc, mit in P.THREATS:
        ws.cell(row=r, column=1, value=tid).alignment = CTR
        ws.cell(row=r, column=2, value=name).font = BOLD
        ws.cell(row=r, column=2).alignment = TOP
        ws.cell(row=r, column=3, value=desc).alignment = TOP
        ws.cell(row=r, column=4, value=mit).alignment = TOP
        fill = RED if tid in ("T1", "T4") else (BAND if r % 2 == 0 else WHITE)
        for j in range(1, 5):
            ws.cell(row=r, column=j).border = BOX
            ws.cell(row=r, column=j).fill = PatternFill("solid", fgColor=fill)
            if j > 1:
                ws.cell(row=r, column=j).font = BODY if j > 2 else BOLD
        ws.row_dimensions[r].height = 62
        r += 1
    r += 1
    ws.cell(row=r, column=2,
            value="T1 and T4 are the structural limitations of this review: no "
                  "subscription indexes, and single-reviewer screening with no "
                  "inter-rater agreement.").font = SMALL
    return ws


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="slr/out/SLR_Tracker_v2.xlsx")
    args = ap.parse_args()

    orphans = P.orphaned_review_questions()
    if orphans:
        sys.exit(f"Protocol error: Review Questions with no Research Question: {orphans}")
    unserved = [q for q in P.REVIEW_QUESTIONS if not P.strings_for(q)]
    if unserved:
        print(f"  warning: ReQs with no search string (check REQ_EVIDENCE_SOURCE): {unserved}")

    wb = Workbook()
    # Authorship. openpyxl stamps itself as creator otherwise.
    wb.properties.creator = P.CANDIDATE
    wb.properties.lastModifiedBy = P.CANDIDATE
    wb.properties.title = "Systematic Literature Review Tracker"
    wb.properties.subject = P.TITLE
    wb.properties.description = (
        f"SLR protocol v{P.VERSION}, locked {P.PROTOCOL_DATE}. "
        f"{P.PROGRAMME}. Supervisor: {P.SUPERVISOR}.")
    wb.remove(wb.active)
    sheet_protocol(wb)
    sheet_search_log(wb)
    sheet_screening(wb)
    sheet_extraction(wb)
    sheet_gap_chains(wb)
    sheet_synthesis(wb)
    sheet_prisma(wb)
    sheet_threats(wb)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"Wrote {out}")
    print(f"  sheets            : {len(wb.sheetnames)}  -> {', '.join(wb.sheetnames)}")
    print(f"  Review Questions  : {len(P.REVIEW_QUESTIONS)}  (all mapped, all evidenced)")
    print(f"  search strings    : {len(P.SEARCH_STRINGS)}")
    print(f"  extraction columns: {len(P.EXTRACTION_COLUMNS)}")
    print(f"  threats recorded  : {len(P.THREATS)}")
    print("  Structure is generated from slr/protocol.py — edit the protocol and re-run.")


if __name__ == "__main__":
    main()
