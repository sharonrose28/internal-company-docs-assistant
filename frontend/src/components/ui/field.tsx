import { forwardRef, type InputHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...props }, ref) {
  return <input ref={ref} className={cn("h-10 w-full rounded-lg border bg-[var(--surface)] px-3 text-sm placeholder:text-[var(--muted)]", className)} {...props} />;
});
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, ...props }, ref) {
  return <textarea ref={ref} className={cn("w-full resize-none rounded-xl border bg-[var(--surface)] px-4 py-3 text-sm placeholder:text-[var(--muted)]", className)} {...props} />;
});
export function FieldError({ children }: { children?: string }) {
  return children ? <p role="alert" className="mt-1 text-sm text-red-600 dark:text-red-400">{children}</p> : null;
}
