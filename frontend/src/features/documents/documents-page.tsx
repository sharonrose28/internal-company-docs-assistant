import { useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileJson, FileText, Files, Search, Trash2, UploadCloud } from "lucide-react";
import { documentsApi } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import { queryKeys } from "@/api/query-keys";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { useToastStore } from "@/stores/toast-store";

const formatSize = (bytes: number) => new Intl.NumberFormat(undefined, { style: "unit", unit: "megabyte", maximumFractionDigits: 1 }).format(bytes / 1_048_576);
const statusStyle = { ready: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300", failed: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300", uploaded: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300", processing: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300" };

export function DocumentsPage() {
  const picker = useRef<HTMLInputElement>(null); const client = useQueryClient(); const show = useToastStore((state) => state.show);
  const documents = useQuery({ queryKey: queryKeys.documents, queryFn: documentsApi.list });
  const upload = useMutation({ mutationFn: (file: File) => documentsApi.upload(file), onSuccess: () => { void client.invalidateQueries({ queryKey: queryKeys.documents }); show({ title: "Upload accepted", description: "The document is being processed.", tone: "success" }); }, onError: (error) => show({ title: "Upload failed", description: errorMessage(error), tone: "error" }) });
  const remove = useMutation({ mutationFn: documentsApi.remove, onSuccess: () => { void client.invalidateQueries({ queryKey: queryKeys.documents }); show({ title: "Document deleted", tone: "success" }); }, onError: (error) => show({ title: "Delete failed", description: errorMessage(error), tone: "error" }) });
  return <div className="mx-auto max-w-7xl px-4 py-8 sm:px-8"><header className="flex flex-col gap-4 sm:flex-row sm:items-center"><div><h1 className="text-2xl font-semibold tracking-tight">Documents</h1><p className="mt-1 text-sm text-[var(--muted)]">Manage the trusted sources available to your team.</p></div><div className="sm:ml-auto"><input ref={picker} className="sr-only" type="file" accept=".pdf,.md,.markdown,.json" onChange={(event) => { const file = event.target.files?.[0]; if (file) upload.mutate(file); event.target.value = ""; }} /><Button onClick={() => picker.current?.click()} disabled={upload.isPending}><UploadCloud className="size-4" />{upload.isPending ? "Uploading…" : "Upload document"}</Button></div></header>
    <div className="relative mt-8 max-w-sm"><Search className="pointer-events-none absolute left-3 top-3 size-4 text-[var(--muted)]" /><Input className="pl-9" placeholder="Search documents" aria-label="Search documents" /></div>
    <section className="mt-5 overflow-hidden rounded-xl border bg-[var(--surface)]" aria-label="Company documents">{documents.isPending ? <div className="space-y-1 p-2">{Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-16" />)}</div> : documents.isError ? <div className="p-8 text-center"><p className="font-medium">Documents could not be loaded</p><p className="mt-1 text-sm text-[var(--muted)]">{errorMessage(documents.error)}</p><Button variant="secondary" className="mt-4" onClick={() => void documents.refetch()}>Try again</Button></div> : documents.data.items.length === 0 ? <EmptyState icon={Files} title="No documents yet" description="Upload a PDF, Markdown file, or Slack export to build your knowledge base." action={<Button onClick={() => picker.current?.click()}><UploadCloud className="size-4" />Upload your first document</Button>} /> : <ul className="divide-y">{documents.data.items.map((document) => { const Icon = document.document_type === "slack_json" ? FileJson : FileText; return <li key={document.id} className="flex items-center gap-4 p-4 hover:bg-[var(--surface-muted)]/50"><div className="rounded-lg bg-[var(--surface-muted)] p-2"><Icon className="size-5" aria-hidden="true" /></div><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{document.title}</p><p className="mt-1 text-xs text-[var(--muted)]">{document.filename} · {formatSize(document.size_bytes)}</p></div><span className={`hidden rounded-full px-2.5 py-1 text-xs font-medium capitalize sm:inline ${statusStyle[document.status]}`}>{document.status}</span><Button variant="ghost" size="icon" aria-label={`Delete ${document.title}`} disabled={remove.isPending} onClick={() => { if (window.confirm(`Delete “${document.title}”? This cannot be undone.`)) remove.mutate(document.id); }}><Trash2 className="size-4" /></Button></li>; })}</ul>}</section>
  </div>;
}
