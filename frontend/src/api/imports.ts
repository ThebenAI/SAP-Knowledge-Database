import { API_BASE_URL, apiFetch, getStoredAuthToken } from "./client";
import type { FilesImportResponse } from "../types/api";

export async function importFiles(
  files: File[],
  importedBy?: string,
  includeResults?: boolean
): Promise<FilesImportResponse> {
  const formData = new FormData();
  const validatedFiles: File[] = [];
  for (const file of files) {
    if (!(file instanceof File)) {
      throw new Error("Ungueltiges Dateiobjekt erkannt. Bitte Datei neu auswaehlen.");
    }
    // Force an in-memory read before upload. This catches unreadable cloud placeholders
    // early and prevents opaque browser-side upload aborts.
    try {
      await file.arrayBuffer();
    } catch {
      throw new Error(`Datei kann lokal nicht gelesen werden: ${file.name}`);
    }
    validatedFiles.push(file);
    formData.append("files", file, file.name);
  }
  if (importedBy) {
    formData.append("imported_by", importedBy);
  }
  if (includeResults) {
    formData.append("include_results", "true");
  }
  if (import.meta.env.DEV) {
    console.info("[upload-debug] request", {
      apiBaseUrl: API_BASE_URL,
      endpoint: `${API_BASE_URL}/import/files`,
      includeResults: Boolean(includeResults),
      importedBy: importedBy ?? "",
      fileCount: validatedFiles.length,
      files: validatedFiles.map((file) => ({
        name: file.name,
        size: file.size,
        type: file.type,
        isFile: file instanceof File,
      })),
      formDataKeys: Array.from(formData.keys()),
      hasAuthToken: Boolean(getStoredAuthToken()),
    });
  }

  return apiFetch<FilesImportResponse>("/import/files", {
    method: "POST",
    body: formData
  });
}
