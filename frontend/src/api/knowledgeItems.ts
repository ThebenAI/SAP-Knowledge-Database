import { apiFetch } from "./client";
import type {
  BackfillSapModulesResponse,
  CleanupRejectedResponse,
  KnowledgeItem,
  KnowledgeItemType,
  ReviewActionRequest,
  VerificationStatus
} from "../types/api";

export interface ListKnowledgeItemsParams {
  verification_status?: VerificationStatus;
  item_type?: KnowledgeItemType;
  document_id?: number;
  q?: string;
}

function toQuery(params: ListKnowledgeItemsParams): string {
  const query = new URLSearchParams();
  if (params.verification_status) query.set("verification_status", params.verification_status);
  if (params.item_type) query.set("item_type", params.item_type);
  if (typeof params.document_id === "number") query.set("document_id", String(params.document_id));
  if (params.q) query.set("q", params.q);
  const result = query.toString();
  return result ? `?${result}` : "";
}

export function listKnowledgeItems(params: ListKnowledgeItemsParams): Promise<KnowledgeItem[]> {
  return apiFetch<KnowledgeItem[]>(`/knowledge-items${toQuery(params)}`);
}

export function getKnowledgeItem(itemId: number): Promise<KnowledgeItem> {
  return apiFetch<KnowledgeItem>(`/knowledge-items/${itemId}`);
}

export function verifyKnowledgeItem(itemId: number, payload: ReviewActionRequest): Promise<KnowledgeItem> {
  return apiFetch<KnowledgeItem>(`/knowledge-items/${itemId}/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function rejectKnowledgeItem(itemId: number, payload: ReviewActionRequest): Promise<KnowledgeItem> {
  return apiFetch<KnowledgeItem>(`/knowledge-items/${itemId}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function markNeedsRevision(itemId: number, payload: ReviewActionRequest): Promise<KnowledgeItem> {
  return apiFetch<KnowledgeItem>(`/knowledge-items/${itemId}/needs-revision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function updateKnowledgeItemMetadata(itemId: number, payload: ReviewActionRequest): Promise<KnowledgeItem> {
  return apiFetch<KnowledgeItem>(`/knowledge-items/${itemId}/update-metadata`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function cleanupRejectedKnowledgeItems(): Promise<CleanupRejectedResponse> {
  return apiFetch<CleanupRejectedResponse>("/knowledge-items/cleanup-rejected", {
    method: "POST"
  });
}

export function backfillSapModules(): Promise<BackfillSapModulesResponse> {
  return apiFetch<BackfillSapModulesResponse>("/knowledge-items/backfill-sap-modules", {
    method: "POST"
  });
}
