import axios, { AxiosError } from "axios";
import { useAuthStore } from "@/stores/auth-store";
import type { ApiErrorBody } from "./types";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "/api",
  timeout: 30_000,
  headers: { Accept: "application/json" },
});

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(undefined, (error: AxiosError<ApiErrorBody>) => {
  if (error.response?.status === 401) useAuthStore.getState().clear();
  return Promise.reject(error);
});

export const errorMessage = (error: unknown) => {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    return error.response?.data?.error?.message ?? error.response?.data?.detail ?? "The server could not complete the request.";
  }
  return error instanceof Error ? error.message : "An unexpected error occurred.";
};
