import { create } from "zustand";

const TOKEN_KEY = "atlas_access_token";
type AuthState = {
  token: string | null;
  setToken: (token: string) => void;
  clear: () => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  token: sessionStorage.getItem(TOKEN_KEY),
  setToken: (token) => { sessionStorage.setItem(TOKEN_KEY, token); set({ token }); },
  clear: () => { sessionStorage.removeItem(TOKEN_KEY); set({ token: null }); },
}));
