interface LinkNoteModalProps {
  isOpen: boolean;
  tableName: string;
  sapModule: string;
  relationshipMapByTable: Record<string, string[]>;
  linksNote: string;
  isRelationshipEditable: boolean;
  sourceTable: string;
  targetTable: string;
  joinField: string;
  onRelationshipChange: (patch: { sourceTable?: string; targetTable?: string; joinField?: string }) => void;
  onChange: (next: string) => void;
  onSave: () => void;
  onCancel: () => void;
}

export function LinkNoteModal({
  isOpen,
  tableName,
  sapModule,
  relationshipMapByTable,
  linksNote,
  isRelationshipEditable,
  sourceTable,
  targetTable,
  joinField,
  onRelationshipChange,
  onChange,
  onSave,
  onCancel
}: LinkNoteModalProps) {
  if (!isOpen) return null;
  const relationships = relationshipMapByTable[tableName] ?? [];

  return (
    <div className="link-note-modal" role="dialog" aria-modal="true" aria-labelledby="link-note-title">
      <div className="link-note-modal__panel card">
        <h3 id="link-note-title">Link-Hinweis bearbeiten</h3>
        <p>
          <strong>Tabelle:</strong> {tableName}
        </p>
        <p>
          <strong>SAP-Modul:</strong> {sapModule || "Unbekannt"}
        </p>
        <div>
          <strong>Erkannte Beziehungen:</strong>
          {relationships.length > 0 ? (
            <div className="link-note-modal__relationships">
              {relationships.map((line) => (
                <div key={line} className="link-note-modal__relationship-line">
                  {line}
                </div>
              ))}
            </div>
          ) : (
            <div className="link-note-modal__relationship-line">—</div>
          )}
        </div>
        {isRelationshipEditable && (
          <div className="link-note-modal__relationship-editor">
            <label>
              Source Table
              <input
                value={sourceTable}
                onChange={(e) => onRelationshipChange({ sourceTable: e.target.value })}
                placeholder="z. B. BKPF"
              />
            </label>
            <label>
              Target Table
              <input
                value={targetTable}
                onChange={(e) => onRelationshipChange({ targetTable: e.target.value })}
                placeholder="z. B. BSEG"
              />
            </label>
            <label>
              Join Field
              <input
                value={joinField}
                onChange={(e) => onRelationshipChange({ joinField: e.target.value })}
                placeholder="z. B. BELNR"
              />
            </label>
          </div>
        )}
        <label>
          Link-Hinweis
          <textarea
            value={linksNote}
            onChange={(e) => onChange(e.target.value)}
            rows={7}
            placeholder="Hinweise oder Korrekturen zur Beziehung"
          />
        </label>
        <div className="actions">
          <button type="button" onClick={onSave}>
            Speichern
          </button>
          <button type="button" className="button-secondary" onClick={onCancel}>
            Abbrechen
          </button>
        </div>
      </div>
    </div>
  );
}
