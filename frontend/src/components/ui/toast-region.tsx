import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, CircleAlert, Info, X } from "lucide-react";
import { useToastStore } from "@/stores/toast-store";
import { Button } from "./button";

export function ToastRegion() {
  const { toasts, dismiss } = useToastStore();
  return <div aria-live="polite" aria-atomic="false" className="fixed right-4 top-4 z-50 flex w-[min(24rem,calc(100%-2rem))] flex-col gap-2">
    <AnimatePresence>{toasts.map((toast) => {
      const Icon = toast.tone === "error" ? CircleAlert : toast.tone === "success" ? CheckCircle2 : Info;
      return <motion.div key={toast.id} initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, x: 24 }} role={toast.tone === "error" ? "alert" : "status"} className="flex gap-3 rounded-xl border bg-[var(--surface)] p-4 shadow-xl">
        <Icon className="mt-0.5 size-5 shrink-0 text-[var(--primary)]" aria-hidden="true" />
        <div className="min-w-0 flex-1"><p className="text-sm font-semibold">{toast.title}</p>{toast.description && <p className="mt-1 text-sm text-[var(--muted)]">{toast.description}</p>}</div>
        <Button variant="ghost" size="icon" className="-m-2 size-8" onClick={() => dismiss(toast.id)} aria-label="Dismiss notification"><X className="size-4" /></Button>
      </motion.div>;
    })}</AnimatePresence>
  </div>;
}
