"""
Bundle every SLR output into one Excel workbook.

    python3 -m slr.to_excel
    python3 -m slr.to_excel --out slr/out/SLR_Working_Data.xlsx

WHY THE CSVs STILL EXIST
    The CSVs are the machinery, not the deliverable. slr/screen_cli.py appends
    to decisions.csv after every judgement and flushes immediately, so a crash
    on day three cannot cost day two; slr/pipeline.py rewrites screening.csv
    wholesale on each run. Excel cannot be appended to safely from a running
    process, and a workbook held open by Excel is locked against writes.

    So the CSVs stay as the working format and this produces a readable view
    over them, the same way the tracker is a view over the protocol. Re-run it
    whenever the underlying data changes.

    EDITS MADE IN THE WORKBOOK DO NOT FLOW BACK. Screening decisions belong in
    screen_cli; anything typed into these sheets is overwritten next rebuild.
    The one exception is the Notes column, which is yours and is preserved.
"""
import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

OUT = Path(__file__).resolve().parent / "out"
DEFAULT = OUT / "SLR_Working_Data.xlsx"

# Greyscale, matching the tracker: a working instrument, not a poster.
INK, BAND, LIGHT, WHITE, GREY = "1A1A1A", "F2F2F2", "D9D9D9", "FFFFFF", "6E6E6E"
H1 = Font(bold=True, size=13, color=INK)
HDR = Font(bold=True, size=10, color=WHITE)
BODY = Font(size=10)
SMALL = Font(size=9, color=GREY, italic=True)
TOP = Alignment(vertical="top", wrap_text=True)
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

# (csv name, sheet name, one-line description, column widths by header substring)
SOURCES = [
    ("screening.csv", "Screening",
     "Every unique record retrieved. My title/abstract and full-text decisions go "
     "in via screen_cli, not here.",
     {"title": 60, "abstract": 80, "reason": 30, "suggestion": 30, "flags": 26,
      "authors": 26, "venue": 24, "doi": 24, "pdf_url": 30, "notes": 24}),
    ("prescreen.csv", "Decision briefs",
     "Facts extracted from each abstract, tagged with the criterion each bears on, "
     "with the sentence it came from. Facts only — no recommendation.",
     {"title": 58, "facts": 46, "evidence": 90, "datasets": 22}),
    ("access.csv", "Full-text access",
     "Open-access copies resolved via Unpaywall, falling back to arXiv. 'version' "
     "matters: an accepted manuscript is not the version of record.",
     {"title": 58, "url": 52, "landing_page": 40}),
    ("search_log.csv", "Search log",
     "One row per search string per source, as actually run.",
     {"protocol_string": 70, "query_sent": 60, "purpose": 40, "notes": 30}),
    ("nearest_neighbours.csv", "Nearest neighbours",
     "Records mentioning edge deployment AND healthcare — the intersection this "
     "thesis occupies, and the papers most likely to challenge its novelty.",
     {"title": 60, "abstract": 80, "venue": 24}),
    ("decisions.csv", "My decisions",
     "Written by screen_cli, one row per judgement, with the reason recorded at "
     "the time rather than reconstructed later.",
     {"title": 58, "reason": 40, "note": 40}),
]


def add_table(wb, name, title, note, rows, widths):
    ws = wb.create_sheet(name[:31])
    ws.cell(row=1, column=1, value=title).font = H1
    ws.cell(row=2, column=1, value=note).font = SMALL
    if not rows:
        ws.cell(row=4, column=1,
                value="(no data yet — this fills as the work proceeds)").font = SMALL
        return ws, 0

    headers = list(rows[0])
    for j, h in enumerate(headers, start=1):
        c = ws.cell(row=4, column=j, value=h)
        c.font = HDR
        c.fill = PatternFill("solid", fgColor=INK)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BOX
        w = next((v for k, v in widths.items() if k in h.lower()), 14)
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.row_dimensions[4].height = 26
    ws.freeze_panes = ws.cell(row=5, column=1)
    ws.auto_filter.ref = f"A4:{get_column_letter(len(headers))}{4 + len(rows)}"

    for i, row in enumerate(rows):
        r = 5 + i
        for j, h in enumerate(headers, start=1):
            v = row.get(h, "")
            # Numbers as numbers, so sorting and filtering behave.
            if isinstance(v, str) and v.isdigit() and h.lower() in (
                    "year", "cited_by", "hits", "retrieved", "matched_predicate"):
                v = int(v)
            c = ws.cell(row=r, column=j, value=v)
            c.font = BODY
            c.alignment = TOP
            c.border = BOX
            if i % 2:
                c.fill = PatternFill("solid", fgColor=BAND)
    return ws, len(rows)


def read_csv(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build(dest: Path):
    wb = Workbook()
    wb.remove(wb.active)

    # ── contents sheet ──
    ws = wb.create_sheet("Contents")
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 104
    ws.cell(row=1, column=1, value="SLR WORKING DATA").font = H1
    ws.cell(row=2, column=1,
            value=f"Generated {date.today().isoformat()} from the CSVs in slr/out/. "
                  "Re-run `python3 -m slr.to_excel` after any change.").font = SMALL
    ws.cell(row=3, column=1,
            value="Edits made here do NOT flow back. Screening decisions go through "
                  "`python3 -m slr.screen_cli`; anything typed into these sheets is "
                  "replaced on the next rebuild.").font = SMALL
    r = 5
    for j, h in enumerate(("Sheet", "Rows", "What it holds"), start=1):
        c = ws.cell(row=r, column=j, value=h)
        c.font = HDR
        c.fill = PatternFill("solid", fgColor=INK)
        c.border = BOX
    r += 1

    made = []
    for fname, sheet, note, widths in SOURCES:
        rows = read_csv(OUT / fname)
        _, n = add_table(wb, sheet, sheet, note, rows, widths)
        made.append((sheet, n, note))
        a = ws.cell(row=r, column=1, value=sheet); a.font = Font(bold=True, size=10)
        b = ws.cell(row=r, column=2, value=n); b.alignment = Alignment(horizontal="right")
        c = ws.cell(row=r, column=3, value=note); c.alignment = TOP
        for j in range(1, 4):
            ws.cell(row=r, column=j).border = BOX
        r += 1

    # ── the two JSON results, flattened ──
    prisma = OUT / "prisma.json"
    if prisma.exists():
        d = json.loads(prisma.read_text())
        flat = []
        for section in ("identification", "automated_screening", "screening_tiers"):
            blk = d.get(section, {})
            for k, v in blk.items():
                if isinstance(v, (int, str)):
                    flat.append({"section": section, "item": k, "value": v})
                elif isinstance(v, dict):
                    for k2, v2 in v.items():
                        if isinstance(v2, (int, str)):
                            flat.append({"section": section, "item": f"{k} · {k2}",
                                         "value": v2})
        _, n = add_table(wb, "PRISMA numbers", "PRISMA numbers",
                         "Identification and mechanical screening, straight from "
                         "prisma.json.", flat, {"item": 46, "value": 60, "section": 22})
        made.append(("PRISMA numbers", n, "identification and screening counts"))
        a = ws.cell(row=r, column=1, value="PRISMA numbers"); a.font = Font(bold=True, size=10)
        ws.cell(row=r, column=2, value=n).alignment = Alignment(horizontal="right")
        ws.cell(row=r, column=3, value="identification and mechanical screening counts")
        for j in range(1, 4):
            ws.cell(row=r, column=j).border = BOX
        r += 1

    lat = OUT / "falsification_S7.json"
    if lat.exists():
        d = json.loads(lat.read_text())
        rungs = [{"clauses active": rr["n_clauses"],
                  "dropped": ", ".join(rr["dropped"]),
                  "papers": rr["count"]} for rr in d.get("rungs", [])]
        rungs.insert(0, {"clauses active": len(d.get("clauses", [])),
                         "dropped": "(none — the full conjunction)",
                         "papers": d["full_conjunction"]["count"]})
        _, n = add_table(wb, "Conjunction ladder", "Conjunction ladder (S7)",
                         f"Falsification test over a pool of {d.get('pool')} papers. "
                         "The full seven-clause query returns zero; relaxing a clause "
                         "shows what the literature does contain.",
                         rungs, {"dropped": 56, "papers": 12, "clauses": 14})
        made.append(("Conjunction ladder", n, "the falsification test"))
        a = ws.cell(row=r, column=1, value="Conjunction ladder"); a.font = Font(bold=True, size=10)
        ws.cell(row=r, column=2, value=n).alignment = Alignment(horizontal="right")
        ws.cell(row=r, column=3, value="S7 falsification ladder")
        for j in range(1, 4):
            ws.cell(row=r, column=j).border = BOX

    dest.parent.mkdir(parents=True, exist_ok=True)
    wb.save(dest)
    return made


def main(argv=None):
    p = argparse.ArgumentParser(description="Bundle the SLR CSVs into one workbook")
    p.add_argument("--out", default=str(DEFAULT))
    a = p.parse_args(argv)
    dest = Path(a.out)
    made = build(dest)
    print(f"Wrote {dest}")
    for sheet, n, _ in made:
        print(f"  {sheet:22s} {n:>6} rows")
    print("\nThe CSVs remain the working format — the tools read and write them.")
    print("Decisions go through `python3 -m slr.screen_cli`, not this workbook.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
