"""
test_api.py - end-to-end check of the backend using the sample files.
Run:  python make_samples.py   (once)   then   python test_api.py
Uses a temporary database, so your real data is never touched.
"""
import glob
import io
import os
import tempfile
import warnings

warnings.filterwarnings("ignore")
os.environ["INVOICE_DATA_DIR"] = tempfile.mkdtemp()

from fastapi.testclient import TestClient  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

import main  # noqa: E402

passed = 0


def check(name, condition):
    global passed
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        raise SystemExit(1)
    passed += 1


with TestClient(main.app) as c:
    samples = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "samples", "*")))
    check("sample files exist (run make_samples.py)", len(samples) >= 6)

    ids = {}
    for path in samples:
        name = os.path.basename(path)
        with open(path, "rb") as f:
            r = c.post("/api/extract", files={"file": (name, f)})
        check(f"upload {name} -> HTTP 200", r.status_code == 200)
        ids[name] = r.json()

    gst = ids["01_gst_invoice.pdf"]
    f = gst["data"]["fields"]
    check("GST invoice: vendor, number, date, total", (f["vendor_name"]["value"], f["invoice_number"]["value"], f["invoice_date"]["value"], f["total_amount"]["value"]) == ("Sunrise Technologies Pvt Ltd", "SRT/2026/0147", "2026-03-15", 59590.0))
    check("GST invoice: 3 line items and status ready", len(gst["data"]["line_items"]) == 3 and gst["status"] == "ready")
    check("IGST invoice: lakh-format amounts", ids["02_igst_invoice.pdf"]["data"]["fields"]["total_amount"]["value"] == 147500.0)
    check("USD invoice: currency and US date", ids["03_usd_invoice.pdf"]["data"]["fields"]["currency"]["value"] == "USD" and ids["03_usd_invoice.pdf"]["data"]["fields"]["invoice_date"]["value"] == "2026-03-05")
    bad = ids["04_wrong_total_missing_date.pdf"]
    check("wrong total + missing date -> needs_review with warnings", bad["status"] == "needs_review" and len(bad["data"]["warnings"]) >= 2)
    check("scanned image read with OCR", ids["05_scanned_photo.jpg"]["source"] == "ocr" and ids["05_scanned_photo.jpg"]["data"]["fields"]["total_amount"]["value"] == 59590.0)
    check("not-an-invoice file -> failed with message", ids["07_not_an_invoice.txt"]["status"] == "failed" and ids["07_not_an_invoice.txt"]["error"])

    # unsupported type
    r = c.post("/api/extract", files={"file": ("x.exe", io.BytesIO(b"abc"))})
    check("unsupported file type -> HTTP 400", r.status_code == 400)

    # duplicate detection
    with open(os.path.join(os.path.dirname(__file__), "samples", "01_gst_invoice.pdf"), "rb") as fh:
        dup = c.post("/api/extract", files={"file": ("copy.pdf", fh)}).json()
    check("duplicate upload is flagged", dup["duplicate_of"] == gst["id"] and any("duplicate" in w["message"].lower() for w in dup["data"]["warnings"]))

    # list + filters
    check("list all", len(c.get("/api/invoices").json()) == len(samples) + 1)
    check("filter by status=failed", all(i["status"] == "failed" for i in c.get("/api/invoices?status=failed").json()))
    check("search by vendor", [i["id"] for i in c.get("/api/invoices?search=Greenfield").json()] == [ids["02_igst_invoice.pdf"]["id"]])
    check("filter by date range", len(c.get("/api/invoices?date_from=2026-04-01&date_to=2026-04-30").json()) == 1)

    # edit: fix the missing date and total, check original is preserved and corrections are logged
    r = c.put(f"/api/invoices/{bad['id']}", json={"fields": {"invoice_date": "2026-05-10", "total_amount": 9440}})
    out = r.json()
    check("edit saves and marks reviewed", r.status_code == 200 and out["status"] == "reviewed")
    check("original extraction is preserved", out["original"]["fields"]["total_amount"] == 9720.0 and out["data"]["fields"]["total_amount"]["value"] == 9440.0)
    check("corrections logged (date + total)", {x["field"] for x in out["corrections"]} == {"invoice_date", "total_amount"})
    check("warnings cleared after fixing", not [w for w in out["data"]["warnings"] if w["level"] == "error"])
    check("bad number -> 422", c.put(f"/api/invoices/{bad['id']}", json={"fields": {"subtotal": "abc"}}).status_code == 422)

    # preview file
    r = c.get(f"/api/invoices/{gst['id']}/file")
    check("original file served for preview", r.status_code == 200 and r.headers["content-type"] == "application/pdf")

    r = c.get(f"/api/invoices/{gst['id']}/page/0")
    check("PDF page preview is a PNG image", r.status_code == 200 and r.content[:4] == b"\x89PNG" and gst["page_count"] == 1)
    check("page preview 404 for out-of-range page", c.get(f"/api/invoices/{gst['id']}/page/5").status_code == 404)

    # stats
    s = c.get("/api/stats").json()
    check("stats counts", s["total"] == len(samples) + 1 and s["failed"] == 1 and s["reviewed"] == 1 and len(s["monthly"]) >= 2)

    # exports
    x = c.get("/api/export?format=xlsx")
    wb = load_workbook(io.BytesIO(x.content))
    check("xlsx export has Invoices + Line items sheets", wb.sheetnames == ["Invoices", "Line items"] and wb["Invoices"].max_row > 3)
    check("csv export", c.get("/api/export?format=csv").text.count("\n") > 3)
    check("json export", isinstance(c.get("/api/export?format=json").json(), list))
    check("export respects filters", len(c.get("/api/export?format=json&search=Greenfield").json()) == 1)

    # delete
    check("delete invoice", c.delete(f"/api/invoices/{dup['id']}").status_code == 200 and c.get(f"/api/invoices/{dup['id']}").status_code == 404)

print(f"\nAll {passed} checks passed.")
