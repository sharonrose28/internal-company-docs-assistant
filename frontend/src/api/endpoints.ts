import { api } from "./client";
import type { ChatHistoryItem, ChatResponse, ChatSession, DocumentList, DocumentRecord, TokenResponse } from "./types";

export const authApi = {
  login: async (input: { email: string; password: string }) => (await api.post<TokenResponse>("/login", input)).data,
  signup: async (input: { email: string; password: string; department: string }) => (await api.post<TokenResponse>("/signup", input)).data,
};
export const documentsApi = {
  list: async () => (await api.get<DocumentList>("/documents")).data,
  get: async (id: string) => (await api.get<DocumentRecord>(`/documents/${id}`)).data,
  upload: async (file: File, title?: string) => {
    const body = new FormData(); body.append("file", file); if (title) body.append("title", title);
    return (await api.post<DocumentRecord>("/upload", body)).data;
  },
  remove: async (id: string) => { await api.delete(`/documents/${id}`); },
};
export const chatApi = {
  ask: async (input: { question: string; session_id?: string }) => (await api.post<ChatResponse>("/chat", input)).data,
  sessions: async () => (await api.get<ChatSession[]>("/chat/sessions")).data,
  createSession: async (title: string) => (await api.post<ChatSession>("/chat/sessions", { title })).data,
  history: async (sessionId: string) => (await api.get<ChatHistoryItem[]>("/chat/history", { params: { session_id: sessionId } })).data,
  removeSession: async (sessionId: string) => { await api.delete(`/chat/sessions/${sessionId}`); },
};
