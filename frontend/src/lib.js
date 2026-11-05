// Small helpers and field definitions shared by several pages.

export const FIELD_GROUPS = [
  { title: "Invoice details", fields: [
    { key: "invoice_number", label: "Invoice number", type: "text", required: true },
    { key: "invoice_date", label: "Invoice date", type: "date", required: true },
    { key: "due_date", label: "Due date", type: "date" },
    { key: "po_number", label: "PO number", type: "text" },
    { key: "currency", label: "Currency", type: "currency" },
  ]},
  { title: "Seller and buyer", fields: [
    { key: "vendor_name", label: "Vendor name", type: "text", required: true, wide: true },
    { key: "vendor_gstin", label: "Vendor GSTIN", type: "text" },
    { key: "buyer_name", label: "Buyer name", type: "text", wide: true },
    { key: "buyer_gstin", label: "Buyer GSTIN", type: "text" },
  ]},
  { title: "Amounts", fields: [
    { key: "subtotal", label: "Subtotal", type: "number" },
    { key: "cgst", label: "CGST", type: "number" },
    { key: "sgst", label: "SGST", type: "number" },
    { key: "igst", label: "IGST", type: "number" },
    { key: "total_tax", label: "Total tax", type: "number" },
    { key: "total_amount", label: "Total amount", type: "number", required: true },
  ]},
];

export const ALL_FIELDS = FIELD_GROUPS.flatMap((g) => g.fields);
export const FIELD_LABEL = Object.fromEntries(ALL_FIELDS.map((f) => [f.key, f.label]));

export const STATUS = {
  ready: { label: "Ready", tone: "ok" },
  needs_review: { label: "Needs review", tone: "warn" },
  reviewed: { label: "Reviewed", tone: "brand" },
  failed: { label: "Failed", tone: "bad" },
};

const SYMBOL = { INR: "₹", USD: "$", EUR: "€", GBP: "£" };

export function money(value, currency = "INR") {
  if (value === null || value === undefined || value === "") return "—";
  const locale = currency === "INR" ? "en-IN" : "en-US";
  return `${SYMBOL[currency] || ""}${Number(value).toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function shortDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso.length <= 10 ? iso + "T00:00:00" : iso);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export const pct = (x) => `${Math.round((x || 0) * 100)}%`;

/** Turn the saved invoice into plain strings for the form inputs. */
export function toFormValues(invoice) {
  const out = {};
  ALL_FIELDS.forEach(({ key }) => {
    const v = invoice.data.fields[key].value;
    out[key] = v === null || v === undefined ? "" : typeof v === "number" ? v.toFixed(2) : String(v);
  });
  return out;
}

export const sameNumber = (a, b, tol = 0.01) => Math.abs((Number(a) || 0) - (Number(b) || 0)) <= tol;
