import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BarChart3, CheckCircle2, ClipboardCheck, IndianRupee, ScanLine } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { EmptyState, ErrorBox, PageHeader, Spinner } from "../components/ui.jsx";
import { STATUS, pct } from "../lib.js";
import { useTheme } from "../theme.jsx";

// Recharts draws SVG, so it needs real colour values instead of CSS variables.
const PALETTE = {
  light: {
    brand: "#522B5B",
    ok: "#15803D",
    warn: "#A16207",
    bad: "#BE2A3E",
    muted: "#854F6C",
    grid: "#DFB6B2",
    tip: "#FFFAF8",
    ink: "#190019",
  },
  dark: {
    brand: "#DFB6B2",
    ok: "#5ED48E",
    warn: "#F6B242",
    bad: "#FF808E",
    muted: "#DFB6B2",
    grid: "#854F6C",
    tip: "#2B124C",
    ink: "#FBE4DB",
  },
};

const compact = (n) => new Intl.NumberFormat("en-IN", { notation: "compact", maximumFractionDigits: 1 }).format(n);

function Stat({ icon: Icon, label, value, hint }) {
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between text-muted"><span className="text-sm font-semibold">{label}</span><Icon className="h-4 w-4" /></div>
      <p className="num mt-2 text-3xl font-extrabold tracking-tight">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}

export default function Dashboard() {
  const { theme } = useTheme();
  const c = PALETTE[theme];
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => { api.stats().then(setStats).catch((e) => setError(e.message)); }, []);

  if (error) return <ErrorBox>{error}</ErrorBox>;
  if (!stats) return <div className="grid place-items-center py-24"><Spinner className="h-7 w-7 text-brand" /></div>;

  const tooltip = { contentStyle: { background: c.tip, border: `1px solid ${c.grid}`, borderRadius: 8, color: c.ink, fontSize: 12 }, cursor: { fill: c.grid, opacity: 0.4 } };
  const tick = { fill: c.muted, fontSize: 12 };
  const statusData = Object.entries(stats.by_status).map(([k, v]) => ({ name: STATUS[k]?.label || k, value: v, color: c[STATUS[k]?.tone] || c.muted }));

  return (
    <>
      <PageHeader title="Dashboard" subtitle="A summary of everything processed so far.">
        <Link to="/" className="btn btn-primary"><ScanLine className="h-4 w-4" />Extract invoices</Link>
      </PageHeader>

      {stats.total === 0 ? (
        <div className="card"><EmptyState icon={BarChart3} title="Nothing to chart yet" action={<Link to="/" className="btn btn-primary">Upload your first invoice</Link>}>Charts and totals appear here once invoices are processed.</EmptyState></div>
      ) : (
        <div className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Stat icon={ScanLine} label="Invoices processed" value={stats.total} hint={stats.failed ? `${stats.failed} could not be read` : "All files were read"} />
            <Stat icon={ClipboardCheck} label="Waiting for review" value={stats.needs_review} hint={stats.needs_review ? "Open History and filter by status" : "Nothing waiting"} />
            <Stat icon={IndianRupee} label="Total invoice value" value={compact(stats.total_value)} hint="Duplicates excluded. Mixed currencies added as-is." />
            <Stat icon={CheckCircle2} label="Average confidence" value={pct(stats.avg_confidence)} hint={`${stats.corrections} manual corrections made`} />
          </div>

          <div className="grid gap-5 lg:grid-cols-3">
            <section className="card p-5 lg:col-span-2">
              <h2 className="mb-4 text-sm font-extrabold">Invoice value by month</h2>
              {stats.monthly.length === 0 ? <p className="py-10 text-center text-sm text-muted">No invoices with a date yet.</p> : (
                <div className="h-64" role="img" aria-label="Bar chart of invoice value by month">
                  <ResponsiveContainer>
                    <BarChart data={stats.monthly} margin={{ left: -10, right: 8 }}>
                      <CartesianGrid vertical={false} stroke={c.grid} />
                      <XAxis dataKey="month" tick={tick} tickLine={false} axisLine={{ stroke: c.grid }} />
                      <YAxis tick={tick} tickLine={false} axisLine={false} tickFormatter={compact} />
                      <Tooltip {...tooltip} formatter={(v) => [Number(v).toLocaleString("en-IN"), "Total"]} />
                      <Bar dataKey="total" fill={c.brand} radius={[6, 6, 0, 0]} maxBarSize={48} isAnimationActive={false} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </section>

            <section className="card p-5">
              <h2 className="mb-4 text-sm font-extrabold">Status</h2>
              <div className="h-44" role="img" aria-label="Donut chart of invoice statuses">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={statusData} dataKey="value" nameKey="name" innerRadius={44} outerRadius={70} paddingAngle={2} stroke="none" isAnimationActive={false}>
                      {statusData.map((d) => <Cell key={d.name} fill={d.color} />)}
                    </Pie>
                    <Tooltip {...tooltip} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="mt-3 space-y-1.5 text-sm">
                {statusData.map((d) => (
                  <li key={d.name} className="flex items-center justify-between"><span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: d.color }} />{d.name}</span><span className="num font-semibold">{d.value}</span></li>
                ))}
              </ul>
            </section>
          </div>

          <section className="card p-5">
            <h2 className="mb-4 text-sm font-extrabold">Top vendors by value</h2>
            {stats.top_vendors.length === 0 ? <p className="text-sm text-muted">No vendors yet.</p> : (
              <div style={{ height: 48 * stats.top_vendors.length + 24 }} role="img" aria-label="Bar chart of top vendors">
                <ResponsiveContainer>
                  <BarChart data={stats.top_vendors} layout="vertical" margin={{ left: 8, right: 16 }}>
                    <XAxis type="number" tick={tick} tickLine={false} axisLine={false} tickFormatter={compact} />
                    <YAxis type="category" dataKey="vendor" width={150} tick={tick} tickLine={false} axisLine={false} />
                    <Tooltip {...tooltip} formatter={(v) => [Number(v).toLocaleString("en-IN"), "Total"]} />
                    <Bar dataKey="total" fill={c.brand} radius={[0, 6, 6, 0]} barSize={20} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </section>
        </div>
      )}
    </>
  );
}
