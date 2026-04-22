import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getKnowledgeItem,
  markNeedsRevision,
  rejectKnowledgeItem,
  verifyKnowledgeItem
} from "../api/knowledgeItems";
import { ReviewActionPanel } from "../components/ReviewActionPanel";
import { formatConfidence, type KnowledgeItem } from "../types/api";

export function KnowledgeItemDetailPage() {
  const { itemId } = useParams();
  const [item, setItem] = useState<KnowledgeItem | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const id = Number(itemId);

  const loadItem = async () => {
    if (!Number.isFinite(id)) return;
    setError(null);
    try {
      const data = await getKnowledgeItem(id);
      setItem(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load item");
    }
  };

  useEffect(() => {
    void loadItem();
  }, [id]);

  const runAction = async (action: (reviewer: string, comment?: string) => Promise<KnowledgeItem>, reviewer: string, comment?: string) => {
    setIsSubmitting(true);
    setError(null);
    try {
      const updated = await action(reviewer, comment);
      setItem(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update review status");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!Number.isFinite(id)) return <p className="error">Invalid item id.</p>;
  if (!item) return <p>Lade Eintrag...</p>;

  return (
    <main className="page">
      <section className="page-header card">
        <h2>Knowledge Item Details</h2>
        <p>Technische Metadaten und Review-Historie eines einzelnen Eintrags.</p>
      </section>
      <p>
        <Link to="/review">← Zurück zur Liste</Link>
      </p>
      {error && <p className="error">{error}</p>}
      <section className="card">
        <h2>{item.title}</h2>
        <p>
          <strong>Document Code:</strong> {item.document_code ?? "N/A"}
        </p>
        <p>
          <strong>Status:</strong> {item.verification_status}
        </p>
        <p>
          <strong>Item Type:</strong> {item.item_type}
        </p>
        <p>
          <strong>Source Ref:</strong> {item.source_ref}
        </p>
        <p>
          <strong>Confidence:</strong> {formatConfidence(item.confidence)}
        </p>
        <p>
          <strong>SAP Module:</strong> {item.sap_module ?? "N/A"}
        </p>
        <p>
          <strong>SAP Module Source:</strong> {item.sap_module_source ?? "N/A"}
        </p>
        <p>
          <strong>Content:</strong> {item.content}
        </p>
        <p>
          <strong>Extracted Data:</strong>
        </p>
        <pre>{JSON.stringify(item.extracted_data, null, 2)}</pre>
        <p>
          <strong>Reviewed by:</strong> {item.verified_by ?? "N/A"}
        </p>
        <p>
          <strong>Reviewed at:</strong> {item.verified_at ?? "N/A"}
        </p>
        <p>
          <strong>Review comment:</strong> {item.review_comment ?? "N/A"}
        </p>
      </section>

      <ReviewActionPanel
        item={item}
        isSubmitting={isSubmitting}
        onVerify={(reviewer, comment) => runAction((r, c) => verifyKnowledgeItem(item.id, { reviewer: r, comment: c }), reviewer, comment)}
        onReject={(reviewer, comment) => runAction((r, c) => rejectKnowledgeItem(item.id, { reviewer: r, comment: c }), reviewer, comment)}
        onNeedsRevision={(reviewer, comment) =>
          runAction((r, c) => markNeedsRevision(item.id, { reviewer: r, comment: c }), reviewer, comment)
        }
      />
    </main>
  );
}
