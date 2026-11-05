"""
make_samples.py - creates DUMMY invoices (fictional companies) in backend/samples/ for testing.
Run:  python make_samples.py
"""
import os
import random

import fitz
from PIL import Image, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
os.makedirs(OUT, exist_ok=True)


def make_pdf(name, rows):
    """rows: list of (y, [(x, text), ...], fontsize, bold)"""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    for y, cells, size, bold in rows:
        for x, text in cells:
            page.insert_text((x, y), text, fontsize=size, fontname="hebo" if bold else "helv")
    path = os.path.join(OUT, name)
    doc.save(path)
    return path


def table(y, items, cols=(50, 90, 300, 345, 410, 490)):
    rows = []
    rows.append((y, [(cols[0], "No"), (cols[1], "Description"), (cols[2], "HSN"), (cols[3], "Qty"), (cols[4], "Rate"), (cols[5], "Amount")], 10, True))
    for i, (d, hsn, q, r, a) in enumerate(items, 1):
        rows.append((y + 20 * i, [(cols[0], str(i)), (cols[1], d), (cols[2], hsn), (cols[3], q), (cols[4], r), (cols[5], a)], 10, False))
    return rows


# 1. Normal GST invoice (CGST + SGST), Indian number format
inv1 = [
    (60, [(50, "Sunrise Technologies Pvt Ltd")], 16, True),
    (78, [(50, "Plot 14, Hinjewadi Phase 1, Pune, Maharashtra")], 9, False),
    (92, [(50, "GSTIN: 27AABCS1429B1Z5")], 9, False),
    (125, [(50, "TAX INVOICE")], 13, True),
    (150, [(50, "Invoice No: SRT/2026/0147"), (350, "Invoice Date: 15/03/2026")], 10, False),
    (165, [(50, "PO Number: PO-88213"), (350, "Due Date: 14/04/2026")], 10, False),
    (200, [(50, "Bill To:")], 10, True),
    (215, [(50, "Meridian Retail Solutions LLP")], 10, False),
    (229, [(50, "GSTIN: 27AAACP1234C1ZV")], 9, False),
] + table(270, [
    ("Website maintenance (monthly)", "998314", "1", "25,000.00", "25,000.00"),
    ("Cloud hosting - standard plan", "998315", "3", "4,500.00", "13,500.00"),
    ("Support hours", "998313", "10", "1,200.00", "12,000.00"),
]) + [
    (400, [(330, "Sub Total:"), (470, "Rs. 50,500.00")], 10, False),
    (416, [(330, "CGST @ 9%:"), (470, "Rs. 4,545.00")], 10, False),
    (432, [(330, "SGST @ 9%:"), (470, "Rs. 4,545.00")], 10, False),
    (448, [(330, "Total GST:"), (470, "Rs. 9,090.00")], 10, False),
    (470, [(330, "Grand Total:"), (470, "Rs. 59,590.00")], 11, True),
]

# 2. IGST invoice, written month dates, "Bill No." label, lakh format
inv2 = [
    (60, [(50, "Greenfield Traders")], 16, True),
    (78, [(50, "12 Market Road, Kolhapur, Maharashtra")], 9, False),
    (92, [(50, "GSTIN: 27BBBPG5678D1Z2")], 9, False),
    (125, [(50, "Tax Invoice")], 13, True),
    (150, [(50, "Bill No. GT-2026-311"), (350, "Date: 02 April 2026")], 10, False),
    (200, [(50, "Customer:")], 10, True),
    (215, [(50, "Ashoka Builders Pvt Ltd")], 10, False),
    (229, [(50, "GSTIN: 29AABCA9999E1Z8")], 9, False),
] + table(270, [
    ("Steel rods 12mm", "7214", "50", "2,000.00", "1,00,000.00"),
    ("Cement bags", "2523", "50", "500.00", "25,000.00"),
]) + [
    (350, [(330, "Taxable Value:"), (470, "Rs. 1,25,000.00")], 10, False),
    (366, [(330, "IGST @ 18%:"), (470, "Rs. 22,500.00")], 10, False),
    (390, [(330, "Total Amount:"), (470, "Rs. 1,47,500.00")], 11, True),
]

# 3. Different layout: USD, US-style date, no GSTIN, tax label "Sales Tax"
inv3 = [
    (60, [(50, "Bluebird Design Studio LLC")], 16, True),
    (78, [(50, "88 Harbor Street, Austin, TX")], 9, False),
    (125, [(50, "INVOICE")], 13, True),
    (150, [(50, "Invoice #: INV-2026-0042")], 10, False),
    (165, [(50, "Invoice Date: March 5, 2026")], 10, False),
    (180, [(50, "Payment due: April 4, 2026")], 10, False),
    (210, [(50, "Bill To: Harper & Sons Inc")], 10, False),
] + table(250, [
    ("Brand identity design", "", "1", "$1,800.00", "$1,800.00"),
    ("Website mockups", "", "4", "$350.00", "$1,400.00"),
]) + [
    (330, [(330, "Subtotal"), (470, "$3,200.00")], 10, False),
    (346, [(330, "Sales Tax (8%)"), (470, "$256.00")], 10, False),
    (368, [(330, "Amount Due"), (470, "$3,456.00")], 11, True),
]

# 4. Invoice with a WRONG total and missing invoice date -> should be flagged for review
inv4 = [
    (60, [(50, "Orbit Stationery Mart")], 16, True),
    (92, [(50, "GSTIN: 27AAECO2222F1Z9")], 9, False),
    (125, [(50, "TAX INVOICE")], 13, True),
    (150, [(50, "Invoice No: OSM-5521")], 10, False),
    (300, [(330, "Sub Total:"), (470, "Rs. 8,000.00")], 10, False),
    (316, [(330, "CGST @ 9%:"), (470, "Rs. 720.00")], 10, False),
    (332, [(330, "SGST @ 9%:"), (470, "Rs. 720.00")], 10, False),
    (356, [(330, "Grand Total:"), (470, "Rs. 9,720.00")], 11, True),
]

p1 = make_pdf("01_gst_invoice.pdf", inv1)
make_pdf("02_igst_invoice.pdf", inv2)
make_pdf("03_usd_invoice.pdf", inv3)
make_pdf("04_wrong_total_missing_date.pdf", inv4)

# 5. Scanned-style image: render invoice 1, blur slightly, add noise, tiny rotation
page = fitz.open(p1)[0]
pix = page.get_pixmap(dpi=130)
img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).rotate(1.2, expand=True, fillcolor="white")
img = img.filter(ImageFilter.GaussianBlur(0.6))
px = img.load()
random.seed(1)
for _ in range(img.width * img.height // 60):
    x, y = random.randrange(img.width), random.randrange(img.height)
    v = random.randint(150, 230)
    px[x, y] = (v, v, v)
img.save(os.path.join(OUT, "05_scanned_photo.jpg"), quality=70)

# 6. A text file invoice and a not-an-invoice file for error testing
with open(os.path.join(OUT, "06_text_invoice.txt"), "w") as f:
    f.write("Lakeview Supplies\nGSTIN: 27AACCL3333G1Z1\nInvoice Number: LV-1009\nInvoice Date: 2026-02-20\n"
            "Taxable Value: 2,000.00\nIGST @ 12%: 240.00\nTotal Amount: 2,240.00\n")
with open(os.path.join(OUT, "07_not_an_invoice.txt"), "w") as f:
    f.write("Meeting notes\nDiscuss the roadmap and assign tasks to the team.\n")

print("Sample files written to", OUT)
