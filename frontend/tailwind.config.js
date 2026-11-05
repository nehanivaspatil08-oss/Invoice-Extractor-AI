/** Colours come from CSS variables (see src/index.css) so light and dark themes share one set of class names. */
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: { sans: ["Manrope", "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"] },
      colors: {
        page: v("page"), surface: v("surface"), sunk: v("sunk"), line: v("line"),
        ink: v("ink"), muted: v("muted"),
        brand: v("brand"), "brand-soft": v("brand-soft"), "on-brand": v("on-brand"),
        ok: v("ok"), "ok-soft": v("ok-soft"),
        warn: v("warn"), "warn-soft": v("warn-soft"),
        bad: v("bad"), "bad-soft": v("bad-soft"),
      },
      boxShadow: { card: "0 1px 2px rgb(var(--shadow) / 0.06), 0 4px 16px -8px rgb(var(--shadow) / 0.10)" },
    },
  },
  plugins: [],
};
