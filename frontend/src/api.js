// All calls to the FastAPI backend live here. Vite forwards /api to http://127.0.0.1:8000.
async function request(url, options) {
  let res;
  try {
    res = await fetch(url, options);
  } catch {
    throw new Error("Cannot reach the backend. Start it with: uvicorn main:app --reload");
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try { const body = await res.json(); if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail); } catch { /* not JSON */ }
    throw new Error(detail);
  }
  return res.json();
}

const qs = (params) => {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v && p.set(k, v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const api = {
  extract: (file) => { const f = new FormData(); f.append("file", file); return request("/api/extract", { method: "POST", body: f }); },
  list: (filters) => request(`/api/invoices${qs(filters)}`),
  get: (id) => request(`/api/invoices/${id}`),
  save: (id, body) => request(`/api/invoices/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  remove: (id) => request(`/api/invoices/${id}`, { method: "DELETE" }),
  stats: () => request("/api/stats"),
  fileUrl: (id) => `/api/invoices/${id}/file`,
  pageUrl: (id, page) => `/api/invoices/${id}/page/${page}`,
  exportUrl: (format, filters) => `/api/export${qs({ ...filters, format })}`,
};
