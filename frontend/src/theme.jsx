import { createContext, useContext, useEffect, useState } from "react";

// Theme rules: a saved choice (localStorage "theme") wins; otherwise follow the system setting.
const ThemeContext = createContext({ theme: "light", toggle: () => {} });
export const useTheme = () => useContext(ThemeContext);

const systemTheme = () => (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
const savedTheme = () => {
  try { return localStorage.getItem("theme"); } catch { return null; }
};

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => savedTheme() || systemTheme());

  // apply the class on <html>
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  // enable smooth transitions only after the first paint
  useEffect(() => {
    const id = requestAnimationFrame(() => document.documentElement.classList.add("theme-ready"));
    return () => cancelAnimationFrame(id);
  }, []);

  // follow system changes only while the user has not picked a theme
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => { if (!savedTheme()) setTheme(systemTheme()); };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    try { localStorage.setItem("theme", next); } catch { /* storage blocked: still works for this session */ }
    setTheme(next);
  };

  return <ThemeContext.Provider value={{ theme, toggle }}>{children}</ThemeContext.Provider>;
}
