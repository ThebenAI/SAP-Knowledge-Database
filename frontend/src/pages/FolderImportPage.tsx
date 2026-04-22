import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { importFiles } from "../api/imports";
import { FolderImportForm } from "../components/FolderImportForm";
import type { FilesImportResponse } from "../types/api";

function toImportErrorMessage(error: unknown): string {
  if (!(error instanceof Error)) {
    return "Datei-Import fehlgeschlagen.";
  }
  if (error.message === "AUTH_REQUIRED") {
    return "Sitzung abgelaufen. Bitte erneut anmelden.";
  }
  if (error.message === "FORBIDDEN") {
    return "Keine Berechtigung fuer den Import. Bitte Admin kontaktieren.";
  }
  if (error.message === "Failed to fetch") {
    return "Verbindungsfehler beim Upload. Bitte Backend/Proxy pruefen und erneut versuchen.";
  }
  return error.message;
}

export function FolderImportPage() {
  const navigate = useNavigate();
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
      if (err instanceof Error && err.message === "AUTH_REQUIRED") {
        setError("Sitzung abgelaufen. Bitte erneut anmelden.");
        navigate("/login", { replace: true });
      } else {
        setError(toImportErrorMessage(err));
      }
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
          <div className="import-metrics-grid">
            <p>
              <span className="debug-field">📄 Documents</span>: {result.documents_processed ?? 0}
            </p>
            <p>
              <span className="debug-field">✅ Created</span>: {result.knowledge_items_created ?? 0}
            </p>
            <p>
              <span className="debug-field" title="Bestehende Einträge wurden mit neuem Kontext verbessert">
                🧠 Angereichert
              </span>
              : {result.duplicates_enriched ?? 0}
            </p>
            <p>
              <span className="debug-field">⏭️ Skipped</span>: {result.duplicates_skipped ?? 0}
            </p>
            <p>
              <span className="debug-field">❌ Failed</span>: {result.failed_files ?? 0}
            </p>
          </div>
          {result.results && result.results.length > 0 && (
            <div className="debug-results">
              <h4>Per-file results (debug)</h4>
              <ul className="debug-list">
                {result.results.map((r) => (
                  <li key={r.file_index}>
                    <span className="debug-field">#{r.file_index}</span>{" "}
                    <span className="debug-field">{r.file_type}</span>{" "}
                    <span className="debug-field">{r.status}</span> — {r.message}
                    {r.status === "processed" ? (
                      <>
                        {" "}
                        <span className="debug-field">enriched: {r.duplicates_enriched ?? 0}</span>
                        {" "}
                        <span className="debug-field">skipped: {r.duplicates_skipped ?? 0}</span>
                      </>
                    ) : null}
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
