import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/app-shell";
import { ProtectedRoute } from "@/components/protected-route";
import { Skeleton } from "@/components/ui/skeleton";

const LoginPage = lazy(() => import("@/features/auth/login-page").then((module) => ({ default: module.LoginPage })));
const SignupPage = lazy(() => import("@/features/auth/signup-page").then((module) => ({ default: module.SignupPage })));
const ChatPage = lazy(() => import("@/features/chat/chat-page").then((module) => ({ default: module.ChatPage })));
const DocumentsPage = lazy(() => import("@/features/documents/documents-page").then((module) => ({ default: module.DocumentsPage })));
const fallback = <div className="mx-auto max-w-4xl space-y-4 p-8" role="status" aria-label="Loading page"><Skeleton className="h-8 w-48" /><Skeleton className="h-40" /><Skeleton className="h-40" /></div>;

export function AppRouter() {
  return <Suspense fallback={fallback}><Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/signup" element={<SignupPage />} />
    <Route element={<ProtectedRoute />}><Route element={<AppShell />}><Route index element={<Navigate to="/chat" replace />} /><Route path="/chat" element={<ChatPage />} /><Route path="/chat/:sessionId" element={<ChatPage />} /><Route path="/documents" element={<DocumentsPage />} /></Route></Route>
    <Route path="*" element={<main className="grid min-h-dvh place-items-center p-6 text-center"><div><p className="text-sm font-medium text-[var(--primary)]">404</p><h1 className="mt-2 text-2xl font-semibold">Page not found</h1><a href="/" className="mt-5 inline-block text-sm text-[var(--primary)] underline">Return to Atlas Docs</a></div></main>} />
  </Routes></Suspense>;
}
