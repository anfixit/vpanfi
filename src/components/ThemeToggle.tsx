import { Icon } from "./Icon";

export type Theme = "light" | "dark";

export function ThemeToggle({
  theme,
  onToggle,
}: {
  theme: Theme;
  onToggle: () => void;
}) {
  return (
    <button
      className="theme-toggle"
      type="button"
      onClick={onToggle}
      aria-pressed={theme === "dark"}
      aria-label={theme === "light" ? "Включить тёмную тему" : "Включить светлую тему"}
    >
      <Icon name="sun" />
      <span className={`theme-toggle-knob ${theme === "dark" ? "is-dark" : ""}`} />
      <Icon name="moon" />
    </button>
  );
}
