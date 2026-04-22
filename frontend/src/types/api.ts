export type VerificationStatus = "pending" | "verified" | "rejected" | "needs_revision";
export type KnowledgeItemType = "table_mention" | "field_mention" | "relationship_hint";
export type UserRole = "admin" | "reviewer";

export interface FileImportResult {
  file_index: number;
  file_type: string;
  status: string;
  message: string;
  /** Present on failed rows when import was requested with per-file debug (include_results). */
  stage?: string;
}

export interface FilesImportResponse {
  documents_processed: number;
  knowledge_items_created: number;
  duplicates_skipped: number;
  failed_files: number;
  results?: FileImportResult[] | null;
}

export interface CleanupRejectedResponse {
  deleted_count: number;
}

export interface BackfillSapModulesResponse {
  updated_count: number;
  skipped_count: number;
  local_updated: number;
  web_updated: number;
}

export interface KnowledgeItem {
  id: number;
  item_type: KnowledgeItemType;
  title: string;
  content: string;
  source_document_id: number;
  document_code?: string | null;
  source_ref: string;
  confidence: number | null;
  extracted_data: Record<string, unknown>;
  verification_status: VerificationStatus;
  verified_by: string | null;
  verified_at: string | null;
  review_comment: string | null;
  links_note: string | null;
  sap_module: string | null;
  sap_module_source: "local" | "web" | "manual" | null;
  created_at: string;
}

export interface ReviewActionRequest {
  reviewer: string;
  comment?: string;
  sap_module?: string;
  links_note?: string;
  source_table?: string;
  target_table?: string;
  join_field?: string;
}

export interface User {
  id: number;
  username: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface AuthLoginRequest {
  username: string;
  password: string;
}

export interface AuthLoginResponse {
  access_token: string;
  token_type: "bearer";
  user: User;
}

export interface UserCreateRequest {
  username: string;
  password: string;
  role: UserRole;
  is_active: boolean;
}

export interface UserUpdateRequest {
  role?: UserRole;
  is_active?: boolean;
}

export function formatConfidence(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "N/A";
  return `${(value * 100).toFixed(0)}%`;
}
