import { FormEvent, useState } from "react";

interface FolderImportFormProps {
  onImport: (args: { files: File[]; imported_by?: string; debugMode: boolean }) => Promise<void>;
  isSubmitting: boolean;
}

export function FolderImportForm({ onImport, isSubmitting }: FolderImportFormProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [importedBy, setImportedBy] = useState("");
  const [debugMode, setDebugMode] = useState(false);

  const supportedFiles = files.filter((file) => {
    const lower = file.name.toLowerCase();
    return lower.endsWith(".docx") || lower.endsWith(".xlsx") || lower.endsWith(".pdf");
  });

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (supportedFiles.length === 0) return;
    await onImport({
      files: supportedFiles,
      imported_by: importedBy.trim() || undefined,
      debugMode
    });
  };

  return (
    <form className="card" onSubmit={handleSubmit}>
      <h2>Import SAP Folder</h2>
      <label>
        Folder
        <input
          type="file"
          multiple
          {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
          required
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
        />
      </label>
      <p>Supported files selected: {supportedFiles.length}</p>
      <label>
        Imported by (optional)
        <input value={importedBy} onChange={(e) => setImportedBy(e.target.value)} placeholder="user" />
      </label>
      <label className="inline-check">
        <input
          type="checkbox"
          checked={debugMode}
          onChange={(e) => setDebugMode(e.target.checked)}
        />
        Debug-Modus
      </label>
      <button type="submit" disabled={isSubmitting || supportedFiles.length === 0}>
        {isSubmitting ? "Importing..." : "Ordner importieren"}
      </button>
    </form>
  );
}
