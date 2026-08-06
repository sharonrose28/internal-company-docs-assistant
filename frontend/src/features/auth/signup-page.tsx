import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";
import { authApi } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import { Button } from "@/components/ui/button";
import { FieldError, Input } from "@/components/ui/field";
import { useAuthStore } from "@/stores/auth-store";

const schema = z.object({
  email: z.email("Enter a valid company email"),
  department: z.string().trim().min(2, "Enter your department").max(120),
  password: z.string()
    .min(5, "Password must be at least 5 characters")
    .regex(/[A-Za-z]/, "Password must include a letter")
    .regex(/\d/, "Password must include a number"),
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords do not match",
  path: ["confirmPassword"],
});
type FormData = z.infer<typeof schema>;

export function SignupPage() {
  const navigate = useNavigate();
  const setToken = useAuthStore((state) => state.setToken);
  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({ resolver: zodResolver(schema) });
  const signup = useMutation({
    mutationFn: (data: FormData) => authApi.signup({
      email: data.email,
      password: data.password,
      department: data.department,
    }),
    onSuccess: (result) => {
      setToken(result.access_token);
      navigate("/chat", { replace: true });
    },
  });

  return <main className="grid min-h-dvh lg:grid-cols-[1.1fr_.9fr]">
    <section className="hidden bg-[#17171c] p-12 text-white lg:flex lg:flex-col"><div className="flex items-center gap-3 font-semibold"><span className="grid size-9 place-items-center rounded-xl bg-[#6d6de3]">A</span>Atlas Docs</div><div className="my-auto max-w-xl"><p className="mb-5 text-sm font-medium text-[#aaaaf4]">SECURE COMPANY KNOWLEDGE</p><h1 className="text-5xl font-semibold leading-tight tracking-tight">Find trusted answers faster.</h1><p className="mt-6 max-w-lg text-lg leading-8 text-zinc-400">Create an employee account to search only the documents assigned to you.</p></div><div className="flex items-center gap-2 text-sm text-zinc-400"><ShieldCheck className="size-4" />Employee access by default</div></section>
    <section className="flex items-center justify-center p-6 sm:p-12"><motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-sm"><div className="mb-10 lg:hidden"><span className="grid size-10 place-items-center rounded-xl bg-[var(--primary)] font-bold text-white">A</span></div><h1 className="text-2xl font-semibold tracking-tight">Create your account</h1><p className="mt-2 text-sm text-[var(--muted)]">Register with your company details. New accounts receive employee access.</p>
      <form className="mt-8 space-y-4" onSubmit={handleSubmit((data) => signup.mutate(data))} noValidate>
        <div><label className="mb-2 block text-sm font-medium" htmlFor="email">Work email</label><Input id="email" type="email" autoComplete="email" aria-invalid={!!errors.email} {...register("email")} /><FieldError>{errors.email?.message}</FieldError></div>
        <div><label className="mb-2 block text-sm font-medium" htmlFor="department">Department</label><Input id="department" autoComplete="organization-title" placeholder="For example, Engineering" aria-invalid={!!errors.department} {...register("department")} /><FieldError>{errors.department?.message}</FieldError></div>
        <div><label className="mb-2 block text-sm font-medium" htmlFor="password">Password</label><Input id="password" type="password" autoComplete="new-password" aria-invalid={!!errors.password} {...register("password")} /><FieldError>{errors.password?.message}</FieldError></div>
        <div><label className="mb-2 block text-sm font-medium" htmlFor="confirmPassword">Confirm password</label><Input id="confirmPassword" type="password" autoComplete="new-password" aria-invalid={!!errors.confirmPassword} {...register("confirmPassword")} /><FieldError>{errors.confirmPassword?.message}</FieldError></div>
        {signup.isError && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300">{errorMessage(signup.error)}</p>}
        <Button type="submit" className="w-full" disabled={signup.isPending}>{signup.isPending ? "Creating account…" : <>Create account<ArrowRight className="size-4" /></>}</Button>
      </form>
      <p className="mt-6 text-center text-sm text-[var(--muted)]">Already have an account? <Link className="font-medium text-[var(--primary)] hover:underline" to="/login">Sign in</Link></p>
    </motion.div></section>
  </main>;
}
