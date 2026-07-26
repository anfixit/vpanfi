export type Theme = "light" | "dark";

export function ThemeToggle({ theme, onToggle }: { theme: Theme; onToggle: () => void }) {
  return (
    <button
      className="theme-toggle"
      type="button"
      onClick={onToggle}
      aria-label={theme === "light" ? "Включить тёмную тему" : "Включить светлую тему"}
    >
      <span aria-hidden="true">☀</span>
      <span className={`theme-toggle-knob ${theme === "dark" ? "is-dark" : ""}`} />
      <span aria-hidden="true">☾</span>
    </button>
  );
}
