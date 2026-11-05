INVOICE EXTRACTOR AI
Windows 11 setup guide and technology notes

--------------------------------------------------------------------
1. WHAT THIS PROJECT DOES
--------------------------------------------------------------------
Upload invoices (PDF, JPG, PNG, TXT). The backend reads them (PDF text layer
or OCR), extracts fields with rule-based logic, validates them, and stores
the result in SQLite. The web app shows the original invoice beside the
extracted fields, flags missing values and calculation errors, lets you
correct values, keeps a history with filters, and exports to Excel, CSV
and JSON.

Folder layout

  Invoice_Extractor_AI/
    backend/
      main.py           API routes (FastAPI)
      extractor.py      reading, OCR, field extraction, validation
      database.py       SQLite tables and queries
      exporter.py       Excel / CSV / JSON export
      make_samples.py   creates dummy test invoices in backend/samples
      test_api.py       automated end-to-end test of the API
      requirements.txt  Python packages
    frontend/
      src/              React app (pages, components, theme, api client)
      package.json      JavaScript packages

--------------------------------------------------------------------
2. TECHNOLOGY EXPLANATION (SHORT)
--------------------------------------------------------------------
React + Vite       Fast single-page web app. Vite proxies /api to the backend.
Tailwind CSS       Styling. Light and dark colours are CSS variables, so every
                   component supports both themes with the same class names.
Lucide, Recharts   Icons and dashboard charts.
FastAPI + Uvicorn  Python web API. Swagger UI is generated at /docs.
Pydantic           Validates data sent to the API.
SQLite             One file database (backend/data/invoices.db). No server needed.
PyMuPDF            Reads the text layer of PDFs and draws PDF pages for the preview.
Tesseract + pytesseract  OCR for scans and photos.
Pillow, OpenCV     Image clean-up before OCR (grayscale, upscale, denoise, threshold).
OpenPyXL           Excel export. CSV and JSON use Python's standard library.

How extraction works
1. Text comes from the PDF text layer. If there is none, pages are OCR'd.
2. Words are regrouped into lines by position so table rows stay together.
3. Labels such as "Invoice No", "Grand Total", "CGST @ 9%" are matched with
   regular expressions. Each field stores value, confidence, source
   (text / ocr / calculated / manual) and the line it came from.
4. Validation checks: required fields, subtotal + tax = total, CGST = SGST,
   GSTIN format, date sanity, line items vs subtotal, duplicates.
5. Status is "ready" or "needs_review". Saving corrections sets "reviewed".
   The original extraction is never overwritten. Every change is stored in
   the corrections table with original and corrected value.

--------------------------------------------------------------------
3. WINDOWS 11 SETUP
--------------------------------------------------------------------
Install these once:

  a) Python 3.12      https://www.python.org/downloads/
                      Tick "Add python.exe to PATH" in the installer.
  b) Node.js LTS      https://nodejs.org/
  c) Tesseract OCR    https://github.com/UB-Mannheim/tesseract/wiki
                      Use the default folder
                      (C:\Program Files\Tesseract-OCR). The backend finds it
                      automatically. Without Tesseract, text PDFs still work
                      but scans and images cannot be read.
  d) Git (optional)

Backend (PowerShell window 1)

  cd Invoice_Extractor_AI\backend
  python -m venv venv
  venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  uvicorn main:app --reload

  If activation is blocked, run once:
  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

  The API runs at http://127.0.0.1:8000 and Swagger UI at
  http://127.0.0.1:8000/docs

Frontend (PowerShell window 2)

  cd Invoice_Extractor_AI\frontend
  npm install
  npm run dev

  Open http://localhost:5173

Both windows must stay open while you use the app.

--------------------------------------------------------------------
4. TESTING
--------------------------------------------------------------------
Dummy invoices (fictional companies) are in backend\samples. To recreate:

  python make_samples.py

Automated API test (uses a temporary database, your data is untouched):

  python test_api.py

Manual test: upload backend\samples\04_wrong_total_missing_date.pdf. The app
shows a missing invoice date and a total mismatch. Use "Use calculated
total", enter the date, and save. Then open History.

--------------------------------------------------------------------
5. FEATURE STATUS
--------------------------------------------------------------------
Implemented and tested
  - Upload of PDF, JPG, PNG, TXT; several files in one go (processed in turn)
  - Text-layer reading and OCR with preprocessing
  - Rule-based extraction of 15 fields plus line items
  - Per-field confidence, source tracking, overall confidence
  - Validation: missing fields, total mismatch, GST checks, GSTIN format,
    date checks, ambiguous DD/MM dates, duplicate detection (same file, or
    same vendor + invoice number)
  - Calculated values (total, subtotal, total tax) when not printed
  - Side-by-side invoice preview and editable fields
  - Manual correction with original and corrected values stored separately
  - Processing status and error messages for unreadable files
  - History with search, status filter, date range, delete
  - Export to Excel (two sheets), CSV, JSON, honouring current filters
  - Dashboard with totals and charts
  - Light and dark themes: toggle in the top bar, saved in localStorage,
    follows the system theme until you choose one
  - Responsive layout (desktop and 390 px mobile checked)

Not included (optional future work)
  - Docling and pretrained document-understanding models. They need large
    downloads (PyTorch). The code is structured so another extractor can
    be added in extractor.py.
  - Layout-aware template learning per vendor
  - Login and multiple users
  - Handwritten invoices (Tesseract is weak on handwriting)

Known limits
  - Rules are tuned for common Indian GST and international invoice layouts.
    Unusual layouts may produce missing fields. These are flagged, not guessed.
  - OCR accuracy depends on scan quality. Low-quality scans are flagged.
  - Multi-invoice PDFs are treated as one invoice.
  - The dashboard adds amounts of different currencies without converting.
