import { Laptop, Moon, Sun } from "lucide-react";
import { useThemeStore, type Theme } from "@/stores/theme-store";
import { Button } from "./ui/button";

const sequence: Theme[] = ["system", "light", "dark"];
export function ThemeToggle() {
  const { theme, setTheme } = useThemeStore();
  const Icon = theme === "dark" ? Moon : theme === "light" ? Sun : Laptop;
  return <Button variant="ghost" size="icon" aria-label={`Theme: ${theme}. Change theme`} title={`Theme: ${theme}`} onClick={() => setTheme(sequence[(sequence.indexOf(theme) + 1) % sequence.length] ?? "system")}><Icon className="size-4" /></Button>;
}
