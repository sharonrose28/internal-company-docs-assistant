import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowUp, BookOpen, MessageSquareText, Sparkles } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useLocation, useParams } from "react-router-dom";
import { chatApi } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import { queryKeys } from "@/api/query-keys";
import { createClientId } from "@/lib/id";
import type { ChatHistoryItem, ChatResponse } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { useToastStore } from "@/stores/toast-store";

type LocalExchange = Pick<ChatHistoryItem, "question" | "answer" | "citations" | "confidence"> & { id: string };
const fallbackAnswer = "I couldn't find enough trusted information in the documents available to you.";
export function ChatPage() {
  const params = useParams<{ sessionId: string }>();
  const location = useLocation();
  const [question, setQuestion] = useState(""); const [createdSessionId, setCreatedSessionId] = useState<string>(); const [local, setLocal] = useState<LocalExchange[]>([]); const [revealedAnswers, setRevealedAnswers] = useState<Record<string, string>>({}); const [revealingId, setRevealingId] = useState<string>(); const revealTimer = useRef<number | undefined>(undefined); const bottom = useRef<HTMLDivElement>(null); const queryClient = useQueryClient(); const show = useToastStore((s) => s.show);
  const sessionId = params.sessionId ?? createdSessionId;
  const history = useQuery({ queryKey: sessionId ? queryKeys.history(sessionId) : ["chat-history", "new"], queryFn: () => chatApi.history(sessionId!), enabled: !!sessionId });
  const ask = useMutation({ mutationFn: (text: string) => chatApi.ask({ question: text, session_id: sessionId }), onSuccess: (result: ChatResponse, text) => {
    const id = createClientId(); const fullAnswer = result.answer ?? fallbackAnswer; const words = fullAnswer.split(/(\s+)/); let cursor = 0;
    setCreatedSessionId(result.session_id); setRevealingId(id); setRevealedAnswers((values) => ({ ...values, [id]: "" }));
    setLocal((items) => [...items, { id, question: text, answer: fullAnswer, citations: Array.isArray(result.citations) ? result.citations : [], confidence: result.confidence }]);
    if (revealTimer.current) window.clearInterval(revealTimer.current);
    revealTimer.current = window.setInterval(() => { cursor = Math.min(cursor + 2, words.length); setRevealedAnswers((values) => ({ ...values, [id]: words.slice(0, cursor).join("") })); if (cursor >= words.length) { if (revealTimer.current) window.clearInterval(revealTimer.current); revealTimer.current = undefined; setRevealingId(undefined); } }, 35);
    void queryClient.invalidateQueries({ queryKey: queryKeys.sessions });
  }, onError: (error) => show({ title: "Question failed", description: errorMessage(error), tone: "error" }) });
  useEffect(() => { if (revealTimer.current) window.clearInterval(revealTimer.current); revealTimer.current = undefined; setQuestion(""); setLocal([]); setRevealedAnswers({}); setRevealingId(undefined); setCreatedSessionId(undefined); }, [params.sessionId, location.key]);
  useEffect(() => () => { if (revealTimer.current) window.clearInterval(revealTimer.current); }, []);
  const exchanges: LocalExchange[] = [...(history.data ?? []).map((item) => ({ ...item })), ...local];
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [exchanges.length, ask.isPending]);
  const submit = () => { const value = question.trim(); if (!value || ask.isPending || revealingId) return; setQuestion(""); ask.mutate(value); };
  return <div className="flex min-h-full flex-col"><div className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 sm:px-6">{history.isPending && sessionId ? <div className="space-y-6 py-12"><Skeleton className="ml-auto h-16 w-2/3" /><Skeleton className="h-36 w-5/6" /></div> : exchanges.length === 0 ? <div className="my-auto py-16 text-center"><div className="mx-auto grid size-12 place-items-center rounded-2xl bg-[var(--primary)] text-white"><Sparkles className="size-6" /></div><h1 className="mt-5 text-2xl font-semibold tracking-tight">What can I help you find?</h1><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--muted)]">Ask about policies, processes, benefits, or anything in the documents available to you.</p><div className="mx-auto mt-8 grid max-w-xl gap-2 sm:grid-cols-2">{["Summarize our leave policy", "How do I report a security incident?"].map((text) => <button key={text} onClick={() => setQuestion(text)} className="rounded-xl border bg-[var(--surface)] p-4 text-left text-sm transition hover:bg-[var(--surface-muted)]"><MessageSquareText className="mb-3 size-4 text-[var(--primary)]" />{text}</button>)}</div></div> : <div className="space-y-8 py-8">{exchanges.map((item) => { const citations = Array.isArray(item.citations) ? item.citations : []; const visibleAnswer = revealedAnswers[item.id] ?? (typeof item.answer === "string" ? item.answer : fallbackAnswer); const isRevealing = revealingId === item.id; return <article key={item.id} className="space-y-5"><div className="ml-auto max-w-[85%] rounded-2xl bg-[var(--surface-muted)] px-4 py-3 text-sm">{item.question}</div><div className="flex gap-3"><div className="mt-1 grid size-7 shrink-0 place-items-center rounded-lg bg-[var(--primary)] text-white"><Sparkles className="size-4" /></div><div className="min-w-0 flex-1"><div className="prose-docs text-sm">{isRevealing ? <span className="whitespace-pre-wrap">{visibleAnswer}</span> : <ReactMarkdown>{visibleAnswer}</ReactMarkdown>}{isRevealing && <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-[var(--primary)]" aria-label="Response is being revealed" />}</div>{citations.length > 0 && !isRevealing && <details className="mt-4"><summary className="cursor-pointer text-xs font-medium text-[var(--muted)]">{citations.length} source{citations.length === 1 ? "" : "s"}</summary><div className="mt-2 grid gap-2">{citations.map((citation, index) => { const score = Number(citation.similarity_score); return <div key={citation.source_id || `${item.id}-${index}`} className="rounded-lg border bg-[var(--surface)] p-3 text-xs"><p className="flex items-center gap-2 font-medium"><BookOpen className="size-3.5" />{citation.document_name || "Internal document"}</p><p className="mt-1 text-[var(--muted)]">{[citation.page_number && `Page ${citation.page_number}`, citation.section_heading].filter(Boolean).join(" · ")}{Number.isFinite(score) ? ` · Score ${score.toFixed(2)}` : ""}</p></div>; })}</div></details>}</div></div></article>; })}<AnimatePresence>{ask.isPending && <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex items-center gap-3 text-sm text-[var(--muted)]"><span className="size-2 animate-pulse rounded-full bg-[var(--primary)]" />Searching authorized documents…</motion.div>}</AnimatePresence><div ref={bottom} /></div>}</div>
    <div className="sticky bottom-0 border-t bg-[var(--background)]/90 px-4 py-4 backdrop-blur"><div className="mx-auto max-w-3xl"><div className="relative"><Textarea value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.repeat) { event.preventDefault(); submit(); } }} rows={2} maxLength={4000} placeholder="Ask a question about company knowledge…" aria-label="Question" className="min-h-14 pr-14" disabled={ask.isPending || !!revealingId} /><Button size="icon" className="absolute right-2 top-1/2 size-10 -translate-y-1/2 rounded-lg" disabled={!question.trim() || ask.isPending || !!revealingId} onClick={submit} aria-label="Send question"><ArrowUp className="size-4" /></Button></div><p className="mt-2 text-center text-xs text-[var(--muted)]">Answers are generated from documents you’re authorized to access. Verify important details.</p></div></div>
  </div>;
}
