"""exporter.py - turns invoice records into Excel, CSV or JSON files (returned as bytes)."""
import csv
import io
import json

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from extractor import AMOUNT_FIELDS

COLUMNS = [
    ("id", "ID"), ("filename", "Source file"), ("vendor_name", "Vendor"), ("vendor_gstin", "Vendor GSTIN"),
    ("invoice_number", "Invoice no."), ("invoice_date", "Invoice date"), ("due_date", "Due date"),
    ("buyer_name", "Buyer"), ("buyer_gstin", "Buyer GSTIN"), ("po_number", "PO number"), ("currency", "Currency"),
    ("subtotal", "Subtotal"), ("cgst", "CGST"), ("sgst", "SGST"), ("igst", "IGST"),
    ("total_tax", "Total tax"), ("total_amount", "Total"),
]


def _row(inv, corrections):
    """One flat row per invoice."""
    f = inv["data"]["fields"]
    row = []
    for key, _ in COLUMNS:
        if key == "id":
            row.append(inv["id"])
        elif key == "filename":
            row.append(inv["filename"])
        else:
            row.append(f[key]["value"])
    notes = "; ".join(w["message"] for w in inv["data"]["warnings"] if w["level"] in ("error", "warning"))
    row += [inv["status"], round((inv["overall_conf"] or 0) * 100), corrections.get(inv["id"], 0), notes]
    return row


HEADERS = [h for _, h in COLUMNS] + ["Status", "Confidence %", "Corrections", "Review notes"]


def export_csv(invoices, corrections):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HEADERS)
    for inv in invoices:
        w.writerow(_row(inv, corrections))
    return ("\ufeff" + buf.getvalue()).encode("utf-8")  # BOM so Excel reads UTF-8 correctly


def export_json(invoices):
    out = []
    for inv in invoices:
        out.append({
            "id": inv["id"], "filename": inv["filename"], "status": inv["status"],
            "confidence": inv["overall_conf"],
            "fields": {k: v["value"] for k, v in inv["data"]["fields"].items()},
            "field_details": inv["data"]["fields"],
            "line_items": inv["data"]["line_items"],
            "warnings": inv["data"]["warnings"],
        })
    return json.dumps(out, indent=2, ensure_ascii=False).encode("utf-8")


def export_xlsx(invoices, corrections):
    wb = Workbook()
    ws = wb.active
    ws.title = "Invoices"
    ws.append(HEADERS)
    for inv in invoices:
        ws.append(_row(inv, corrections))

    # styling: header row, number formats, widths, freeze panes
    head_fill = PatternFill("solid", fgColor="0B6B5D")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = head_fill
        cell.alignment = Alignment(vertical="center")
    amount_cols = [i + 1 for i, (k, _) in enumerate(COLUMNS) if k in AMOUNT_FIELDS]
    for row in ws.iter_rows(min_row=2):
        for c in amount_cols:
            row[c - 1].number_format = "#,##0.00"
    for i, col in enumerate(ws.columns, 1):
        longest = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[get_column_letter(i)].width = min(max(10, longest + 2), 45)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    # second sheet: line items, one row per item
    li = wb.create_sheet("Line items")
    li.append(["Invoice ID", "Invoice no.", "Description", "HSN/SAC", "Quantity", "Unit price", "Amount"])
    for inv in invoices:
        num = inv["data"]["fields"]["invoice_number"]["value"]
        for it in inv["data"]["line_items"]:
            li.append([inv["id"], num, it["description"], it["hsn"], it["quantity"], it["unit_price"], it["amount"]])
    for cell in li[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = head_fill
    for col, w in zip("ABCDEFG", (11, 16, 40, 10, 10, 12, 12)):
        li.column_dimensions[col].width = w
    li.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
