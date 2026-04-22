import { FormEvent, useState } from "react";
import type { KnowledgeItem } from "../types/api";

interface ReviewActionPanelProps {
  item: KnowledgeItem;
  onVerify: (reviewer: string, comment?: string) => Promise<void>;
  onReject: (reviewer: string, comment?: string) => Promise<void>;
  onNeedsRevision: (reviewer: string, comment?: string) => Promise<void>;
  isSubmitting: boolean;
}

export function ReviewActionPanel({
  item,
  onVerify,
  onReject,
  onNeedsRevision,
  isSubmitting
}: ReviewActionPanelProps) {
  const [reviewer, setReviewer] = useState("");
  const [comment, setComment] = useState("");

  const withPayload = async (action: (reviewer: string, comment?: string) => Promise<void>, event: FormEvent) => {
    event.preventDefault();
    if (!reviewer.trim()) return;
    await action(reviewer.trim(), comment.trim() || undefined);
  };

  return (
    <section className="card">
      <h3>Review Item #{item.id}</h3>
      <label>
        Reviewer
        <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="reviewer1" />
      </label>
      <label>
        Comment (optional)
        <textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={3} />
      </label>

      <div className="actions">
        <button disabled={isSubmitting || !reviewer.trim()} onClick={(e) => withPayload(onVerify, e)}>
          Verify
        </button>
        <button disabled={isSubmitting || !reviewer.trim()} onClick={(e) => withPayload(onReject, e)}>
          Reject
        </button>
        <button disabled={isSubmitting || !reviewer.trim()} onClick={(e) => withPayload(onNeedsRevision, e)}>
          Needs Revision
        </button>
      </div>
    </section>
  );
}
