import { useEffect, useState } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { FileSearch, History as HistoryIcon, LayoutDashboard, Menu, Moon, ScanText, Sun, X } from "lucide-react";
import { useTheme } from "./theme.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Extract from "./pages/Extract.jsx";
import History from "./pages/History.jsx";
import InvoiceDetail from "./pages/InvoiceDetail.jsx";

const NAV = [
  { to: "/", label: "Extract", icon: FileSearch, end: true },
  { to: "/history", label: "History", icon: HistoryIcon },
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
];

function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid h-9 w-9 place-items-center rounded-lg bg-brand text-on-brand"><ScanText className="h-5 w-5" /></span>
      <span className="text-[15px] font-extrabold leading-tight tracking-tight">Invoice Extractor<span className="block text-xs font-semibold text-muted">AI data extraction</span></span>
    </div>
  );
}

function NavLinks({ onNavigate }) {
  return (
    <nav aria-label="Main" className="space-y-1">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} onClick={onNavigate}
          className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold ${isActive ? "bg-brand-soft text-brand" : "text-muted hover:bg-sunk hover:text-ink"}`}>
          <Icon className="h-[18px] w-[18px]" />{label}
        </NavLink>
      ))}
    </nav>
  );
}

export default function App() {
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => setOpen(false), [pathname]);

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[240px_1fr]">
      {/* sidebar (desktop) */}
      <aside className="hidden border-r border-line bg-surface lg:block">
        <div className="sticky top-0 space-y-8 p-5"><Brand /><NavLinks /></div>
      </aside>

      {/* mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <div className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 space-y-8 bg-surface p-5 shadow-xl">
            <div className="flex items-start justify-between"><Brand /><button aria-label="Close menu" className="rounded p-1 text-muted hover:bg-sunk" onClick={() => setOpen(false)}><X className="h-5 w-5" /></button></div>
            <NavLinks onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}

      <div className="min-w-0">
        {/* top navigation bar */}
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-line bg-surface/90 px-4 backdrop-blur sm:px-6">
          <div className="flex items-center gap-3">
            <button aria-label="Open menu" className="rounded-lg p-2 text-muted hover:bg-sunk lg:hidden" onClick={() => setOpen(true)}><Menu className="h-5 w-5" /></button>
            <div className="lg:hidden"><Brand /></div>
          </div>
          <button onClick={toggle} className="btn !px-3" aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"} title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}>
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            <span className="hidden sm:inline">{theme === "dark" ? "Light" : "Dark"}</span>
          </button>
        </header>

        <main className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 sm:py-8">
          <Routes>
            <Route path="/" element={<Extract />} />
            <Route path="/history" element={<History />} />
            <Route path="/invoice/:id" element={<InvoiceDetail />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="*" element={<p className="py-20 text-center text-muted">Page not found.</p>} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
