import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; size?: "sm" | "md" | "icon" };
export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { className, variant = "primary", size = "md", type = "button", ...props }, ref,
) {
  return <button ref={ref} type={type} className={cn(
    "inline-flex shrink-0 items-center justify-center gap-2 rounded-lg font-medium transition disabled:pointer-events-none disabled:opacity-50",
    "focus-visible:outline-2 focus-visible:outline-[var(--primary)]",
    variant === "primary" && "bg-[var(--primary)] text-white hover:bg-[var(--primary-hover)]",
    variant === "secondary" && "border bg-[var(--surface)] hover:bg-[var(--surface-muted)]",
    variant === "ghost" && "hover:bg-[var(--surface-muted)]",
    variant === "danger" && "bg-red-600 text-white hover:bg-red-700",
    size === "sm" && "h-8 px-3 text-sm", size === "md" && "h-10 px-4 text-sm", size === "icon" && "size-10",
    className,
  )} {...props} />;
});
