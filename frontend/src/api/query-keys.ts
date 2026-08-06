export const queryKeys = {
  documents: ["documents"] as const,
  sessions: ["chat-sessions"] as const,
  history: (sessionId: string) => ["chat-history", sessionId] as const,
};
