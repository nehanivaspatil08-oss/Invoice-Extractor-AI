import { useEffect, useMemo, useState } from "react";
import { AlertCircle, AlertTriangle, Calculator, CheckCircle2, Cpu, FileText, History, Info, Plus, Save, ScanText, Trash2 } from "lucide-react";
import { api } from "../api.js";
import { FIELD_GROUPS, FIELD_LABEL, money, pct, sameNumber, toFormValues } from "../lib.js";
import { Badge, ConfidenceBar, ErrorBox, StatusBadge } from "./ui.jsx";

const SOURCE_LABEL = { text: "Text", ocr: "OCR", calculated: "Calculated", manual: "Edited" };
const WARN_ICON = { error: AlertCircle, warning: AlertTriangle, info: Info };
const WARN_TONE = { error: "text-bad", warning: "text-warn", info: "text-muted" };

/* ------------------------------------------------------------ preview of the original file */
function Preview({ invoice }) {
  const isImage = /\.(png|jpe?g)$/i.test(invoice.stored_name);
  const isPdf = invoice.page_count > 0;
  return (
    <div className="card overflow-hidden lg:sticky lg:top-20">
      <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-3 text-sm font-semibold">
        <span className="flex min-w-0 items-center gap-2"><FileText className="h-4 w-4 shrink-0 text-muted" /><span className="truncate">{invoice.filename}</span></span>
        <a href={api.fileUrl(invoice.id)} target="_blank" rel="noreferrer" className="shrink-0 text-xs font-semibold text-brand hover:underline">Open original</a>
      </div>
      <div className="max-h-[300px] space-y-3 sm:max-h-[480px] overflow-auto bg-sunk p-3 lg:max-h-[calc(100vh-11rem)]">
        {isPdf && Array.from({ length: invoice.page_count }, (_, i) => (
          <img key={i} src={api.pageUrl(invoice.id, i)} alt={`${invoice.filename}, page ${i + 1}`} className="mx-auto block w-full rounded bg-white shadow-card" />
        ))}
        {isImage && <img src={api.fileUrl(invoice.id)} alt={`Preview of ${invoice.filename}`} className="mx-auto block w-full rounded bg-white shadow-card" />}
        {!isPdf && !isImage && <pre className="whitespace-pre-wrap rounded bg-surface p-3 text-xs">{invoice.raw_text}</pre>}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ one form field */
function Field({ def, value, onChange, meta, original, edited, warnings, currencyOptions }) {
  const status = edited ? "edited" : meta.status;
  const missing = value === "" && def.required;
  const ring =
    missing || warnings.some((w) => w.level === "error") ? "border-bad/60 bg-bad-soft/40"
    : status === "warning" || warnings.length ? "border-warn/60 bg-warn-soft/40"
    : status === "calculated" ? "border-brand/50 bg-brand-soft/40" : "";
  const id = `f-${def.key}`;
  const sourceTag = edited ? "Edited" : value === "" ? null : SOURCE_LABEL[meta.source];

  return (
    <div className={def.wide ? "sm:col-span-2" : ""}>
      <div className="mb-1 flex items-center justify-between gap-2">
        <label htmlFor={id} className="text-xs font-semibold text-muted">
          {def.label}{def.required && <span className="text-bad" aria-label="required"> *</span>}
        </label>
        <span className="flex items-center gap-1.5 text-[11px] font-semibold text-muted">
          {sourceTag && <span>{sourceTag}</span>}
          {!edited && value !== "" && meta.source !== "manual" && <span className="num">{pct(meta.confidence)}</span>}
          {value === "" && <span className={def.required ? "text-bad" : ""}>{def.required ? "Missing" : "Not found"}</span>}
        </span>
      </div>
      {def.type === "currency" ? (
        <select id={id} className={`input ${ring}`} value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">Select…</option>
          {currencyOptions.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      ) : (
        <input
          id={id}
          className={`input ${def.type === "number" ? "num text-right" : ""} ${ring}`}
          type={def.type === "number" ? "text" : def.type}
          inputMode={def.type === "number" ? "decimal" : undefined}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={def.required ? "Required" : ""}
        />
      )}
      {warnings.map((w, i) => (
        <p key={i} className={`mt-1 text-xs font-medium ${WARN_TONE[w.level]}`}>{w.message}</p>
      ))}
      {edited && <p className="mt-1 text-xs text-muted">Extracted value: {original === null || original === undefined ? "not found" : String(original)}</p>}
    </div>
  );
}

/* ------------------------------------------------------------ main panel */
export default function ReviewPanel({ invoice, onSaved, onDeleted }) {
  const [values, setValues] = useState(() => (invoice.data ? toFormValues(invoice) : {}));
  const [items, setItems] = useState(() => invoice.data?.line_items || []);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  // reset the form whenever a different (or freshly saved) invoice arrives
  useEffect(() => {
    if (invoice.data) {
      setValues(toFormValues(invoice));
      setItems(invoice.data.line_items || []);
    }
    setError("");
  }, [invoice]);

  const initial = useMemo(() => (invoice.data ? toFormValues(invoice) : {}), [invoice]);

  if (invoice.status === "failed") {
    return (
      <div className="grid gap-5 lg:grid-cols-2">
        <Preview invoice={invoice} />
        <div className="card p-6">
          <div className="mb-3 flex items-center gap-2"><StatusBadge status="failed" /><span className="font-bold">{invoice.filename}</span></div>
          <ErrorBox>{invoice.error}</ErrorBox>
          <p className="mt-4 text-sm text-muted">Nothing was saved for this file and it is not counted in your totals. Try a clearer scan, or upload the original PDF instead of a photo.</p>
          <button className="btn btn-danger mt-4" onClick={() => api.remove(invoice.id).then(onDeleted)}><Trash2 className="h-4 w-4" />Remove this file</button>
        </div>
      </div>
    );
  }

  const data = invoice.data;
  const dirty = Object.keys(values).some((k) => values[k] !== initial[k]) || JSON.stringify(items) !== JSON.stringify(data.line_items);
  const set = (key, v) => { setValues((s) => ({ ...s, [key]: v })); setMessage(""); };

  // live arithmetic check: subtotal + tax = total
  const num = (k) => (values[k] === "" ? null : Number(String(values[k]).replace(/,/g, "")));
  const split = ["cgst", "sgst", "igst"].reduce((a, k) => a + (num(k) || 0), 0);
  const tax = num("total_tax") ?? split;
  const computed = num("subtotal") !== null ? Math.round((num("subtotal") + tax) * 100) / 100 : null;
  const totalOk = computed !== null && num("total_amount") !== null && sameNumber(computed, num("total_amount"), Math.max(1, 0.005 * computed));
  const cur = values.currency || "INR";

  const save = async () => {
    setSaving(true); setError(""); setMessage("");
    try {
      const updated = await api.save(invoice.id, { fields: values, line_items: items.map((i) => ({ ...i, quantity: i.quantity === "" ? null : i.quantity, unit_price: i.unit_price === "" ? null : i.unit_price, amount: i.amount === "" ? null : i.amount })) });
      setMessage("Saved. This invoice is now marked as reviewed.");
      onSaved(updated);
    } catch (e) { setError(e.message); }
    setSaving(false);
  };

  const remove = async () => {
    if (!window.confirm("Delete this invoice and its file? This cannot be undone.")) return;
    try { await api.remove(invoice.id); onDeleted(); } catch (e) { setError(e.message); }
  };

  const setItem = (idx, key, v) => { setItems((rows) => rows.map((r, i) => (i === idx ? { ...r, [key]: v } : r))); setMessage(""); };
  const itemsSum = items.reduce((a, r) => a + (Number(r.amount) || 0), 0);
  const warnings = data.warnings;
  const blocking = warnings.filter((w) => w.level !== "info");

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Preview invoice={invoice} />

      <div className="space-y-5">
        {/* header: status, confidence, how it was read */}
        <div className="card p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <StatusBadge status={invoice.status} />
              {invoice.duplicate_of && <Badge tone="warn">Duplicate of #{invoice.duplicate_of}</Badge>}
            </div>
            <ConfidenceBar value={invoice.overall_conf} />
          </div>
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
            <span className="inline-flex items-center gap-1.5">{invoice.source === "ocr" ? <ScanText className="h-3.5 w-3.5" /> : <Cpu className="h-3.5 w-3.5" />}
              {invoice.source === "ocr" ? `Read with OCR (text quality ${Math.round(data.ocr_confidence || 0)}%)` : "Read from the PDF text layer"}</span>
            <span>Processed in {invoice.processing_ms} ms</span>
          </div>

          {blocking.length === 0 ? (
            <p className="mt-4 flex items-center gap-2 rounded-lg bg-ok-soft px-3 py-2 text-sm font-semibold text-ok"><CheckCircle2 className="h-4 w-4" />All required fields found and the totals add up.</p>
          ) : (
            <div className="mt-4 rounded-lg border border-warn/40 bg-warn-soft/50 p-3">
              <p className="mb-2 text-sm font-bold text-warn">{blocking.length} {blocking.length === 1 ? "item needs" : "items need"} your attention</p>
              <ul className="space-y-1.5">
                {blocking.map((w, i) => {
                  const Icon = WARN_ICON[w.level];
                  return (
                    <li key={i} className="flex gap-2 text-sm">
                      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${WARN_TONE[w.level]}`} />
                      <span><span className="font-semibold">{FIELD_LABEL[w.field] || w.field}:</span> {w.message}</span>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>

        {/* editable fields */}
        {FIELD_GROUPS.map((group) => (
          <section key={group.title} className="card p-5">
            <h2 className="mb-4 text-sm font-extrabold">{group.title}</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              {group.fields.map((def) => (
                <Field
                  key={def.key}
                  def={def}
                  value={values[def.key] ?? ""}
                  onChange={(v) => set(def.key, v)}
                  meta={data.fields[def.key]}
                  original={invoice.original.fields[def.key]}
                  edited={(values[def.key] ?? "") !== initial[def.key]}
                  warnings={warnings.filter((w) => w.field === def.key && w.level !== "info")}
                  currencyOptions={["INR", "USD", "EUR", "GBP"]}
                />
              ))}
            </div>
            {group.title === "Amounts" && computed !== null && num("total_amount") !== null && (
              <div className={`mt-4 flex flex-wrap items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm ${totalOk ? "bg-ok-soft text-ok" : "bg-warn-soft text-warn"}`}>
                <span className="flex items-center gap-2 font-semibold"><Calculator className="h-4 w-4" />
                  {totalOk ? `Subtotal + tax = ${money(computed, cur)}. Matches the total.` : `Subtotal + tax = ${money(computed, cur)}, but the total is ${money(num("total_amount"), cur)}.`}
                </span>
                {!totalOk && <button type="button" className="btn !py-1 text-xs" onClick={() => set("total_amount", String(computed))}>Use calculated total</button>}
              </div>
            )}
          </section>
        ))}

        {/* line items */}
        <section className="card p-5">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-extrabold">Line items <span className="font-medium text-muted">({items.length})</span></h2>
            <button type="button" className="btn !px-3 !py-1.5 text-xs" onClick={() => setItems([...items, { description: "", hsn: "", quantity: "", unit_price: "", amount: "" }])}><Plus className="h-3.5 w-3.5" />Add row</button>
          </div>
          {items.length === 0 ? (
            <p className="text-sm text-muted">No table rows were detected on this invoice. You can add rows manually.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] text-sm">
                <thead><tr className="text-left text-xs text-muted">
                  <th className="pb-2 pr-2 font-semibold">Description</th><th className="pb-2 pr-2 font-semibold">HSN</th>
                  <th className="pb-2 pr-2 text-right font-semibold">Qty</th><th className="pb-2 pr-2 text-right font-semibold">Rate</th>
                  <th className="pb-2 pr-2 text-right font-semibold">Amount</th><th className="w-8" />
                </tr></thead>
                <tbody>
                  {items.map((r, i) => (
                    <tr key={i}>
                      <td className="pb-1.5 pr-2"><input aria-label="Description" className="input !py-1.5" value={r.description} onChange={(e) => setItem(i, "description", e.target.value)} /></td>
                      <td className="pb-1.5 pr-2 w-24"><input aria-label="HSN" className="input !py-1.5" value={r.hsn} onChange={(e) => setItem(i, "hsn", e.target.value)} /></td>
                      {["quantity", "unit_price", "amount"].map((k) => (
                        <td key={k} className="pb-1.5 pr-2 w-24"><input aria-label={k} className="input num !py-1.5 text-right" inputMode="decimal" value={r[k] ?? ""} onChange={(e) => setItem(i, k, e.target.value === "" ? "" : Number(e.target.value) || 0)} /></td>
                      ))}
                      <td className="pb-1.5"><button type="button" aria-label="Remove row" className="rounded p-1.5 text-muted hover:bg-bad-soft hover:text-bad" onClick={() => setItems(items.filter((_, j) => j !== i))}><Trash2 className="h-4 w-4" /></button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="num mt-2 text-right text-xs text-muted">Rows add up to <span className="font-bold text-ink">{money(itemsSum, cur)}</span></p>
            </div>
          )}
        </section>

        {/* change history */}
        {invoice.corrections?.length > 0 && (
          <section className="card p-5">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-extrabold"><History className="h-4 w-4" />Changes from the extracted values</h2>
            <ul className="divide-y divide-line text-sm">
              {invoice.corrections.map((c) => (
                <li key={c.field} className="flex flex-wrap items-baseline justify-between gap-x-4 py-2">
                  <span className="font-semibold">{FIELD_LABEL[c.field] || c.field}</span>
                  <span className="num text-muted"><s>{c.original_value ?? "not found"}</s> <span className="font-semibold text-ink">→ {c.corrected_value ?? "cleared"}</span></span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* actions */}
        <div className="card sticky bottom-3 z-10 flex flex-wrap items-center justify-between gap-3 p-3">
          <div className="min-h-[1.25rem] px-1 text-sm">
            {error ? <span className="font-semibold text-bad">{error}</span> : message ? <span className="font-semibold text-ok">{message}</span> : dirty ? <span className="text-muted">You have unsaved changes.</span> : null}
          </div>
          <div className="flex gap-2">
            <button className="btn btn-danger" onClick={remove}><Trash2 className="h-4 w-4" /><span className="hidden sm:inline">Delete</span></button>
            <button className="btn btn-primary" onClick={save} disabled={saving || (!dirty && invoice.status === "reviewed")}>
              <Save className="h-4 w-4" />{saving ? "Saving…" : dirty ? "Save changes" : invoice.status === "reviewed" ? "Saved" : "Mark as reviewed"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
