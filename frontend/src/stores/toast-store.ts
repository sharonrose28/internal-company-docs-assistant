import { create } from "zustand";
import { createClientId } from "@/lib/id";

export type Toast = { id: string; title: string; description?: string; tone?: "success" | "error" | "info" };
type ToastState = {
  toasts: Toast[];
  show: (toast: Omit<Toast, "id">) => void;
  dismiss: (id: string) => void;
};

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  show: (toast) => {
    const id = createClientId();
    set((state) => ({ toasts: [...state.toasts, { ...toast, id }] }));
    window.setTimeout(() => set((state) => ({ toasts: state.toasts.filter((item) => item.id !== id) })), 5000);
  },
  dismiss: (id) => set((state) => ({ toasts: state.toasts.filter((item) => item.id !== id) })),
}));
