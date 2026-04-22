import { useState } from "react";
import { importFiles } from "../api/imports";
import { FolderImportForm } from "../components/FolderImportForm";
import type { FilesImportResponse } from "../types/api";

export function FolderImportPage() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<FilesImportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleImport = async (payload: { files: File[]; imported_by?: string; debugMode: boolean }) => {
    setIsSubmitting(true);
    setError(null);
    try {
      const response = await importFiles(payload.files, payload.imported_by, payload.debugMode);
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "File import failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="page">
      <section className="page-header card">
        <h2>Import Workspace</h2>
        <p>Dateien hochladen und Knowledge Items für die Review Queue erzeugen.</p>
      </section>
      <FolderImportForm onImport={handleImport} isSubmitting={isSubmitting} />
      {error && <p className="error">{error}</p>}
      {result && (
        <section className="card">
          <h3>Import Complete</h3>
          <p>Documents processed: {result.documents_processed}</p>
          <p>Knowledge items created: {result.knowledge_items_created}</p>
          <p>Duplicates skipped: {result.duplicates_skipped}</p>
          <p>Failed files: {result.failed_files}</p>
          {result.results && result.results.length > 0 && (
            <div className="debug-results">
              <h4>Per-file results (debug)</h4>
              <ul className="debug-list">
                {result.results.map((r) => (
                  <li key={r.file_index}>
                    <span className="debug-field">#{r.file_index}</span>{" "}
                    <span className="debug-field">{r.file_type}</span>{" "}
                    <span className="debug-field">{r.status}</span> — {r.message}
                    {r.stage ? (
                      <>
                        {" "}
                        <span className="debug-field">stage: {r.stage}</span>
                      </>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
