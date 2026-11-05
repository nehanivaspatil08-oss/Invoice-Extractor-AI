"""
main.py - FastAPI application. Run with:  uvicorn main:app --reload
Interactive API docs (Swagger UI) are available at http://127.0.0.1:8000/docs
"""
import hashlib
import io
import json
import os
import time
import uuid
from typing import Dict, List, Optional, Union

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
import fitz  # PyMuPDF, used to draw PDF pages for the preview
from pydantic import BaseModel

import database as db
from exporter import export_csv, export_json, export_xlsx
from extractor import (AMOUNT_FIELDS, FIELD_ORDER, SUPPORTED, ExtractionError,
                       extract_invoice, parse_date, validate)

MAX_UPLOAD_MB = 15
MEDIA_TYPES = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
               ".jpeg": "image/jpeg", ".txt": "text/plain"}

app = FastAPI(title="Invoice Extractor AI", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup():
    db.init_db()


# ------------------------------------------------------------------ request models
class LineItem(BaseModel):
    description: str = ""
    hsn: str = ""
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None


class InvoiceUpdate(BaseModel):
    fields: Dict[str, Union[str, float, None]]
    line_items: Optional[List[LineItem]] = None


# ------------------------------------------------------------------ helpers
def save_record(conn, rec_id, data, status=None):
    """Write the current values of an invoice back to the searchable columns."""
    f = data["fields"]
    conn.execute(
        """UPDATE invoices SET vendor_name=?, invoice_number=?, invoice_date=?, currency=?, total_amount=?,
           data_json=?, warnings_json=?, overall_conf=?, status=COALESCE(?, status) WHERE id=?""",
        (f["vendor_name"]["value"], f["invoice_number"]["value"], f["invoice_date"]["value"],
         f["currency"]["value"], f["total_amount"]["value"], json.dumps(data),
         json.dumps(data["warnings"]), data["overall_confidence"], status, rec_id))


def get_or_404(conn, invoice_id):
    row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Invoice not found")
    return row



def with_pages(inv):
    """Add the number of PDF pages so the frontend knows how many preview images to request."""
    inv["page_count"] = 0
    if inv["stored_name"].lower().endswith(".pdf"):
        try:
            inv["page_count"] = fitz.open(os.path.join(db.UPLOAD_DIR, inv["stored_name"])).page_count
        except Exception:
            pass
    return inv

def filters(search, status, date_from, date_to):
    return db.build_filters(search, status, date_from, date_to)


# ------------------------------------------------------------------ routes
@app.post("/api/extract")
def extract(file: UploadFile = File(...)):
    """Upload one invoice. It is stored, extracted, validated and saved. Returns the full record."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in SUPPORTED:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Upload PDF, PNG, JPG or TXT.")
    content = file.file.read()
    if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {MAX_UPLOAD_MB} MB.")

    stored_name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(db.UPLOAD_DIR, stored_name)
    with open(path, "wb") as out:
        out.write(content)
    file_hash = hashlib.sha256(content).hexdigest()

    started = time.time()
    try:
        data = extract_invoice(path)
        error = None
    except ExtractionError as e:
        data, error = None, str(e)
    except Exception as e:  # never let one bad file crash the server
        data, error = None, f"Unexpected error while reading this file: {e}"
    ms = int((time.time() - started) * 1000)

    with db.connect() as conn:
        cur = conn.execute(
            """INSERT INTO invoices (filename, stored_name, file_hash, uploaded_at, status, error, source, processing_ms)
               VALUES (?,?,?,?,?,?,?,?)""",
            (file.filename, stored_name, file_hash, db.now(), "failed" if error else data["status"],
             error, data["source"] if data else None, ms))
        rec_id = cur.lastrowid
        if data:
            f = data["fields"]
            dup_id, why = db.find_duplicate(conn, file_hash, f["vendor_name"]["value"], f["invoice_number"]["value"], rec_id)
            if dup_id:
                data["warnings"].append({"field": "invoice_number", "level": "warning",
                                         "message": f"Possible duplicate of invoice #{dup_id} ({why})."})
                data["status"] = "needs_review"
                conn.execute("UPDATE invoices SET duplicate_of=? WHERE id=?", (dup_id, rec_id))
            conn.execute("UPDATE invoices SET original_json=?, raw_text=? WHERE id=?",
                         (json.dumps({"fields": {k: v["value"] for k, v in f.items()},
                                      "line_items": data["line_items"]}), data["raw_text"], rec_id))
            save_record(conn, rec_id, data, data["status"])
        return with_pages(db.row_to_dict(get_or_404(conn, rec_id)))


@app.get("/api/invoices")
def list_invoices(search: str = "", status: str = "", date_from: str = "", date_to: str = "",
                  limit: int = Query(200, le=1000)):
    where, args = filters(search, status, date_from, date_to)
    with db.connect() as conn:
        rows = conn.execute(f"SELECT * FROM invoices WHERE {where} ORDER BY id DESC LIMIT ?", (*args, limit)).fetchall()
        return [db.row_to_dict(r, full=False) for r in rows]


@app.get("/api/invoices/{invoice_id}")
def get_invoice(invoice_id: int):
    with db.connect() as conn:
        inv = with_pages(db.row_to_dict(get_or_404(conn, invoice_id)))
        inv["corrections"] = [dict(r) for r in conn.execute(
            "SELECT field, original_value, corrected_value, corrected_at FROM corrections WHERE invoice_id=? ORDER BY id", (invoice_id,))]
        return inv


@app.put("/api/invoices/{invoice_id}")
def update_invoice(invoice_id: int, body: InvoiceUpdate):
    """Save the user's corrections. Original values stay untouched; every change goes to `corrections`."""
    with db.connect() as conn:
        row = get_or_404(conn, invoice_id)
        if row["status"] == "failed":
            raise HTTPException(400, "A failed extraction cannot be edited. Upload the file again.")
        data = json.loads(row["data_json"])
        original = json.loads(row["original_json"])

        for name, raw in body.fields.items():
            if name not in FIELD_ORDER:
                raise HTTPException(422, f"Unknown field '{name}'")
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                value = None
            elif name in AMOUNT_FIELDS:
                try:
                    value = round(float(str(raw).replace(",", "")), 2)
                except ValueError:
                    raise HTTPException(422, f"'{name}' must be a number")
            elif name in ("invoice_date", "due_date"):
                value = parse_date(str(raw))[0]
                if value is None:
                    raise HTTPException(422, f"'{name}' must be a valid date (YYYY-MM-DD)")
            else:
                value = str(raw).strip()
                if name.endswith("gstin"):
                    value = value.upper()
            fd = data["fields"][name]
            if value != fd["value"]:
                fd.update(value=value, confidence=1.0 if value is not None else 0.0,
                          source="manual" if value is not None else None,
                          status="edited" if value is not None else "missing", evidence="Entered by user")

        if body.line_items is not None:
            data["line_items"] = [i.model_dump() for i in body.line_items]

        # re-run the checks on the corrected values
        fields = data["fields"]
        for k in AMOUNT_FIELDS:  # a previously calculated value is real data now
            if fields[k]["status"] == "calculated":
                fields[k]["status"] = "ok"
        data["warnings"], data["overall_confidence"], _ = validate(fields, data["line_items"], [])
        dup_id, why = db.find_duplicate(conn, row["file_hash"], fields["vendor_name"]["value"],
                                        fields["invoice_number"]["value"], invoice_id)
        if dup_id:
            data["warnings"].append({"field": "invoice_number", "level": "warning",
                                     "message": f"Possible duplicate of invoice #{dup_id} ({why})."})

        # correction log: compare the current values with the ORIGINAL extraction
        conn.execute("DELETE FROM corrections WHERE invoice_id = ?", (invoice_id,))
        stamp = db.now()
        for name in FIELD_ORDER:
            before, after = original["fields"].get(name), fields[name]["value"]
            if before != after:
                conn.execute("INSERT INTO corrections (invoice_id, field, original_value, corrected_value, corrected_at) VALUES (?,?,?,?,?)",
                             (invoice_id, name, None if before is None else str(before), None if after is None else str(after), stamp))
        save_record(conn, invoice_id, data, "reviewed")
        conn.execute("UPDATE invoices SET reviewed_at=?, duplicate_of=? WHERE id=?", (stamp, dup_id, invoice_id))
    # read back AFTER the transaction above has been committed
    return get_invoice(invoice_id)


@app.delete("/api/invoices/{invoice_id}")
def delete_invoice(invoice_id: int):
    with db.connect() as conn:
        row = get_or_404(conn, invoice_id)
        conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
    try:
        os.remove(os.path.join(db.UPLOAD_DIR, row["stored_name"]))
    except OSError:
        pass
    return {"deleted": invoice_id}


@app.get("/api/invoices/{invoice_id}/file")
def get_file(invoice_id: int):
    """The original uploaded file, shown next to the extracted values."""
    with db.connect() as conn:
        row = get_or_404(conn, invoice_id)
    path = os.path.join(db.UPLOAD_DIR, row["stored_name"])
    if not os.path.exists(path):
        raise HTTPException(404, "Original file no longer exists")
    ext = os.path.splitext(row["stored_name"])[1]
    return FileResponse(path, media_type=MEDIA_TYPES.get(ext, "application/octet-stream"),
                        headers={"Content-Disposition": f'inline; filename="{row["filename"]}"'})


@app.get("/api/invoices/{invoice_id}/page/{page}")
def get_page_image(invoice_id: int, page: int):
    """One page of a PDF drawn as a PNG. Works in every browser, unlike embedding the PDF viewer."""
    with db.connect() as conn:
        row = get_or_404(conn, invoice_id)
    path = os.path.join(db.UPLOAD_DIR, row["stored_name"])
    if not row["stored_name"].lower().endswith(".pdf") or not os.path.exists(path):
        raise HTTPException(404, "No page preview for this file")
    doc = fitz.open(path)
    if not 0 <= page < doc.page_count:
        raise HTTPException(404, "Page not found")
    png = doc[page].get_pixmap(dpi=130).tobytes("png")
    return Response(png, media_type="image/png")


@app.get("/api/stats")
def get_stats():
    with db.connect() as conn:
        return db.stats(conn)


@app.get("/api/export")
def export(format: str = "xlsx", search: str = "", status: str = "", date_from: str = "", date_to: str = ""):
    """Export the invoices that match the current filters as xlsx, csv or json."""
    where, args = filters(search, status, date_from, date_to)
    with db.connect() as conn:
        rows = [db.row_to_dict(r) for r in conn.execute(
            f"SELECT * FROM invoices WHERE {where} AND status != 'failed' ORDER BY id", args)]
        corr = {}
        for r in conn.execute("SELECT invoice_id, COUNT(*) n FROM corrections GROUP BY invoice_id"):
            corr[r["invoice_id"]] = r["n"]
    if format == "xlsx":
        body, media = export_xlsx(rows, corr), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif format == "csv":
        body, media = export_csv(rows, corr), "text/csv"
    elif format == "json":
        body, media = export_json(rows), "application/json"
    else:
        raise HTTPException(400, "format must be xlsx, csv or json")
    return Response(body, media_type=media, headers={"Content-Disposition": f'attachment; filename="invoices.{format}"'})
