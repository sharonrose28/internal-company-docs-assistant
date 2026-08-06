export function createClientId(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }

  const random = Math.random().toString(36).slice(2);
  return `local-${Date.now().toString(36)}-${random}`;
}
