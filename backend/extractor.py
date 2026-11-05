"""
extractor.py - reads an invoice (PDF / image / TXT) and returns structured data.

Pipeline (kept deliberately simple):
  1. read_document()   -> plain text lines (PDF text layer, or OCR for scans/images)
  2. extract_fields()  -> rule-based extraction, every field has value + confidence + source
  3. validate()        -> maths checks (subtotal + tax = total), GSTIN format, dates, missing fields
"""
import os
import re
import shutil
import sys
from datetime import date, datetime

import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageOps

try:  # OpenCV is optional: it only improves OCR on poor scans
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover
    cv2 = None

# ---------------------------------------------------------------- Tesseract
# On Windows, Tesseract is usually not on PATH, so we look in the default folder.
if not shutil.which("tesseract") and sys.platform.startswith("win"):
    default_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(default_path):
        pytesseract.pytesseract.tesseract_cmd = default_path

SUPPORTED = {".pdf", ".png", ".jpg", ".jpeg", ".txt"}
REQUIRED_FIELDS = ["vendor_name", "invoice_number", "invoice_date", "total_amount"]
FIELD_ORDER = [
    "vendor_name", "vendor_gstin", "invoice_number", "invoice_date", "due_date",
    "buyer_name", "buyer_gstin", "po_number", "currency",
    "subtotal", "cgst", "sgst", "igst", "total_tax", "total_amount",
]
AMOUNT_FIELDS = ["subtotal", "cgst", "sgst", "igst", "total_tax", "total_amount"]


class ExtractionError(Exception):
    """Raised when a document cannot be read at all."""


# ================================================================ 1. READING
def _words_to_lines(page):
    """Rebuild text lines from word positions so table rows stay on one line."""
    words = page.get_text("words")
    rows = []  # each row: [y_center, [(x0, x1, text), ...]]
    for x0, y0, x1, y1, text, *_ in sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        yc = (y0 + y1) / 2
        if rows and abs(rows[-1][0] - yc) < 3:
            rows[-1][1].append((x0, x1, text))
        else:
            rows.append([yc, [(x0, x1, text)]])
    lines = []
    for _, items in rows:
        items.sort()
        out = items[0][2]
        for prev, cur in zip(items, items[1:]):
            out += ("   " if cur[0] - prev[1] > 12 else " ") + cur[2]  # wide gap = new column
        lines.append(out)
    return lines


def _preprocess(img):
    """Grayscale, upscale small images, remove noise, binarise. Improves OCR on scans."""
    img = ImageOps.exif_transpose(img).convert("L")
    if img.width < 1600:
        scale = 1600 / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    if cv2 is not None:
        arr = np.array(img)
        arr = cv2.fastNlMeansDenoising(arr, None, 10, 7, 21)
        arr = cv2.adaptiveThreshold(arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)
        return Image.fromarray(arr)
    return ImageOps.autocontrast(img)


def _ocr(img):
    """Run Tesseract. Returns (lines, mean_confidence 0-100)."""
    try:
        prepared = _preprocess(img)
        data = pytesseract.image_to_data(prepared, config="--psm 6", output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractNotFoundError:
        raise ExtractionError(
            "Tesseract OCR is not installed or not found. Install it (see README) to read scans and images."
        )
    confs = [float(c) for c, t in zip(data["conf"], data["text"]) if t.strip() and float(c) >= 0]
    # group words into lines using Tesseract's own block/paragraph/line numbers
    grouped = {}
    for i, t in enumerate(data["text"]):
        if t.strip():
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            grouped.setdefault(key, []).append(t)
    lines = [" ".join(words) for _, words in sorted(grouped.items())]
    return lines, (sum(confs) / len(confs) if confs else 0.0)


def read_document(path):
    """Return (lines, source, ocr_confidence). source is 'text' or 'ocr'."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED:
        raise ExtractionError(f"Unsupported file type '{ext}'. Upload PDF, PNG, JPG or TXT.")
    if os.path.getsize(path) == 0:
        raise ExtractionError("The file is empty.")

    if ext == ".txt":
        with open(path, encoding="utf-8", errors="ignore") as f:
            return [l.rstrip() for l in f.read().splitlines() if l.strip()], "text", 100.0

    if ext == ".pdf":
        try:
            doc = fitz.open(path)
        except Exception:
            raise ExtractionError("This PDF could not be opened. It may be damaged or password protected.")
        lines = []
        for page in doc:
            lines += _words_to_lines(page)
        if len("".join(lines)) >= 40:  # has a real text layer
            return lines, "text", 100.0
        # scanned PDF: render each page and OCR it
        lines, confs = [], []
        for page in doc:
            pix = page.get_pixmap(dpi=250)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            page_lines, conf = _ocr(img)
            lines += page_lines
            confs.append(conf)
        return lines, "ocr", (sum(confs) / len(confs) if confs else 0.0)

    try:  # PNG / JPG
        img = Image.open(path)
        img.load()
    except Exception:
        raise ExtractionError("This image could not be opened.")
    lines, conf = _ocr(img)
    return lines, "ocr", conf


# ================================================================ 2. PARSING HELPERS
def parse_amount(text):
    """'Rs. 1,25,000.00' -> 125000.0 ; '1.234,56' -> 1234.56 ; returns None if no number."""
    m = re.search(r"-?\d[\d,.\s]*\d|\d", text or "")
    if not m:
        return None
    s = m.group(0).replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".") if re.search(r",\d{2}$", s) and s.count(",") == 1 and len(s.split(",")[1]) != 3 else s.replace(",", "")
    try:
        return round(float(s), 2)
    except ValueError:
        return None


MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_date(text):
    """Return (iso_date, ambiguous). Day-first is assumed for numeric dates (Indian convention)."""
    t = (text or "").strip()
    m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", t)
    if m:
        return _safe_date(int(m[1]), int(m[2]), int(m[3])), False
    m = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", t)
    if m:
        a, b, y = int(m[1]), int(m[2]), int(m[3])
        y += 2000 if y < 100 else 0
        ambiguous = a <= 12 and b <= 12 and a != b
        if b > 12 >= a:  # clearly month-first (e.g. 03/25/2026)
            return _safe_date(y, a, b), False
        return _safe_date(y, b, a), ambiguous
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?[\s\-,]*([A-Za-z]{3,9})[\s\-,.]*(\d{4})", t)
    if m and m[2][:3].lower() in MONTHS:
        return _safe_date(int(m[3]), MONTHS[m[2][:3].lower()], int(m[1])), False
    m = re.search(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", t)
    if m and m[1][:3].lower() in MONTHS:
        return _safe_date(int(m[3]), MONTHS[m[1][:3].lower()], int(m[2])), False
    return None, False


def _safe_date(y, mth, d):
    try:
        return date(y, mth, d).isoformat()
    except ValueError:
        return None


def find_after(lines, labels, value_regex, start=0, last=False):
    """
    Find a line containing one of `labels` (regex) and return the value that follows it
    (on the same line, or at the start of the next line).
    Returns (value_text, line_text, line_index) or None.
    """
    hits = []
    pattern = re.compile("(?:" + "|".join(labels) + ")", re.I)
    for i in range(start, len(lines)):
        m = pattern.search(lines[i])
        if not m:
            continue
        rest = lines[i][m.end():]
        rest = re.sub(r"^[\s:.\-#=]+", "", rest)
        v = re.search(value_regex, rest)
        if not v and i + 1 < len(lines):
            v = re.search(r"^\s*" + value_regex, lines[i + 1])
            if v:
                hits.append((v.group(1) if v.groups() else v.group(0), lines[i] + " / " + lines[i + 1], i))
                continue
        if v:
            hits.append((v.group(1) if v.groups() else v.group(0), lines[i], i))
    if not hits:
        return None
    return hits[-1] if last else hits[0]


PCT = re.compile(r"\(?\s*@?\s*\d+(?:\.\d+)?\s*%\s*\)?")
NUM = r"((?:₹|rs\.?|inr|usd|eur|gbp|\$|€|£)?\s*-?\d[\d,]*(?:\.\d{1,2})?)"


def find_amount(lines, labels, last=True, exclude=None):
    """Amount following a label. Tax percentages like '@ 9%' are stripped first."""
    pattern = re.compile("(?:" + "|".join(labels) + ")", re.I)
    hits = []
    for i, line in enumerate(lines):
        m = pattern.search(line)
        if not m or (exclude and re.search(exclude, line, re.I)):
            continue
        rest = PCT.sub(" ", line[m.end():])
        nums = re.findall(NUM, rest, re.I)
        nums = [n for n in nums if re.search(r"\d", n)]
        if not nums and i + 1 < len(lines):  # amount on the next line
            nums = re.findall(NUM, PCT.sub(" ", lines[i + 1]), re.I)[:1]
            line = line + " / " + lines[i + 1]
        if nums:
            val = parse_amount(nums[-1])
            if val is not None:
                hits.append((val, line.strip(), i))
    if not hits:
        return None
    return hits[-1] if last else hits[0]


def fix_gstin(token):
    """Repair common OCR confusions (O/0, I/1, S/5, B/8, Z/2) using the fixed GSTIN pattern."""
    if len(token) != 15:
        return None
    to_digit = {"O": "0", "I": "1", "S": "5", "B": "8", "Z": "2", "L": "1"}
    to_alpha = {v: k for k, v in to_digit.items() if k != "L"}
    out = []
    for i, ch in enumerate(token.upper()):
        if i in (0, 1, 7, 8, 9, 10):
            out.append(to_digit.get(ch, ch))
        elif i in (2, 3, 4, 5, 6, 11):
            out.append(to_alpha.get(ch, ch))
        else:
            out.append(ch)
    fixed = "".join(out)
    return fixed if GSTIN_RE.fullmatch(fixed) else None


GSTIN_RE = re.compile(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z])\b")
COMPANY_WORDS = r"(pvt|private|ltd|limited|llp|llc|inc|corp|co\.|company|technologies|enterprises|traders|solutions|industries|services|systems|associates|agency|stores|works)"
SKIP_TOP = re.compile(r"^(tax\s+invoice|invoice|bill\s+of\s+supply|original|duplicate|page|cash\s+memo|proforma)", re.I)


def _next_text_line(lines, i):
    """First meaningful line after index i (skips empties and bare labels)."""
    for j in range(i + 1, min(i + 4, len(lines))):
        s = lines[j].strip()
        if len(s) > 2 and not re.match(r"^(gstin|address|phone|email|date)\b", s, re.I):
            return s, lines[j]
    return None, None


def _clean_name(s):
    s = re.split(r"\s{3,}|\s+GSTIN|\s+GST\s*No", s, flags=re.I)[0]
    return re.sub(r"^[\s:\-]+|[\s,;:]+$", "", s)


# ================================================================ 3. EXTRACTION
def make_field(value=None, conf=0.0, source="text", evidence=""):
    return {"value": value, "confidence": round(conf, 2), "source": source if value is not None else None,
            "evidence": evidence[:160], "status": "ok" if value is not None else "missing"}


def extract_fields(lines, source="text", ocr_conf=100.0):
    """Return (fields dict, line_items list, notes list)."""
    f = {k: make_field() for k in FIELD_ORDER}
    notes = []
    # OCR lowers trust in every field a little (scaled by Tesseract's own confidence)
    q = 1.0 if source == "text" else min(1.0, 0.55 + ocr_conf / 200)
    src = source

    def put(name, value, conf, evidence):
        f[name] = make_field(value, conf * q, src, evidence)

    # --- invoice number
    r = find_after(
        lines,
        [r"invoice\s*(?:number|no\.?|num|#|id)", r"inv\.?\s*(?:no\.?|#)", r"bill\s*(?:number|no\.?|#)", r"document\s*(?:no\.?|number)", r"tax\s+invoice\s+no\.?"],
        r"([A-Za-z0-9][A-Za-z0-9/\-_.]{2,})",
    )
    if r and re.search(r"\d", r[0]) and not parse_date(r[0])[0]:
        put("invoice_number", r[0].rstrip(".-"), 0.92, r[1])

    # --- dates
    r = find_after(lines, [r"invoice\s*date", r"date\s*of\s*issue", r"bill\s*date", r"dated", r"\bdate\b"],
                   r"(\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}|\d{1,2}(?:st|nd|rd|th)?[\s\-]+[A-Za-z]{3,9}[\s\-,.]+\d{4}|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4})")
    if r:
        iso, ambiguous = parse_date(r[0])
        if not iso:
            notes.append(("invoice_date", "warning", f"Found '{r[0]}' next to the invoice date label, but it is not a valid date. Check the invoice."))
        if iso:
            put("invoice_date", iso, 0.9 if not ambiguous else 0.6, r[1])
            if ambiguous:
                f["invoice_date"]["status"] = "warning"
                notes.append(("invoice_date", "warning", f"Date '{r[0]}' could be DD/MM or MM/DD. Read as day-first; please check."))
    r = find_after(lines, [r"due\s*date", r"payment\s*due", r"due\s*on", r"pay\s*by"],
                   r"(\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}|\d{1,2}(?:st|nd|rd|th)?[\s\-]+[A-Za-z]{3,9}[\s\-,.]+\d{4}|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4})")
    if r:
        iso, _ = parse_date(r[0])
        if iso:
            put("due_date", iso, 0.85, r[1])

    # --- PO number
    r = find_after(lines, [r"p\.?o\.?\s*(?:number|no\.?|#)", r"purchase\s*order(?:\s*(?:no\.?|number|#))?", r"order\s*(?:no\.?|number)"],
                   r"([A-Za-z0-9][A-Za-z0-9/\-_.]{2,})")
    if r and re.search(r"\d", r[0]):
        put("po_number", r[0].rstrip(".-"), 0.8, r[1])

    # --- GSTINs (first = seller unless a buyer keyword is above it)
    gst_hits = []
    for i, line in enumerate(lines):
        found = GSTIN_RE.findall(line.upper())
        if not found and source == "ocr":  # try to repair OCR mistakes in 15-character tokens
            for tok in re.findall(r"\b[A-Z0-9]{15}\b", line.upper()):
                fixed = fix_gstin(tok)
                if fixed:
                    found.append(fixed)
        for g in found:
            gst_hits.append((g, i, line))
    seller_idx = buyer_idx = None
    for i, line in enumerate(lines):
        if re.search(r"bill(?:ed)?\s*to|buyer|customer|consignee|recipient", line, re.I) and buyer_idx is None:
            buyer_idx = i
        if re.search(r"seller|supplier|vendor|sold\s*by|billed\s*by|from\b", line, re.I) and seller_idx is None:
            seller_idx = i
    for g, i, line in gst_hits:
        is_buyer = buyer_idx is not None and i >= buyer_idx and (seller_idx is None or buyer_idx > seller_idx or i > buyer_idx)
        if buyer_idx is None and f["vendor_gstin"]["value"]:
            is_buyer = True
        name = "buyer_gstin" if is_buyer else "vendor_gstin"
        if f[name]["value"] is None:
            put(name, g, 0.9, line)

    # --- vendor name
    r = find_after(lines, [r"seller", r"supplier", r"vendor", r"sold\s*by", r"billed\s*by", r"from"], r"(\S.*)")
    vendor = None
    if r:
        txt = _clean_name(r[0])
        if len(txt) < 3 or txt.endswith(":"):
            nxt, ln = _next_text_line(lines, r[2])
            txt = _clean_name(nxt) if nxt else ""
        if len(txt) >= 3 and not GSTIN_RE.search(txt):
            vendor = (txt, 0.8, r[1])
    if not vendor:
        for line in lines[:8]:
            s = _clean_name(line.strip())
            if len(s) < 3 or SKIP_TOP.match(s) or not re.search(r"[A-Za-z]{3}", s) or parse_date(s)[0]:
                continue
            vendor = (s, 0.85 if re.search(COMPANY_WORDS, s, re.I) else 0.6, line)
            break
    if vendor:
        put("vendor_name", *vendor)

    # --- buyer name
    r = find_after(lines, [r"bill(?:ed)?\s*to", r"buyer", r"customer\s*name", r"customer", r"sold\s*to", r"consignee"], r"(\S.*)")
    if r:
        txt = _clean_name(r[0])
        if len(txt) < 3 or txt.endswith(":"):
            nxt, _ = _next_text_line(lines, r[2])
            txt = _clean_name(nxt) if nxt else ""
        if len(txt) >= 3 and not GSTIN_RE.search(txt):
            put("buyer_name", txt, 0.75, r[1])

    # --- currency
    blob = "\n".join(lines)
    cur = None
    if re.search(r"₹|\brs\.?\s*\d|\binr\b", blob, re.I):
        cur = "INR"
    elif re.search(r"\$|\busd\b", blob, re.I):
        cur = "USD"
    elif re.search(r"€|\beur\b", blob, re.I):
        cur = "EUR"
    elif re.search(r"£|\bgbp\b", blob, re.I):
        cur = "GBP"
    elif f["vendor_gstin"]["value"]:
        cur = "INR"
    if cur:
        put("currency", cur, 0.8, "currency symbol in document")

    # --- amounts
    tax_excl = r"taxable|sub\s*total|total\s*(?:tax|gst|vat)"
    spec = {
        "subtotal": ([r"sub\s*-?\s*total", r"taxable\s*(?:value|amount)", r"amount\s*before\s*(?:tax|gst)", r"total\s*before\s*(?:tax|gst)", r"net\s*amount"], 0.88, False),
        "cgst": ([r"c\.?gst"], 0.92, True),
        "sgst": ([r"s\.?gst", r"utgst"], 0.92, True),
        "igst": ([r"i\.?gst"], 0.92, True),
        "total_tax": ([r"total\s*(?:tax|gst|vat)(?:\s*amount)?", r"tax\s*total", r"(?:gst|vat|sales\s*tax)\s*amount", r"\bvat\b", r"\bsales\s*tax\b"], 0.85, True),
    }
    for name, (labels, conf, last) in spec.items():
        ex = r"total\s*(?:tax|gst|vat)" if name in ("cgst", "sgst", "igst") else None
        r = find_amount(lines, labels, last=last, exclude=ex)
        if r and not (name == "subtotal" and re.search(r"total\s*(tax|gst)", r[1], re.I)):
            put(name, r[0], conf, r[1])

    r = find_amount(lines, [r"grand\s*total", r"total\s*amount\s*(?:due|payable)?", r"amount\s*(?:due|payable)", r"balance\s*due", r"total\s*due", r"net\s*payable", r"invoice\s*total", r"total\s*invoice\s*value", r"total\s*payable"],
                    exclude=r"words|in\s*words|before|tax|gst|vat")
    if r:
        put("total_amount", r[0], 0.92, r[1])
    else:  # fallback: a line that starts with the word 'total'
        r = find_amount(lines, [r"^\s*total\b"], exclude=r"sub|tax|gst|vat|qty|quantity")
        if r:
            put("total_amount", r[0], 0.7, r[1])

    items = extract_line_items(lines)
    return f, items, notes


ROW_RE = re.compile(r"^\s*(?:\d{1,3}[.)]?\s+)?(?P<desc>[A-Za-z].*?)\s+(?:(?P<hsn>\d{4,8})\s+)?(?P<qty>\d+(?:\.\d+)?)\s+(?:\w{0,5}\s+)?(?P<rate>[\d,]+(?:\.\d{1,2})?)\s+(?P<amt>[\d,]+(?:\.\d{1,2})?)\s*$")


def extract_line_items(lines):
    """Best-effort table reader: header row with description + qty + amount, then rows until totals."""
    items, in_table = [], False
    for line in lines:
        low = line.lower()
        if not in_table:
            if re.search(r"description|item|particulars", low) and re.search(r"qty|quantity", low) and re.search(r"amount|total|price|rate", low):
                in_table = True
            continue
        if re.search(r"sub\s*total|taxable|^\s*total|grand\s*total|cgst|sgst|igst", low):
            break
        clean = re.sub(r"₹|\$|€|£|\bRs\.?|\bINR\b", "", line)
        clean = re.sub(r"^[^\w(]+|[\s,._;|]+$", "", clean)  # OCR junk at both ends
        m = ROW_RE.match(clean)
        if m:
            items.append({
                "description": m["desc"].strip(),
                "hsn": m["hsn"] or "",
                "quantity": parse_amount(m["qty"]),
                "unit_price": parse_amount(m["rate"]),
                "amount": parse_amount(m["amt"]),
            })
    return items


# ================================================================ 4. VALIDATION
def validate(fields, items, notes):
    """Fill calculated values, add warnings, and decide the review status."""
    v = lambda k: fields[k]["value"]
    warnings = [{"field": n, "level": l, "message": m} for n, l, m in notes]

    def warn(field, level, message):
        warnings.append({"field": field, "level": level, "message": message})
        if level in ("error", "warning") and fields.get(field, {}).get("status") == "ok":
            fields[field]["status"] = "warning"

    def calc(field, value, why):
        fields[field] = {"value": round(value, 2), "confidence": 0.7, "source": "calculated",
                         "evidence": why, "status": "calculated"}

    # missing required fields
    for k in REQUIRED_FIELDS:
        if v(k) is None:
            warnings.append({"field": k, "level": "error", "message": f"{k.replace('_', ' ').capitalize()} was not found. Enter it manually."})

    # calculated values
    split_tax = sum(v(k) or 0 for k in ("cgst", "sgst", "igst"))
    if v("total_tax") is None and split_tax:
        calc("total_tax", split_tax, "CGST + SGST + IGST")
    tax = v("total_tax") if v("total_tax") is not None else split_tax
    if v("total_amount") is None and v("subtotal") is not None and tax is not None:
        calc("total_amount", v("subtotal") + tax, "Subtotal + tax")
        warnings.append({"field": "total_amount", "level": "warning", "message": "Total was not printed on the invoice. It was calculated from subtotal and tax."})
    if v("subtotal") is None and v("total_amount") is not None and tax:
        calc("subtotal", v("total_amount") - tax, "Total - tax")
    if v("subtotal") is None and items:
        calc("subtotal", sum(i["amount"] or 0 for i in items), "Sum of line items")

    # arithmetic checks
    if v("subtotal") is not None and v("total_amount") is not None:
        expected = round(v("subtotal") + (tax or 0), 2)
        if abs(expected - v("total_amount")) > max(1.0, 0.005 * v("total_amount")):
            warn("total_amount", "error", f"Subtotal + tax = {expected:,.2f}, but total on invoice is {v('total_amount'):,.2f}.")
    if v("cgst") is not None and v("sgst") is not None and abs(v("cgst") - v("sgst")) > 0.5:
        warn("sgst", "warning", "CGST and SGST are normally equal, but here they differ.")
    if v("igst") and (v("cgst") or v("sgst")):
        warn("igst", "warning", "Both IGST and CGST/SGST were found. An invoice normally has only one type.")
    if items and v("subtotal") is not None:
        s = sum(i["amount"] or 0 for i in items)
        if abs(s - v("subtotal")) > max(1.0, 0.005 * v("subtotal")):
            warn("subtotal", "warning", f"Line items add up to {s:,.2f}, but subtotal is {v('subtotal'):,.2f}.")

    # GSTIN format (state code 01-38)
    for k in ("vendor_gstin", "buyer_gstin"):
        g = v(k)
        if g and not (GSTIN_RE.fullmatch(g) and 1 <= int(g[:2]) <= 38):
            warn(k, "warning", "GSTIN format looks invalid.")

    # dates
    inv, due = v("invoice_date"), v("due_date")
    if inv and inv > date.today().isoformat():
        warn("invoice_date", "warning", "Invoice date is in the future.")
    if inv and due and due < inv:
        warn("due_date", "warning", "Due date is before the invoice date.")

    # low confidence
    for k in FIELD_ORDER:
        fd = fields[k]
        if fd["value"] is not None and fd["confidence"] < 0.6 and fd["status"] == "ok":
            fd["status"] = "warning"
            warnings.append({"field": k, "level": "info", "message": f"Low confidence ({int(fd['confidence'] * 100)}%). Please check this value."})

    # overall confidence: average of required fields, missing counts as zero
    overall = sum(fields[k]["confidence"] for k in REQUIRED_FIELDS) / len(REQUIRED_FIELDS)
    has_error = any(w["level"] == "error" for w in warnings)
    needs_review = has_error or overall < 0.75 or any(w["level"] == "warning" for w in warnings)
    return warnings, round(overall, 2), ("needs_review" if needs_review else "ready")


# ================================================================ 5. PUBLIC FUNCTION
def extract_invoice(path):
    """Main entry point. Returns a dict ready to be stored and sent to the frontend."""
    lines, source, ocr_conf = read_document(path)
    if len(" ".join(lines).strip()) < 20:
        raise ExtractionError("No readable text was found. The image may be blurry or too dark. Try a clearer scan.")
    fields, items, notes = extract_fields(lines, source, ocr_conf)
    if all(fields[k]["value"] is None for k in ("invoice_number", "invoice_date", "total_amount")):
        raise ExtractionError("This does not look like an invoice, or the text could not be read. No invoice fields were found.")
    warnings, overall, status = validate(fields, items, notes)
    return {
        "fields": fields, "line_items": items, "warnings": warnings,
        "overall_confidence": overall, "status": status,
        "source": source, "ocr_confidence": round(ocr_conf, 1),
        "raw_text": "\n".join(lines),
    }
