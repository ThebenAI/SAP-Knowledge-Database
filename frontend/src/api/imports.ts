import { apiFetch } from "./client";
import type { FilesImportResponse } from "../types/api";

export function importFiles(
  files: File[],
  importedBy?: string,
  includeResults?: boolean
): Promise<FilesImportResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  if (importedBy) {
    formData.append("imported_by", importedBy);
  }
  if (includeResults) {
    formData.append("include_results", "true");
  }

  return apiFetch<FilesImportResponse>("/import/files", {
    method: "POST",
    body: formData
  });
}
