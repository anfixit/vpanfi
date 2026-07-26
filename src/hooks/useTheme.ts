import { useEffect, useMemo, useState } from "react";
import type { Theme } from "../components/ThemeToggle";

export function useTheme() {
  const preferredTheme = useMemo<Theme>(() => {
    const saved = window.localStorage.getItem("vpanfi-theme");
    if (saved === "light" || saved === "dark") return saved;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }, []);

  const [theme, setTheme] = useState<Theme>(preferredTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("vpanfi-theme", theme);
  }, [theme]);

  return {
    theme,
    toggleTheme: () => setTheme((current) => (current === "light" ? "dark" : "light")),
  };
}
