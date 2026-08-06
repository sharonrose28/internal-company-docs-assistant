import { create } from "zustand";

export type Theme = "light" | "dark" | "system";
const initialTheme = (localStorage.getItem("atlas_theme") as Theme | null) ?? "system";

const applyTheme = (theme: Theme) => {
  const dark = theme === "dark" || (theme === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
};

type ThemeState = { theme: Theme; setTheme: (theme: Theme) => void };
export const useThemeStore = create<ThemeState>((set) => ({
  theme: initialTheme,
  setTheme: (theme) => { localStorage.setItem("atlas_theme", theme); applyTheme(theme); set({ theme }); },
}));

applyTheme(initialTheme);
