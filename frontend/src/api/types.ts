export type Role = "admin" | "manager" | "employee";
export type DocumentStatus = "uploaded" | "processing" | "ready" | "failed";

export interface TokenResponse { access_token: string; token_type: "bearer"; expires_in: number }
export interface DocumentRecord {
  id: string; title: string; filename: string; document_type: "pdf" | "markdown" | "slack_json";
  status: DocumentStatus; size_bytes: number; department_id: string; uploaded_by: string; created_at: string;
}
export interface DocumentList { items: DocumentRecord[]; total: number }
export interface Citation {
  source_id: string; document_id: string; document_name: string; page_number: number | null;
  section_heading: string | null; similarity_score: number; quote: string;
}
export interface ChatResponse {
  session_id: string; answer: string | null; status: "answered" | "insufficient_evidence";
  confidence: number; citations: Citation[];
}
export interface ChatSession { id: string; title: string; user_id: string; created_at: string; updated_at: string }
export interface ChatHistoryItem {
  id: string; question: string; answer: string | null; confidence: number; citations: Citation[] | null; created_at: string;
}
export interface ApiErrorBody { error?: { code?: string; message?: string }; detail?: string }
