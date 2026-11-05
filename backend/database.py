"""
database.py - all SQL lives here, using Python's built-in sqlite3 (no ORM, easy to read).

Tables
  invoices     one row per uploaded file. `original_json` is what the extractor found and is never
               changed; `data_json` holds the current (possibly corrected) values.
  corrections  one row per field the user changed, with original and corrected value side by side.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("INVOICE_DATA_DIR") or os.path.join(BASE_DIR, "data")  # env var is used by test_api.py
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "invoices.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    filename         TEXT NOT NULL,
    stored_name      TEXT NOT NULL,
    file_hash        TEXT NOT NULL,
    uploaded_at      TEXT NOT NULL,
    reviewed_at      TEXT,
    status           TEXT NOT NULL,          -- ready | needs_review | reviewed | failed
    error            TEXT,
    source           TEXT,                   -- text | ocr
    overall_conf     REAL,
    processing_ms    INTEGER,
    duplicate_of     INTEGER,
    -- searchable copies of the current values
    vendor_name      TEXT,
    invoice_number   TEXT,
    invoice_date     TEXT,
    currency         TEXT,
    total_amount     REAL,
    -- full data
    original_json    TEXT,
    data_json        TEXT,
    warnings_json    TEXT,
    raw_text         TEXT
);
CREATE TABLE IF NOT EXISTS corrections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id      INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    field           TEXT NOT NULL,
    original_value  TEXT,
    corrected_value TEXT,
    corrected_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(invoice_date);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)


def row_to_dict(row, full=True):
    """Convert a DB row to the JSON shape the frontend uses."""
    d = dict(row)
    for key in ("original_json", "data_json", "warnings_json"):
        raw = d.pop(key, None)
        d[key.replace("_json", "")] = json.loads(raw) if raw else None
    if not full:
        d.pop("raw_text", None)
        d.pop("original", None)
        d.pop("data", None)
        d.pop("warnings", None)
    return d


def find_duplicate(conn, file_hash, vendor, number, exclude_id=None):
    """Same file, or same vendor + invoice number, already stored."""
    q_ex = " AND id != ?" if exclude_id else ""
    args_ex = (exclude_id,) if exclude_id else ()
    row = conn.execute(f"SELECT id FROM invoices WHERE file_hash = ? AND status != 'failed'{q_ex} ORDER BY id LIMIT 1",
                       (file_hash, *args_ex)).fetchone()
    if row:
        return row["id"], "same file"
    if vendor and number:
        row = conn.execute(
            f"SELECT id FROM invoices WHERE lower(vendor_name) = lower(?) AND invoice_number = ? AND status != 'failed'{q_ex} ORDER BY id LIMIT 1",
            (vendor, number, *args_ex)).fetchone()
        if row:
            return row["id"], "same vendor and invoice number"
    return None, None


def build_filters(search="", status="", date_from="", date_to=""):
    where, args = ["1=1"], []
    if search:
        where.append("(vendor_name LIKE ? OR invoice_number LIKE ? OR filename LIKE ?)")
        args += [f"%{search}%"] * 3
    if status:
        where.append("status = ?")
        args.append(status)
    if date_from:
        where.append("invoice_date >= ?")
        args.append(date_from)
    if date_to:
        where.append("invoice_date <= ?")
        args.append(date_to)
    return " AND ".join(where), args


def stats(conn):
    """Numbers for the dashboard. Invoices flagged as duplicates are left out of value totals."""
    one = lambda q, a=(): conn.execute(q, a).fetchone()[0]
    by_status = {r["status"]: r["n"] for r in conn.execute("SELECT status, COUNT(*) n FROM invoices GROUP BY status")}
    monthly = [dict(r) for r in conn.execute(
        """SELECT substr(invoice_date, 1, 7) AS month, ROUND(SUM(total_amount), 2) AS total, COUNT(*) AS count
           FROM invoices WHERE invoice_date IS NOT NULL AND status != 'failed' AND duplicate_of IS NULL
           GROUP BY month ORDER BY month DESC LIMIT 12""")][::-1]
    vendors = [dict(r) for r in conn.execute(
        """SELECT vendor_name AS vendor, ROUND(SUM(total_amount), 2) AS total FROM invoices
           WHERE vendor_name IS NOT NULL AND status != 'failed' AND duplicate_of IS NULL GROUP BY lower(vendor_name)
           ORDER BY total DESC LIMIT 5""")]
    return {
        "total": one("SELECT COUNT(*) FROM invoices"),
        "needs_review": by_status.get("needs_review", 0),
        "ready": by_status.get("ready", 0),
        "reviewed": by_status.get("reviewed", 0),
        "failed": by_status.get("failed", 0),
        "total_value": one("SELECT COALESCE(ROUND(SUM(total_amount), 2), 0) FROM invoices WHERE status != 'failed' AND duplicate_of IS NULL"),
        "avg_confidence": one("SELECT COALESCE(ROUND(AVG(overall_conf), 2), 0) FROM invoices WHERE status != 'failed'"),
        "corrections": one("SELECT COUNT(*) FROM corrections"),
        "by_status": by_status, "monthly": monthly, "top_vendors": vendors,
    }
