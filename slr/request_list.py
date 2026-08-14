"""
Build the list of papers to request from someone with subscription access.

    python3 -m slr.request_list                     # T1 only (the priority ask)
    python3 -m slr.request_list --tier T1,T2
    python3 -m slr.request_list --dois-only         # bare DOI list for bulk tools

WHAT GOES ON THE LIST
    Only records that are (a) awaiting my screening decision, (b) have no usable
    link from the search, and (c) were not recovered as an open-access copy by
    slr/access.py. Everything already readable is excluded — there is no point
    asking a busy person for a paper I can already open.

    Ordered by citation count, most-cited first, so that a partial response is
    still a useful response.

WHY DOIs LEAD EVERY ENTRY
    A DOI is what a library resolver, an EZproxy link and most bulk-download
    tools actually consume. Titles are for the human reading the list; the DOI
    is for the machine. Every entry on the T1 list has one.
"""
import argparse
import csv
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
SCREENING = OUT / "screening.csv"
ACCESS = OUT / "access.csv"


def load():
    if not SCREENING.exists():
        sys.exit(f"missing {SCREENING}")
    rows = [r for r in csv.DictReader(SCREENING.open(encoding="utf-8"))
            if r["decision"] == "review"]
    got = {}
    if ACCESS.exists():
        for a in csv.DictReader(ACCESS.open(encoding="utf-8")):
            if a.get("resolved") == "yes":
                got[a["id"]] = a
    return rows, got


def needed(tiers):
    rows, got = load()
    out = [r for r in rows
           if r["tier"] in tiers
           and not r["pdf_url"].strip()
           and r["id"] not in got]
    out.sort(key=lambda r: -int(r["cited_by"] or 0))
    return out


def write_xlsx(recs, dest, tiers):
    """A workbook he can tick off, with DOIs as live links.

    The DOI is hyperlinked to doi.org rather than to a publisher page: doi.org
    redirects through whatever resolver the reader's institution has configured,
    so one click lands him inside his own subscription rather than on a paywall.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    INK, BAND, WHITE = "1A1A1A", "F2F2F2", "FFFFFF"
    thin = Side(style="thin", color="BFBFBF")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    top = Alignment(vertical="top", wrap_text=True)

    wb = Workbook()
    wb.properties.creator = "Nwachukwu Chinemerem Favour"
    wb.properties.lastModifiedBy = "Nwachukwu Chinemerem Favour"
    wb.properties.title = "Papers requested via subscription access"
    ws = wb.active
    ws.title = "Papers requested"

    ws["A1"] = (f"Papers I cannot access — {', '.join(sorted(tiers))} tier, "
                f"{len(recs)} items")
    ws["A1"].font = Font(bold=True, size=13, color=INK)
    ws["A2"] = ("Ordered by citation count, most-cited first. DOIs are clickable and "
                "resolve through doi.org. The 'Downloaded' column is for your use.")
    ws["A2"].font = Font(size=9, italic=True, color="6E6E6E")

    heads = ["#", "DOI", "Title", "First author", "Year", "Venue", "Cited", "Downloaded"]
    widths = [5, 30, 62, 22, 7, 34, 8, 13]
    for j, (h, w) in enumerate(zip(heads, widths), start=1):
        c = ws.cell(row=4, column=j, value=h)
        c.font = Font(bold=True, size=10, color=WHITE)
        c.fill = PatternFill("solid", fgColor=INK)
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = box
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.row_dimensions[4].height = 22
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = f"A4:{get_column_letter(len(heads))}{4 + len(recs)}"

    for i, r in enumerate(recs):
        row = 5 + i
        first = (r["authors"].split(";")[0] or "").strip()
        more = " et al." if ";" in r["authors"] else ""
        vals = [i + 1, r["doi"], r["title"], f"{first}{more}",
                int(r["year"]) if r["year"].isdigit() else r["year"],
                r["venue"], int(r["cited_by"] or 0), ""]
        for j, v in enumerate(vals, start=1):
            c = ws.cell(row=row, column=j, value=v)
            c.font = Font(size=10)
            c.alignment = top
            c.border = box
            if i % 2:
                c.fill = PatternFill("solid", fgColor=BAND)
        if r["doi"].strip():
            link = ws.cell(row=row, column=2)
            link.hyperlink = f"https://doi.org/{r['doi'].strip()}"
            link.font = Font(size=10, color="0563C1", underline="single")
        ws.row_dimensions[row].height = 30

    # A dropdown rather than a form-control checkbox. Real Excel checkboxes are
    # floating shapes: they do not survive a conversion to LibreOffice or Google
    # Sheets, they do not filter, and they are not attached to the row they sit
    # over. A validated cell ticks, filters and sorts with its row.
    from openpyxl.worksheet.datavalidation import DataValidation
    dv = DataValidation(type="list", formula1='"Yes,No - paywalled,Not found"',
                        allow_blank=True, showDropDown=False)
    dv.prompt = "Mark once retrieved"
    dv.promptTitle = "Downloaded"
    ws.add_data_validation(dv)
    dv.add(f"H5:H{4 + len(recs)}")

    # A running count, so progress is visible without scrolling 57 rows.
    tally = 4 + len(recs) + 2
    ws.cell(row=tally, column=6, value="Retrieved:").font = Font(bold=True, size=10)
    ws.cell(row=tally, column=7,
            value=f'=COUNTIF(H5:H{4 + len(recs)},"Yes")&" of {len(recs)}"'
            ).font = Font(bold=True, size=10)

    dest.parent.mkdir(parents=True, exist_ok=True)
    wb.save(dest)


def main(argv=None):
    p = argparse.ArgumentParser(description="List papers to request via subscription access")
    p.add_argument("--tier", default="T1")
    p.add_argument("--dois-only", action="store_true")
    p.add_argument("--xlsx", default="", help="write a workbook instead of text")
    p.add_argument("--out", default="")
    a = p.parse_args(argv)
    tiers = {t.strip().upper() for t in a.tier.split(",") if t.strip()}
    recs = needed(tiers)

    if a.xlsx:
        write_xlsx(recs, Path(a.xlsx), tiers)
        print(f"wrote {a.xlsx} — {len(recs)} papers")
        return 0

    if a.dois_only:
        text = "\n".join(r["doi"] for r in recs if r["doi"].strip())
    else:
        L = [f"Papers requested — {', '.join(sorted(tiers))} tier, "
             f"{len(recs)} items, ordered by citation count.",
             "Every entry has a DOI. Titles are for reference only.",
             ""]
        for i, r in enumerate(recs, 1):
            first = (r["authors"].split(";")[0] or "").strip()
            more = " et al." if ";" in r["authors"] else ""
            L.append(f"{i:>3}. {r['doi']}")
            L.append(f"     {r['title']}")
            bits = [b for b in (f"{first}{more}" if first else "",
                                r["year"], r["venue"][:60]) if b]
            L.append(f"     {' · '.join(bits)}")
            L.append("")
        text = "\n".join(L)

    if a.out:
        Path(a.out).write_text(text)
        print(f"wrote {a.out} — {len(recs)} papers")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
