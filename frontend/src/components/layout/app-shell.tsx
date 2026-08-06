import { useState } from "react";
import { motion } from "framer-motion";
import { BookOpen, LogOut, Menu, MessageSquareText, PanelLeftClose, Plus, X } from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { cn } from "@/lib/cn";
import { createClientId } from "@/lib/id";
import { useAuthStore } from "@/stores/auth-store";
import { Button } from "../ui/button";
import { ThemeToggle } from "../theme-toggle";
import { ConversationList } from "@/features/chat/conversation-list";

const links = [
  { to: "/chat", label: "Assistant", icon: MessageSquareText },
  { to: "/documents", label: "Documents", icon: BookOpen },
];

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const clear = useAuthStore((state) => state.clear);
  const navigate = useNavigate();
  const logout = () => { clear(); navigate("/login", { replace: true }); };
  const sidebar = <div className="flex h-full flex-col">
    <div className="flex h-16 items-center gap-3 px-4"><div className="grid size-8 place-items-center rounded-lg bg-[var(--primary)] text-sm font-bold text-white">A</div>{!collapsed && <span className="font-semibold tracking-tight">Atlas Docs</span>}<Button variant="ghost" size="icon" className="ml-auto hidden lg:inline-flex" onClick={() => setCollapsed(!collapsed)} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}><PanelLeftClose className={cn("size-4 transition", collapsed && "rotate-180")} /></Button></div>
    <div className="px-3"><Button className={cn("w-full", collapsed && "px-0")} onClick={() => { navigate("/chat", { state: { resetId: createClientId() } }); setMobileOpen(false); }}><Plus className="size-4" />{!collapsed && "New conversation"}</Button></div>
    <nav aria-label="Primary navigation" className="mt-5 space-y-1 px-3">{links.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} onClick={() => setMobileOpen(false)} className={({ isActive }) => cn("flex h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium text-[var(--muted)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--foreground)]", isActive && "bg-[var(--surface-muted)] text-[var(--foreground)]", collapsed && "justify-center px-0")} title={collapsed ? label : undefined}><Icon className="size-4 shrink-0" />{!collapsed && label}</NavLink>)}</nav>
    <ConversationList collapsed={collapsed} onNavigate={() => setMobileOpen(false)} />
    <div className="mt-auto flex items-center border-t p-3"><ThemeToggle />{!collapsed && <Button variant="ghost" className="ml-auto" onClick={logout}><LogOut className="size-4" />Sign out</Button>}</div>
  </div>;
  return <div className="flex h-dvh overflow-hidden bg-[var(--background)]">
    <aside className={cn("hidden shrink-0 border-r bg-[var(--surface)] transition-[width] lg:block", collapsed ? "w-16" : "w-64")}>{sidebar}</aside>
    {mobileOpen && <><motion.button aria-label="Close navigation" className="fixed inset-0 z-30 bg-black/40 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} onClick={() => setMobileOpen(false)} /><motion.aside className="fixed inset-y-0 left-0 z-40 w-72 border-r bg-[var(--surface)] lg:hidden" initial={{ x: "-100%" }} animate={{ x: 0 }}><Button variant="ghost" size="icon" className="absolute right-2 top-3" onClick={() => setMobileOpen(false)} aria-label="Close navigation"><X className="size-5" /></Button>{sidebar}</motion.aside></>}
    <div className="flex min-w-0 flex-1 flex-col"><header className="flex h-14 shrink-0 items-center border-b bg-[var(--surface)] px-4 lg:hidden"><Button variant="ghost" size="icon" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu className="size-5" /></Button><span className="ml-2 font-semibold">Atlas Docs</span><div className="ml-auto"><ThemeToggle /></div></header><main id="main-content" className="min-h-0 flex-1 overflow-auto"><Outlet /></main></div>
  </div>;
}
