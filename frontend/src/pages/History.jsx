import { useEffect, useState } from "react";
import { FileSpreadsheet, FileText, Braces, Inbox, Search, Trash2 } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { ConfidenceBar, EmptyState, ErrorBox, PageHeader, Spinner, StatusBadge } from "../components/ui.jsx";
import { money, shortDate } from "../lib.js";

export default function History() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState({ search: "", status: "", date_from: "", date_to: "" });
  const [debounced, setDebounced] = useState(filters);
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);

  // wait 300 ms after typing before asking the server
  useEffect(() => {
    const t = setTimeout(() => setDebounced(filters), 300);
    return () => clearTimeout(t);
  }, [filters]);

  useEffect(() => {
    let cancelled = false;
    api.list(debounced).then((r) => { if (!cancelled) { setRows(r); setError(""); } }).catch((e) => !cancelled && setError(e.message));
    return () => { cancelled = true; };
  }, [debounced, reload]);

  const set = (k, v) => setFilters((f) => ({ ...f, [k]: v }));
  const hasFilters = Object.values(filters).some(Boolean);
  const remove = async (e, id) => {
    e.stopPropagation();
    if (!window.confirm("Delete this invoice and its file?")) return;
    try { await api.remove(id); setReload((n) => n + 1); } catch (err) { setError(err.message); }
  };

  const exports = [
    { format: "xlsx", label: "Excel", icon: FileSpreadsheet },
    { format: "csv", label: "CSV", icon: FileText },
    { format: "json", label: "JSON", icon: Braces },
  ];

  return (
    <>
      <PageHeader title="History" subtitle="Every invoice you have processed. Exports include only the rows matching your filters.">
        {exports.map(({ format, label, icon: Icon }) => (
          <a key={format} className="btn" href={api.exportUrl(format, debounced)} download><Icon className="h-4 w-4" />{label}</a>
        ))}
      </PageHeader>

      <div className="card mb-4 grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-[1fr_180px_160px_160px_auto]">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <input className="input pl-9" placeholder="Search vendor, invoice number or file" aria-label="Search" value={filters.search} onChange={(e) => set("search", e.target.value)} />
        </div>
        <select className="input" aria-label="Status" value={filters.status} onChange={(e) => set("status", e.target.value)}>
          <option value="">All statuses</option>
          <option value="ready">Ready</option>
          <option value="needs_review">Needs review</option>
          <option value="reviewed">Reviewed</option>
          <option value="failed">Failed</option>
        </select>
        <input type="date" className="input" aria-label="Invoice date from" value={filters.date_from} onChange={(e) => set("date_from", e.target.value)} />
        <input type="date" className="input" aria-label="Invoice date to" value={filters.date_to} onChange={(e) => set("date_to", e.target.value)} />
        <button className="btn" disabled={!hasFilters} onClick={() => setFilters({ search: "", status: "", date_from: "", date_to: "" })}>Clear</button>
      </div>

      {error && <ErrorBox>{error}</ErrorBox>}

      <div className="card overflow-hidden">
        {rows === null && !error ? (
          <div className="grid place-items-center py-16"><Spinner className="h-6 w-6 text-brand" /></div>
        ) : rows && rows.length === 0 ? (
          <EmptyState icon={Inbox} title={hasFilters ? "No invoices match these filters" : "No invoices yet"}
            action={!hasFilters && <Link to="/" className="btn btn-primary">Upload an invoice</Link>}>
            {hasFilters ? "Try a different search or clear the filters." : "Processed invoices appear here so you can search, review and export them."}
          </EmptyState>
        ) : rows && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-line bg-sunk/60 text-left text-xs font-semibold text-muted">
                  <th className="px-4 py-3">Invoice</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3 text-right">Total</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="hidden px-4 py-3 md:table-cell">Confidence</th>
                  <th className="hidden px-4 py-3 lg:table-cell">Uploaded</th>
                  <th className="w-12" />
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((r) => (
                  <tr key={r.id} tabIndex={0} onClick={() => navigate(`/invoice/${r.id}`)} onKeyDown={(e) => e.key === "Enter" && navigate(`/invoice/${r.id}`)} className="cursor-pointer hover:bg-sunk/60 focus-visible:bg-sunk/60">
                    <td className="px-4 py-3">
                      <div className="font-semibold">{r.vendor_name || <span className="text-muted">{r.status === "failed" ? "Could not read" : "Unknown vendor"}</span>}</div>
                      <div className="max-w-[260px] truncate text-xs text-muted">{r.invoice_number ? `${r.invoice_number} · ` : ""}{r.filename}</div>
                    </td>
                    <td className="num px-4 py-3">{shortDate(r.invoice_date)}</td>
                    <td className="num px-4 py-3 text-right font-semibold">{r.status === "failed" ? "—" : money(r.total_amount, r.currency || "INR")}</td>
                    <td className="px-4 py-3"><StatusBadge status={r.status} /></td>
                    <td className="hidden px-4 py-3 md:table-cell">{r.overall_conf != null && r.status !== "failed" ? <ConfidenceBar value={r.overall_conf} /> : "—"}</td>
                    <td className="num hidden px-4 py-3 text-muted lg:table-cell">{shortDate(r.uploaded_at)}</td>
                    <td className="px-2 py-3"><button aria-label={`Delete ${r.filename}`} className="rounded p-2 text-muted hover:bg-bad-soft hover:text-bad" onClick={(e) => remove(e, r.id)}><Trash2 className="h-4 w-4" /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {rows && rows.length > 0 && <p className="mt-3 text-xs text-muted">{rows.length} {rows.length === 1 ? "invoice" : "invoices"} shown. Failed files are not included in exports.</p>}
    </>
  );
}
