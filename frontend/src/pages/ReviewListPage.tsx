import { FormEvent, KeyboardEvent as ReactKeyboardEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  backfillSapModules,
  cleanupRejectedKnowledgeItems,
  listKnowledgeItems,
  markNeedsRevision,
  rejectKnowledgeItem,
  updateKnowledgeItemMetadata,
  verifyKnowledgeItem
} from "../api/knowledgeItems";
import { LinkNoteModal } from "../components/LinkNoteModal";
import type { KnowledgeItem, KnowledgeItemType, VerificationStatus } from "../types/api";
import { formatConfidence } from "../types/api";

type DraftRow = {
  verification_status: VerificationStatus;
  review_comment: string;
  links_note: string;
  sap_module: string;
  source_table: string;
  target_table: string;
  join_field: string;
};

const SAP_MODULE_OPTIONS = [
  "FI",
  "CO",
  "MM",
  "SD",
  "PP",
  "WM",
  "EWM",
  "HCM",
  "PM",
  "QM",
  "Basis",
  "Cross-Module"
] as const;
const MODULE_FILTER_OPTIONS = [...SAP_MODULE_OPTIONS, "Unbekannt"] as const;

function buildDraftMap(items: KnowledgeItem[]): Record<number, DraftRow> {
  const m: Record<number, DraftRow> = {};
  for (const it of items) {
    m[it.id] = {
      verification_status: it.verification_status,
      review_comment: it.review_comment ?? "",
      links_note: it.links_note ?? "",
      sap_module: it.sap_module ?? "",
      source_table: typeof it.extracted_data.source_table === "string" ? it.extracted_data.source_table : "",
      target_table: typeof it.extracted_data.target_table === "string" ? it.extracted_data.target_table : "",
      join_field: typeof it.extracted_data.join_field === "string" ? it.extracted_data.join_field : ""
    };
  }
  return m;
}

function getDraft(item: KnowledgeItem, draftById: Record<number, DraftRow>): DraftRow {
  return (
    draftById[item.id] ?? {
      verification_status: item.verification_status,
      review_comment: item.review_comment ?? "",
      links_note: item.links_note ?? "",
      sap_module: item.sap_module ?? "",
      source_table: typeof item.extracted_data.source_table === "string" ? item.extracted_data.source_table : "",
      target_table: typeof item.extracted_data.target_table === "string" ? item.extracted_data.target_table : "",
      join_field: typeof item.extracted_data.join_field === "string" ? item.extracted_data.join_field : ""
    }
  );
}

function getTableDisplay(item: KnowledgeItem): string {
  if (item.item_type === "table_mention") {
    const tableName = item.extracted_data.table_name;
    return typeof tableName === "string" && tableName.trim() ? tableName.trim() : item.title;
  }
  return item.title;
}

function getTypeDisplay(itemType: KnowledgeItemType): string {
  if (itemType === "table_mention") return "Table";
  if (itemType === "field_mention") return "Field";
  return "Link";
}

function getTypeBadgeClass(itemType: KnowledgeItemType): string {
  if (itemType === "table_mention") return "type-chip type-chip--table";
  if (itemType === "field_mention") return "type-chip type-chip--field";
  return "type-chip type-chip--link";
}

function getConfidenceClass(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "confidence-pill";
  if (value >= 0.75) return "confidence-pill confidence-pill--high";
  if (value >= 0.5) return "confidence-pill confidence-pill--medium";
  return "confidence-pill confidence-pill--low";
}

function getRelationshipDisplayFromValues(source: string, target: string, joinField: string): string {
  if (source && target && joinField) return `${source} → ${target} (${joinField})`;
  if (source && target) return `${source} → ${target}`;
  return "—";
}

function getRelationshipDisplay(item: KnowledgeItem, draft?: DraftRow): string {
  if (item.item_type !== "relationship_hint") return "—";
  const source = draft?.source_table ?? (typeof item.extracted_data.source_table === "string" ? item.extracted_data.source_table : "");
  const target = draft?.target_table ?? (typeof item.extracted_data.target_table === "string" ? item.extracted_data.target_table : "");
  const joinField = draft?.join_field ?? (typeof item.extracted_data.join_field === "string" ? item.extracted_data.join_field : "");
  return getRelationshipDisplayFromValues(source, target, joinField);
}

function getTableRelationshipMap(items: KnowledgeItem[], draftById: Record<number, DraftRow>): Record<string, string[]> {
  const map = new Map<string, Set<string>>();
  for (const item of items) {
    if (item.item_type !== "relationship_hint") continue;
    const draft = getDraft(item, draftById);
    const source = draft.source_table.trim();
    const target = draft.target_table.trim();
    const joinField = draft.join_field.trim();
    if (!source || !target) continue;

    const sourceLine = joinField ? `→ ${target} (${joinField})` : `→ ${target}`;
    const targetLine = joinField ? `← ${source} (${joinField})` : `← ${source}`;

    const sourceSet = map.get(source) ?? new Set<string>();
    sourceSet.add(sourceLine);
    map.set(source, sourceSet);

    const targetSet = map.get(target) ?? new Set<string>();
    targetSet.add(targetLine);
    map.set(target, targetSet);
  }

  const result: Record<string, string[]> = {};
  for (const [tableName, lines] of map.entries()) {
    result[tableName] = Array.from(lines);
  }
  return result;
}

function isRowDirty(item: KnowledgeItem, draft: DraftRow): boolean {
  return (
    draft.verification_status !== item.verification_status ||
    draft.review_comment.trim() !== (item.review_comment ?? "").trim() ||
    draft.links_note.trim() !== (item.links_note ?? "").trim() ||
    draft.sap_module.trim() !== (item.sap_module ?? "").trim() ||
    draft.source_table.trim() !==
      (typeof item.extracted_data.source_table === "string" ? item.extracted_data.source_table.trim() : "") ||
    draft.target_table.trim() !==
      (typeof item.extracted_data.target_table === "string" ? item.extracted_data.target_table.trim() : "") ||
    draft.join_field.trim() !==
      (typeof item.extracted_data.join_field === "string" ? item.extracted_data.join_field.trim() : "")
  );
}

const STATUS_OPTIONS: VerificationStatus[] = ["pending", "verified", "rejected", "needs_revision"];

export function ReviewListPage() {
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [draftById, setDraftById] = useState<Record<number, DraftRow>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isCleaningUpRejected, setIsCleaningUpRejected] = useState(false);
  const [isBackfillingSapModules, setIsBackfillingSapModules] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const [verificationStatus, setVerificationStatus] = useState<"" | VerificationStatus>("pending");
  const [itemType, setItemType] = useState<"" | KnowledgeItemType>("");
  const [q, setQ] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [selectedModuleFilters, setSelectedModuleFilters] = useState<string[]>([]);
  const [activeLinkItemId, setActiveLinkItemId] = useState<number | null>(null);
  const [activeLinkNote, setActiveLinkNote] = useState("");
  const [selectedRowIds, setSelectedRowIds] = useState<Set<number>>(new Set());
  const [bulkStatus, setBulkStatus] = useState<"" | VerificationStatus>("");
  const [bulkSapModule, setBulkSapModule] = useState("");
  const [bulkComment, setBulkComment] = useState("");
  const [showOnlyChanged, setShowOnlyChanged] = useState(false);
  const [activeRelationshipDraft, setActiveRelationshipDraft] = useState({
    source_table: "",
    target_table: "",
    join_field: ""
  });

  const fetchItems = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listKnowledgeItems({
        verification_status: verificationStatus || undefined,
        item_type: itemType || undefined,
        q: q || undefined
      });
      setItems(data);
      setDraftById(buildDraftMap(data));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load knowledge items");
    } finally {
      setIsLoading(false);
    }
  }, [verificationStatus, itemType, q]);

  useEffect(() => {
    void fetchItems();
  }, []);

  const setDraftField = (item: KnowledgeItem, patch: Partial<DraftRow>) => {
    setDraftById((prev) => {
      const cur = getDraft(item, prev);
      return { ...prev, [item.id]: { ...cur, ...patch } };
    });
  };

  const openLinkModal = (item: KnowledgeItem) => {
    const draft = getDraft(item, draftById);
    setActiveLinkItemId(item.id);
    setActiveLinkNote(draft.links_note);
    setActiveRelationshipDraft({
      source_table: draft.source_table,
      target_table: draft.target_table,
      join_field: draft.join_field
    });
  };

  const closeLinkModal = () => {
    setActiveLinkItemId(null);
    setActiveLinkNote("");
    setActiveRelationshipDraft({ source_table: "", target_table: "", join_field: "" });
  };

  const saveLinkModal = () => {
    if (activeLinkItemId == null) return;
    const item = items.find((it) => it.id === activeLinkItemId);
    if (!item) return;
    setDraftField(item, { links_note: activeLinkNote, ...activeRelationshipDraft });
    closeLinkModal();
  };

  const dirtyRows = useMemo(
    () => items.filter((it) => isRowDirty(it, getDraft(it, draftById))),
    [items, draftById]
  );
  const relationshipMapByTable = useMemo(() => getTableRelationshipMap(items, draftById), [items, draftById]);
  const moduleFilteredItems = useMemo(() => {
    if (selectedModuleFilters.length === 0) return items;
    const selectedSet = new Set(selectedModuleFilters);
    return items.filter((item) => {
      const draft = getDraft(item, draftById);
      const moduleValue = draft.sap_module.trim();
      const isUnknown = !moduleValue || moduleValue.toLowerCase() === "unbekannt";
      if (isUnknown) return selectedSet.has("Unbekannt");
      return selectedSet.has(moduleValue);
    });
  }, [items, draftById, selectedModuleFilters]);
  const sortedItems = useMemo(() => {
    const withIndex = moduleFilteredItems.map((item, index) => ({ item, index }));
    const moduleSortKey = (item: KnowledgeItem): { isUnknown: boolean; value: string } => {
      const draft = getDraft(item, draftById);
      const raw = draft.sap_module.trim();
      if (!raw || raw.toLowerCase() === "unbekannt") {
        return { isUnknown: true, value: "" };
      }
      return { isUnknown: false, value: raw.toLocaleLowerCase() };
    };
    return withIndex
      .sort((a, b) => {
        const moduleA = moduleSortKey(a.item);
        const moduleB = moduleSortKey(b.item);
        if (moduleA.isUnknown !== moduleB.isUnknown) return moduleA.isUnknown ? 1 : -1;
        if (moduleA.value !== moduleB.value) return moduleA.value.localeCompare(moduleB.value);

        const tableA = getTableDisplay(a.item).toLocaleLowerCase();
        const tableB = getTableDisplay(b.item).toLocaleLowerCase();
        if (tableA !== tableB) return tableA.localeCompare(tableB);

        return a.index - b.index;
      })
      .map((entry) => entry.item);
  }, [moduleFilteredItems, draftById]);
  const unsavedCount = dirtyRows.length;
  const hasUnsavedChanges = unsavedCount > 0;
  const dirtyIds = useMemo(() => new Set(dirtyRows.map((row) => row.id)), [dirtyRows]);
  const displayRows = useMemo(
    () => (showOnlyChanged ? sortedItems.filter((item) => dirtyIds.has(item.id)) : sortedItems),
    [showOnlyChanged, sortedItems, dirtyIds]
  );
  const activeLinkItem = activeLinkItemId == null ? null : items.find((it) => it.id === activeLinkItemId) ?? null;
  const activeLinkDraft = activeLinkItem ? getDraft(activeLinkItem, draftById) : null;
  const visibleRowIds = useMemo(() => displayRows.map((item) => item.id), [displayRows]);
  const rowIndexById = useMemo(() => {
    const map = new Map<number, number>();
    displayRows.forEach((item, index) => map.set(item.id, index));
    return map;
  }, [displayRows]);
  const selectedVisibleCount = useMemo(
    () => visibleRowIds.filter((id) => selectedRowIds.has(id)).length,
    [visibleRowIds, selectedRowIds]
  );
  const allVisibleSelected = visibleRowIds.length > 0 && selectedVisibleCount === visibleRowIds.length;

  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (!hasUnsavedChanges) return;
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [hasUnsavedChanges]);

  useEffect(() => {
    setSelectedRowIds((prev) => {
      const next = new Set<number>();
      for (const id of visibleRowIds) {
        if (prev.has(id)) next.add(id);
      }
      return next;
    });
  }, [visibleRowIds]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (activeLinkItemId !== null) {
        closeLinkModal();
        return;
      }
      if (selectedRowIds.size > 0) {
        setSelectedRowIds(new Set());
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [activeLinkItemId, selectedRowIds.size]);

  const toggleRowSelection = (itemId: number, checked: boolean) => {
    setSelectedRowIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(itemId);
      else next.delete(itemId);
      return next;
    });
  };

  const toggleSelectAllVisible = (checked: boolean) => {
    setSelectedRowIds((prev) => {
      const next = new Set(prev);
      for (const id of visibleRowIds) {
        if (checked) next.add(id);
        else next.delete(id);
      }
      return next;
    });
  };

  const applyBulkStatus = () => {
    if (!bulkStatus || selectedRowIds.size === 0) return;
    setDraftById((prev) => {
      const next = { ...prev };
      for (const item of displayRows) {
        if (!selectedRowIds.has(item.id)) continue;
        const cur = getDraft(item, next);
        next[item.id] = { ...cur, verification_status: bulkStatus };
      }
      return next;
    });
  };

  const applyBulkSapModule = () => {
    if (selectedRowIds.size === 0) return;
    setDraftById((prev) => {
      const next = { ...prev };
      for (const item of displayRows) {
        if (!selectedRowIds.has(item.id)) continue;
        const cur = getDraft(item, next);
        next[item.id] = { ...cur, sap_module: bulkSapModule };
      }
      return next;
    });
  };

  const applyBulkComment = () => {
    if (selectedRowIds.size === 0) return;
    setDraftById((prev) => {
      const next = { ...prev };
      for (const item of displayRows) {
        if (!selectedRowIds.has(item.id)) continue;
        const cur = getDraft(item, next);
        next[item.id] = { ...cur, review_comment: bulkComment };
      }
      return next;
    });
  };

  // Navigation blocking via useBlocker is postponed.
  // This page must stay compatible with non-data-router setups.

  const onApplyFilters = async (event: FormEvent) => {
    event.preventDefault();
    if (hasUnsavedChanges) {
      const ok = window.confirm(
        "Filter anwenden verwirft ungespeicherte Änderungen an der Tabelle. Fortfahren?"
      );
      if (!ok) return;
    }
    await fetchItems();
  };

  const onResetFilters = async () => {
    if (hasUnsavedChanges) {
      const ok = window.confirm(
        "Filter zurücksetzen verwirft ungespeicherte Änderungen an der Tabelle. Fortfahren?"
      );
      if (!ok) return;
    }
    setVerificationStatus("pending");
    setItemType("");
    setQ("");
    setSelectedModuleFilters([]);
    setError(null);
    setSaveMessage(null);
    setIsLoading(true);
    try {
      const data = await listKnowledgeItems({ verification_status: "pending" });
      setItems(data);
      setDraftById(buildDraftMap(data));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load knowledge items");
    } finally {
      setIsLoading(false);
    }
  };

  const persistDraftIfPossible = async (item: KnowledgeItem, draft: DraftRow) => {
    if (!isRowDirty(item, draft)) return { ok: true as const, skipped: false as const };
    const payload = {
      reviewer: reviewer.trim(),
      comment: draft.review_comment.trim() || undefined,
      links_note: draft.links_note.trim() || undefined,
      sap_module: draft.sap_module.trim() || undefined,
      source_table: draft.source_table.trim() || undefined,
      target_table: draft.target_table.trim() || undefined,
      join_field: draft.join_field.trim() || undefined
    };
    if (draft.verification_status === "pending") {
      if (item.verification_status !== "pending") return { ok: true as const, skipped: true as const };
      await updateKnowledgeItemMetadata(item.id, payload);
      return { ok: true as const, skipped: false as const };
    }
    if (draft.verification_status === "verified") {
      await verifyKnowledgeItem(item.id, payload);
    } else if (draft.verification_status === "rejected") {
      await rejectKnowledgeItem(item.id, payload);
    } else {
      await markNeedsRevision(item.id, payload);
    }
    return { ok: true as const, skipped: false as const };
  };

  const onSaveAll = async () => {
    if (!reviewer.trim()) {
      setError("Bitte Prüfer/in angeben, bevor Sie speichern.");
      return;
    }
    setIsSaving(true);
    setError(null);
    setSaveMessage(null);
    let skipped = 0;
    let saved = 0;
    try {
      for (const item of items) {
        const draft = getDraft(item, draftById);
        if (!isRowDirty(item, draft)) continue;
        const r = await persistDraftIfPossible(item, draft);
        if (r.skipped) skipped += 1;
        else saved += 1;
      }
      if (skipped > 0) {
        setSaveMessage(
          `${saved} Eintrag/Einträge gespeichert. ${skipped} Zeile(n) übersprungen (pending ohne API oder Zurücksetzen auf pending nicht unterstützt).`
        );
      } else {
        setSaveMessage(saved > 0 ? "Änderungen gespeichert." : "Keine speicherbaren Änderungen.");
      }
      await fetchItems();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setIsSaving(false);
    }
  };

  const onCleanupRejected = async () => {
    if (hasUnsavedChanges) {
      const ok = window.confirm(
        "Es gibt ungespeicherte Änderungen. Rejected löschen und Tabelle neu laden verwirft diese Entwürfe. Fortfahren?"
      );
      if (!ok) return;
    }
    setIsCleaningUpRejected(true);
    setError(null);
    setSaveMessage(null);
    try {
      const result = await cleanupRejectedKnowledgeItems();
      setSaveMessage(`${result.deleted_count} abgelehnte Einträge wurden gelöscht.`);
      await fetchItems();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cleanup fehlgeschlagen");
    } finally {
      setIsCleaningUpRejected(false);
    }
  };

  const onBackfillSapModules = async () => {
    if (hasUnsavedChanges) {
      const ok = window.confirm(
        "Es gibt ungespeicherte Änderungen. SAP-Module nachpflegen und Tabelle neu laden verwirft diese Entwürfe. Fortfahren?"
      );
      if (!ok) return;
    }
    setIsBackfillingSapModules(true);
    setError(null);
    setSaveMessage(null);
    try {
      const result = await backfillSapModules();
      setSaveMessage(
        `${result.updated_count} SAP-Module nachgepflegt (${result.local_updated} lokal, ${result.web_updated} per Web).`
      );
      await fetchItems();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backfill fehlgeschlagen");
    } finally {
      setIsBackfillingSapModules(false);
    }
  };

  useEffect(() => {
    if (!saveMessage) return;
    const timer = window.setTimeout(() => setSaveMessage(null), 3200);
    return () => window.clearTimeout(timer);
  }, [saveMessage]);

  const focusEditableCell = (rowIndex: number, colIndex: number) => {
    const el = document.querySelector<HTMLElement>(
      `[data-row-index="${rowIndex}"][data-col-index="${colIndex}"]`
    );
    if (!el) return;
    el.focus();
    if (el instanceof HTMLInputElement) {
      const len = el.value.length;
      el.setSelectionRange(len, len);
    }
  };

  const onTableEditableKeyDown = (event: ReactKeyboardEvent<HTMLElement>) => {
    const target = event.currentTarget as HTMLElement;
    const rowIndex = Number(target.dataset.rowIndex ?? "-1");
    const colIndex = Number(target.dataset.colIndex ?? "-1");
    if (rowIndex < 0 || colIndex < 0) return;

    const maxRow = displayRows.length - 1;
    const maxCol = 2;
    if (event.key === "Enter") {
      event.preventDefault();
      if (rowIndex >= maxRow) return;
      focusEditableCell(rowIndex + 1, colIndex);
      return;
    }

    if (event.key !== "Tab") return;
    event.preventDefault();
    const delta = event.shiftKey ? -1 : 1;
    const linearIndex = rowIndex * (maxCol + 1) + colIndex + delta;
    if (linearIndex < 0 || linearIndex > maxRow * (maxCol + 1) + maxCol) return;
    const nextRow = Math.floor(linearIndex / (maxCol + 1));
    const nextCol = linearIndex % (maxCol + 1);
    focusEditableCell(nextRow, nextCol);
  };

  const toggleModuleFilter = (module: string) => {
    setSelectedModuleFilters((prev) => {
      const exists = prev.includes(module);
      const next = exists ? prev.filter((v) => v !== module) : [...prev, module];
      return MODULE_FILTER_OPTIONS.filter((option) => next.includes(option));
    });
  };

  const clearModuleFilters = () => {
    setSelectedModuleFilters([]);
  };

  const moduleFilterSummary = useMemo(() => {
    if (selectedModuleFilters.length === 0) return "Alle Module";
    if (selectedModuleFilters.length === 1) return selectedModuleFilters[0];
    if (selectedModuleFilters.length === 2) return `${selectedModuleFilters[0]}, ${selectedModuleFilters[1]}`;
    return `${selectedModuleFilters.length} Module ausgewählt`;
  }, [selectedModuleFilters]);

  return (
    <main className="page page--review-batch">
      <section className="page-header card">
        <h2>Review Workspace</h2>
        <p>Batch-Bearbeitung fuer Status, Modul-Zuordnung und Beziehungs-Hinweise.</p>
      </section>

      <form className="card filters filters--compact" onSubmit={onApplyFilters}>
        <h2>Review Queue</h2>
        <label>
          Status
          <select
            value={verificationStatus}
            onChange={(e) => setVerificationStatus(e.target.value as "" | VerificationStatus)}
          >
            <option value="">All</option>
            <option value="pending">pending</option>
            <option value="verified">verified</option>
            <option value="rejected">rejected</option>
            <option value="needs_revision">needs_revision</option>
          </select>
        </label>
        <label>
          Type
          <select value={itemType} onChange={(e) => setItemType(e.target.value as "" | KnowledgeItemType)}>
            <option value="">All</option>
            <option value="table_mention">Table</option>
            <option value="field_mention">Field</option>
            <option value="relationship_hint">Link</option>
          </select>
        </label>
        <label>
          Search (q)
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="source_ref, title, content" />
        </label>
        <label className="module-filter">
          SAP Module
          <details className="module-filter__dropdown">
            <summary>{moduleFilterSummary}</summary>
            <div className="module-filter__menu">
              {MODULE_FILTER_OPTIONS.map((module) => (
                <label key={module} className="inline-check module-filter__option">
                  <input
                    type="checkbox"
                    checked={selectedModuleFilters.includes(module)}
                    onChange={() => toggleModuleFilter(module)}
                  />
                  <span>{module}</span>
                </label>
              ))}
              <button
                type="button"
                className="button-secondary module-filter__clear"
                disabled={selectedModuleFilters.length === 0}
                onClick={clearModuleFilters}
              >
                Auswahl löschen
              </button>
            </div>
          </details>
        </label>
        <button type="submit">Filter anwenden</button>
      </form>

      <section className="card review-batch-toolbar review-batch-toolbar--sticky">
        <div className="review-batch-toolbar__row">
          <label className="review-batch-reviewer">
            Prüfer/in (für alle Speicherungen)
            <input
              value={reviewer}
              onChange={(e) => setReviewer(e.target.value)}
              placeholder="z. B. reviewer1"
              autoComplete="username"
            />
          </label>
          <div className="review-batch-toolbar__actions">
            {unsavedCount > 0 && (
              <span className="review-unsaved-count" aria-live="polite">
                {unsavedCount} ungespeicherte Änderung{unsavedCount === 1 ? "" : "en"}
              </span>
            )}
            <button
              type="button"
              className="button-danger"
              disabled={isSaving || isLoading || isCleaningUpRejected || isBackfillingSapModules}
              onClick={() => void onCleanupRejected()}
            >
              Rejected löschen
            </button>
            <button
              type="button"
              className="button-secondary"
              disabled={isSaving || isLoading || isCleaningUpRejected || isBackfillingSapModules}
              onClick={() => void onBackfillSapModules()}
            >
              SAP-Module nachpflegen
            </button>
            <button
              type="button"
              disabled={
                !hasUnsavedChanges ||
                !reviewer.trim() ||
                isSaving ||
                isLoading ||
                isCleaningUpRejected ||
                isBackfillingSapModules
              }
              onClick={() => void onSaveAll()}
            >
              {isSaving ? "Speichern..." : "Änderungen speichern"}
            </button>
          </div>
        </div>
        {saveMessage && <p className="review-save-success">{saveMessage}</p>}
      </section>

      {isLoading && <p>Lade Einträge...</p>}
      {error && <p className="error">{error}</p>}
      {!isLoading && !error && items.length === 0 && (
        <section className="card empty-state">
          <h3>Keine Einträge gefunden</h3>
          <p>Passe die Filter an oder importiere neue Daten.</p>
          <button type="button" className="button-secondary" onClick={() => void onResetFilters()}>
            Filter zurücksetzen
          </button>
        </section>
      )}
      {selectedVisibleCount > 0 && (
        <section className="card review-bulk-toolbar">
          <div className="review-bulk-toolbar__head">
            <strong>{selectedVisibleCount} Zeile(n) ausgewählt</strong>
          </div>
          <div className="review-bulk-toolbar__controls">
            <label className="review-bulk-toolbar__primary">
              Status für Auswahl
              <div className="review-bulk-toolbar__inline">
                <select value={bulkStatus} onChange={(e) => setBulkStatus(e.target.value as "" | VerificationStatus)}>
                  <option value="">Status auswählen</option>
                  {STATUS_OPTIONS.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
                <button type="button" onClick={applyBulkStatus}>
                  Anwenden
                </button>
              </div>
            </label>
            <label>
              SAP-Modul für Auswahl
              <div className="review-bulk-toolbar__inline">
                <select value={bulkSapModule} onChange={(e) => setBulkSapModule(e.target.value)}>
                  <option value="">Unbekannt</option>
                  {SAP_MODULE_OPTIONS.map((module) => (
                    <option key={module} value={module}>
                      {module}
                    </option>
                  ))}
                </select>
                <button type="button" onClick={applyBulkSapModule}>
                  Anwenden
                </button>
              </div>
            </label>
            <label>
              Review-Kommentar für Auswahl
              <div className="review-bulk-toolbar__inline">
                <input
                  value={bulkComment}
                  onChange={(e) => setBulkComment(e.target.value)}
                  placeholder="Kommentar für ausgewählte Zeilen"
                />
                <button type="button" onClick={applyBulkComment}>
                  Anwenden
                </button>
              </div>
            </label>
            <div className="review-bulk-toolbar__clear">
              <button type="button" className="button-secondary" onClick={() => setSelectedRowIds(new Set())}>
                Auswahl aufheben
              </button>
            </div>
          </div>
        </section>
      )}

      {!isLoading && !error && items.length > 0 && (
        <div className="card review-table-card">
          <div className="review-table-controls">
            <label className="inline-check">
              <input
                type="checkbox"
                checked={showOnlyChanged}
                onChange={(e) => setShowOnlyChanged(e.target.checked)}
              />
              Nur geänderte anzeigen
            </label>
          </div>
          <div className="review-table-wrap">
          <table className="review-table">
            <thead>
              <tr>
                <th scope="col" className="col-select">
                  <input
                    type="checkbox"
                    aria-label="Select all visible rows"
                    checked={allVisibleSelected}
                    onChange={(e) => toggleSelectAllVisible(e.target.checked)}
                  />
                </th>
                <th scope="col" className="col-type">Type</th>
                <th scope="col" className="col-table">Table</th>
                <th scope="col" className="col-links">Links</th>
                <th scope="col" className="col-confidence">Confidence</th>
                <th scope="col" className="col-module">SAP Module</th>
                <th scope="col" className="col-status">Status</th>
                <th scope="col" className="col-comment">Review Comment</th>
                <th scope="col" className="col-details">Details</th>
              </tr>
            </thead>
            <tbody>
              {displayRows.map((item) => {
                const draft = getDraft(item, draftById);
                const dirty = isRowDirty(item, draft);
                const tableName = getTableDisplay(item);
                const relationshipLines =
                  item.item_type === "table_mention" ? relationshipMapByTable[tableName] ?? [] : [];
                const selected = selectedRowIds.has(item.id);
                const rowIndex = rowIndexById.get(item.id) ?? -1;
                return (
                  <tr
                    key={item.id}
                    className={`${dirty ? "review-table__row--dirty" : ""} ${selected ? "review-table__row--selected" : ""}`.trim()}
                  >
                    <td className="col-select">
                      <input
                        type="checkbox"
                        aria-label={`Select row for item ${item.id}`}
                        checked={selected}
                        onChange={(e) => toggleRowSelection(item.id, e.target.checked)}
                      />
                    </td>
                    <td className="col-type">
                      <span className={getTypeBadgeClass(item.item_type)}>{getTypeDisplay(item.item_type)}</span>
                    </td>
                    <td className="review-table__title col-table">{tableName}</td>
                    <td className="col-links">
                      {relationshipLines.length > 0 && (
                        <div className="review-links-list" title={relationshipLines.join("\n")}>
                          {relationshipLines.map((line) => (
                            <div key={line} className="review-links-list__item">
                              {line}
                            </div>
                          ))}
                        </div>
                      )}
                      <div className="review-links-helper">{getRelationshipDisplay(item, draft)}</div>
                      {draft.links_note.trim() ? (
                        <>
                          <div className="review-links-preview" title={draft.links_note}>
                            {draft.links_note}
                          </div>
                          <button
                            type="button"
                            className="button-secondary review-links-action"
                            onClick={() => openLinkModal(item)}
                          >
                            Bearbeiten
                          </button>
                        </>
                      ) : (
                        <button
                          type="button"
                          className="button-secondary review-links-action review-links-action--hint"
                          onClick={() => openLinkModal(item)}
                        >
                          + Link-Hinweis
                        </button>
                      )}
                    </td>
                    <td className="col-confidence">
                      <span className={getConfidenceClass(item.confidence)}>{formatConfidence(item.confidence)}</span>
                    </td>
                    <td className="col-module">
                      <select
                        aria-label={`SAP module for item ${item.id}`}
                        data-row-index={rowIndex}
                        data-col-index={0}
                        value={draft.sap_module}
                        onChange={(e) => setDraftField(item, { sap_module: e.target.value })}
                        onKeyDown={onTableEditableKeyDown}
                      >
                        <option value="">Unbekannt</option>
                        {SAP_MODULE_OPTIONS.map((module) => (
                          <option key={module} value={module}>
                            {module}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="col-status">
                      <select
                        aria-label={`Status for item ${item.id}`}
                        data-row-index={rowIndex}
                        data-col-index={1}
                        value={draft.verification_status}
                        onChange={(e) =>
                          setDraftField(item, { verification_status: e.target.value as VerificationStatus })
                        }
                        onKeyDown={onTableEditableKeyDown}
                      >
                        {STATUS_OPTIONS.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="col-comment">
                      <input
                        className="review-table__comment"
                        aria-label={`Review comment for item ${item.id}`}
                        data-row-index={rowIndex}
                        data-col-index={2}
                        value={draft.review_comment}
                        onChange={(e) => setDraftField(item, { review_comment: e.target.value })}
                        placeholder="Kommentar"
                        onKeyDown={onTableEditableKeyDown}
                      />
                    </td>
                    <td className="col-details">
                      <Link to={`/knowledge-items/${item.id}`} className="review-table__detail-link">
                        Details
                      </Link>
                    </td>
                  </tr>
                );
              })}
              {displayRows.length === 0 && (
                <tr>
                  <td colSpan={9} className="review-table__empty-row">
                    Keine geänderten Zeilen im aktuellen Filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
        </div>
      )}
      <LinkNoteModal
        isOpen={activeLinkItem !== null}
        tableName={activeLinkItem ? getTableDisplay(activeLinkItem) : ""}
        sapModule={activeLinkDraft?.sap_module ?? activeLinkItem?.sap_module ?? ""}
        relationshipMapByTable={relationshipMapByTable}
        linksNote={activeLinkNote}
        isRelationshipEditable={activeLinkItem?.item_type === "relationship_hint"}
        sourceTable={activeRelationshipDraft.source_table}
        targetTable={activeRelationshipDraft.target_table}
        joinField={activeRelationshipDraft.join_field}
        onRelationshipChange={(patch) =>
          setActiveRelationshipDraft((prev) => ({
            source_table: patch.sourceTable ?? prev.source_table,
            target_table: patch.targetTable ?? prev.target_table,
            join_field: patch.joinField ?? prev.join_field
          }))
        }
        onChange={setActiveLinkNote}
        onSave={saveLinkModal}
        onCancel={closeLinkModal}
      />
    </main>
  );
}
