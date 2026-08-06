import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import axios from "axios";
import type { ReactNode } from "react";
import { BrowserRouter } from "react-router-dom";
import { useLocation } from "react-router-dom";
import { ErrorBoundary } from "@/components/error-boundary";
import { ToastRegion } from "@/components/ui/toast-region";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, gcTime: 10 * 60_000, retry: (count, error) => ![401, 403, 404].includes(axios.isAxiosError(error) ? (error.response?.status ?? 0) : 0) && count < 2, refetchOnWindowFocus: false },
    mutations: { retry: false },
  },
});

function RouteBoundary({ children }: { children: ReactNode }) {
  const location = useLocation();
  return <ErrorBoundary resetKey={location.key}>{children}</ErrorBoundary>;
}

export function AppProviders({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={queryClient}><BrowserRouter><RouteBoundary>{children}</RouteBoundary><ToastRegion /></BrowserRouter></QueryClientProvider>;
}
