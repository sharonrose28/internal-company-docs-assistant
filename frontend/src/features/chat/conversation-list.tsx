import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquare, Trash2 } from "lucide-react";
import { NavLink, useNavigate, useParams } from "react-router-dom";
import { chatApi } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import { queryKeys } from "@/api/query-keys";
import { cn } from "@/lib/cn";
import { useToastStore } from "@/stores/toast-store";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export function ConversationList({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const { sessionId } = useParams(); const navigate = useNavigate(); const client = useQueryClient(); const show = useToastStore((state) => state.show);
  const sessions = useQuery({ queryKey: queryKeys.sessions, queryFn: chatApi.sessions });
  const remove = useMutation({
    mutationFn: chatApi.removeSession,
    onSuccess: (_, deletedId) => {
      client.removeQueries({ queryKey: queryKeys.history(deletedId) });
      void client.invalidateQueries({ queryKey: queryKeys.sessions });
      if (sessionId === deletedId) navigate("/chat", { replace: true });
      show({ title: "Conversation deleted", tone: "success" });
    },
    onError: (error) => show({ title: "Could not delete conversation", description: errorMessage(error), tone: "error" }),
  });
  if (collapsed) return null;
  return <section className="mt-6 min-h-0 flex-1 overflow-y-auto px-3" aria-label="Chat history">
    <p className="mb-2 px-2 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">Recent</p>
    {sessions.isPending ? <div className="space-y-2"><Skeleton className="h-9" /><Skeleton className="h-9" /></div> : sessions.data?.length ? <ul className="space-y-1">{sessions.data.map((session) => <li key={session.id} className="group relative"><NavLink to={`/chat/${session.id}`} onClick={onNavigate} className={({ isActive }) => cn("flex h-9 items-center gap-2 rounded-lg px-2 pr-9 text-sm text-[var(--muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--foreground)]", isActive && "bg-[var(--surface-muted)] text-[var(--foreground)]")}><MessageSquare className="size-3.5 shrink-0" /><span className="truncate">{session.title}</span></NavLink><Button variant="ghost" size="icon" className="absolute right-1 top-0.5 size-8 opacity-0 focus:opacity-100 group-hover:opacity-100" aria-label={`Delete ${session.title}`} disabled={remove.isPending} onClick={() => { if (window.confirm(`Delete “${session.title}” and all its messages?`)) remove.mutate(session.id); }}><Trash2 className="size-3.5" /></Button></li>)}</ul> : <p className="px-2 py-3 text-xs text-[var(--muted)]">No saved conversations</p>}
  </section>;
}
