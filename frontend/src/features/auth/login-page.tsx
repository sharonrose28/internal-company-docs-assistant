import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { useForm } from "react-hook-form";
import { useLocation, useNavigate } from "react-router-dom";
import { Link } from "react-router-dom";
import { z } from "zod";
import { authApi } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import { Button } from "@/components/ui/button";
import { FieldError, Input } from "@/components/ui/field";
import { useAuthStore } from "@/stores/auth-store";

const schema = z.object({
  email: z.email("Enter a valid company email"),
  password: z.string()
    .min(5, "Password must be at least 5 characters")
    .regex(/[A-Za-z]/, "Password must include a letter")
    .regex(/\d/, "Password must include a number"),
});
type FormData = z.infer<typeof schema>;

export function LoginPage() {
  const navigate = useNavigate(); const location = useLocation(); const setToken = useAuthStore((state) => state.setToken);
  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({ resolver: zodResolver(schema) });
  const login = useMutation({ mutationFn: authApi.login, onSuccess: (result) => { setToken(result.access_token); const state = location.state as { from?: string } | null; navigate(state?.from ?? "/chat", { replace: true }); } });
  return <main className="grid min-h-dvh lg:grid-cols-[1.1fr_.9fr]">
    <section className="hidden bg-[#17171c] p-12 text-white lg:flex lg:flex-col"><div className="flex items-center gap-3 font-semibold"><span className="grid size-9 place-items-center rounded-xl bg-[#6d6de3]">A</span>Atlas Docs</div><div className="my-auto max-w-xl"><p className="mb-5 text-sm font-medium text-[#aaaaf4]">COMPANY KNOWLEDGE, GROUNDED</p><h1 className="text-5xl font-semibold leading-tight tracking-tight">Answers your team can trust.</h1><p className="mt-6 max-w-lg text-lg leading-8 text-zinc-400">Search internal knowledge, understand policies, and move faster—with every answer tied to an authorized source.</p></div><div className="flex items-center gap-2 text-sm text-zinc-400"><ShieldCheck className="size-4" />Permission-aware by design</div></section>
    <section className="flex items-center justify-center p-6 sm:p-12"><motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-sm"><div className="mb-10 lg:hidden"><span className="grid size-10 place-items-center rounded-xl bg-[var(--primary)] font-bold text-white">A</span></div><h2 className="text-2xl font-semibold tracking-tight">Welcome back</h2><p className="mt-2 text-sm text-[var(--muted)]">Sign in with your company credentials.</p>
      <form className="mt-8 space-y-5" onSubmit={handleSubmit((data) => login.mutate(data))} noValidate><div><label className="mb-2 block text-sm font-medium" htmlFor="email">Work email</label><Input id="email" type="email" autoComplete="email" aria-invalid={!!errors.email} {...register("email")} /><FieldError>{errors.email?.message}</FieldError></div><div><label className="mb-2 block text-sm font-medium" htmlFor="password">Password</label><Input id="password" type="password" autoComplete="current-password" aria-invalid={!!errors.password} {...register("password")} /><FieldError>{errors.password?.message}</FieldError></div>{login.isError && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300">{errorMessage(login.error)}</p>}<Button type="submit" className="w-full" disabled={login.isPending}>{login.isPending ? "Signing in…" : <>Continue<ArrowRight className="size-4" /></>}</Button></form>
      <p className="mt-6 text-center text-sm text-[var(--muted)]">New to Atlas Docs? <Link className="font-medium text-[var(--primary)] hover:underline" to="/signup">Create an account</Link></p>
    </motion.div></section>
  </main>;
}
