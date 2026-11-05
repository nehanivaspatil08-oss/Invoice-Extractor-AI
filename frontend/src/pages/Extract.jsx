import { useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Download, FileSearch, PencilLine } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import Dropzone from "../components/Dropzone.jsx";
import ReviewPanel from "../components/ReviewPanel.jsx";
import { ConfidenceBar, ErrorBox, Spinner, StatusBadge } from "../components/ui.jsx";

const OK_TYPES = /\.(pdf|png|jpe?g|txt)$/i;
const MAX_MB = 15;

const STEPS = [
  { icon: FileSearch, title: "Upload", text: "Drop one invoice or a whole folder. PDFs, scans and phone photos all work." },
  { icon: PencilLine, title: "Check what was found", text: "Each value is shown beside the original page, with a confidence score. Anything doubtful is flagged." },
  { icon: Download, title: "Export", text: "Download everything as Excel, CSV or JSON from the History page." },
];

export default function Extract() {
  const [queue, setQueue] = useState([]);   // [{ key, name, status: queued|processing|done|error, invoice, error }]
  const [selected, setSelected] = useState(null);
  const counter = useRef(0);

  const patch = (key, changes) => setQueue((q) => q.map((it) => (it.key === key ? { ...it, ...changes } : it)));

  // upload files one after another, so the server is never flooded
  const addFiles = async (fileList) => {
    const entries = [...fileList].map((file) => ({ key: `f${++counter.current}`, name: file.name, file, status: "queued" }));
    setQueue((q) => [...q, ...entries]);
    setSelected((s) => s ?? entries[0].key);
    for (const entry of entries) {
      if (!OK_TYPES.test(entry.name)) { patch(entry.key, { status: "error", error: "Unsupported file type. Use PDF, PNG, JPG or TXT." }); continue; }
      if (entry.file.size > MAX_MB * 1024 * 1024) { patch(entry.key, { status: "error", error: `File is larger than ${MAX_MB} MB.` }); continue; }
      patch(entry.key, { status: "processing" });
      try {
        const invoice = await api.extract(entry.file);
        patch(entry.key, { status: "done", invoice, file: undefined });
      } catch (e) {
        patch(entry.key, { status: "error", error: e.message, file: undefined });
      }
    }
  };

  const current = queue.find((q) => q.key === selected);
  const doneCount = queue.filter((q) => q.status === "done" || q.status === "error").length;
  const reviewCount = queue.filter((q) => q.invoice?.status === "needs_review").length;

  const removeFromQueue = (key) => {
    const rest = queue.filter((q) => q.key !== key);
    setQueue(rest);
    setSelected(rest[0]?.key ?? null);
  };

  /* ---------------- empty state: big upload area ---------------- */
  if (queue.length === 0) {
    return (
      <div className="mx-auto max-w-3xl">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">Turn invoices into checked, structured data</h1>
          <p className="mx-auto mt-3 max-w-xl text-base text-muted">Upload an invoice and see every extracted field next to the original. Missing values and arithmetic mistakes are flagged before anything is exported.</p>
        </div>
        <Dropzone onFiles={addFiles} />
        <ol className="mt-10 grid gap-4 sm:grid-cols-3">
          {STEPS.map(({ icon: Icon, title, text }, i) => (
            <li key={title} className="card p-5">
              <div className="mb-3 flex items-center gap-2.5">
                <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-soft text-brand"><Icon className="h-4 w-4" /></span>
                <h2 className="text-sm font-extrabold">{i + 1}. {title}</h2>
              </div>
              <p className="text-sm text-muted">{text}</p>
            </li>
          ))}
        </ol>
        <p className="mt-6 text-center text-sm text-muted">Already processed invoices? Open <Link to="/history" className="font-semibold text-brand underline-offset-2 hover:underline">History</Link>.</p>
      </div>
    );
  }

  /* ---------------- working view: queue + review ---------------- */
  return (
    <div className="space-y-5">
      <Dropzone onFiles={addFiles} compact />

      <div>
        <p className="mb-2 text-sm font-semibold text-muted">
          {doneCount} of {queue.length} processed{reviewCount > 0 && <> · <span className="text-warn">{reviewCount} need review</span></>}
        </p>
        <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {queue.map((it) => (
            <li key={it.key}>
              <button
                onClick={() => setSelected(it.key)}
                aria-current={selected === it.key}
                className={`flex w-full items-center gap-3 rounded-xl border px-3.5 py-2.5 text-left ${selected === it.key ? "border-brand bg-brand-soft/50" : "border-line bg-surface hover:bg-sunk"}`}
              >
                <span className="shrink-0">
                  {it.status === "processing" || it.status === "queued" ? <Spinner className={`h-4 w-4 ${it.status === "queued" ? "text-muted" : "text-brand"}`} />
                    : it.status === "error" || it.invoice?.status === "failed" ? <AlertTriangle className="h-4 w-4 text-bad" />
                    : <CheckCircle2 className="h-4 w-4 text-ok" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold">{it.invoice?.vendor_name || it.name}</span>
                  <span className="block truncate text-xs text-muted">{it.invoice?.invoice_number ? `${it.invoice.invoice_number} · ${it.name}` : it.status === "queued" ? "Waiting…" : it.status === "processing" ? "Reading…" : it.name}</span>
                </span>
                {it.invoice && <StatusBadge status={it.invoice.status} />}
                {it.status === "error" && <StatusBadge status="failed" />}
              </button>
            </li>
          ))}
        </ul>
      </div>

      {current?.status === "done" && (
        <ReviewPanel
          key={current.invoice.id}
          invoice={current.invoice}
          onSaved={(updated) => patch(current.key, { invoice: updated })}
          onDeleted={() => removeFromQueue(current.key)}
        />
      )}
      {(current?.status === "processing" || current?.status === "queued") && (
        <div className="card flex flex-col items-center gap-3 px-6 py-16 text-center">
          <Spinner className="h-8 w-8 text-brand" />
          <p className="font-bold">{current.status === "queued" ? "Waiting for earlier files" : `Reading ${current.name}`}</p>
          <p className="max-w-sm text-sm text-muted">Scanned pages take a few seconds because every page is run through OCR.</p>
        </div>
      )}
      {current?.status === "error" && (
        <div className="card space-y-4 p-6">
          <ErrorBox>{current.name}: {current.error}</ErrorBox>
          <button className="btn" onClick={() => removeFromQueue(current.key)}>Remove from list</button>
        </div>
      )}
    </div>
  );
}
