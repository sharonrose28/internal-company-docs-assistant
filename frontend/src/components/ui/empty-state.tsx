import type { LucideIcon } from "lucide-react";
export function EmptyState({ icon: Icon, title, description, action }: { icon: LucideIcon; title: string; description: string; action?: React.ReactNode }) {
  return <div className="mx-auto flex max-w-md flex-col items-center px-6 py-16 text-center">
    <div className="mb-4 rounded-2xl border bg-[var(--surface)] p-3"><Icon aria-hidden="true" className="size-6 text-[var(--muted)]" /></div>
    <h2 className="font-semibold">{title}</h2><p className="mt-2 text-sm text-[var(--muted)]">{description}</p>{action && <div className="mt-5">{action}</div>}
  </div>;
}
