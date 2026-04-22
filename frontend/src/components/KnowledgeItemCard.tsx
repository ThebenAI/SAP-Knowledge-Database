import { Link } from "react-router-dom";
import { formatConfidence, type KnowledgeItem } from "../types/api";

interface KnowledgeItemCardProps {
  item: KnowledgeItem;
}

export function KnowledgeItemCard({ item }: KnowledgeItemCardProps) {
  return (
    <article className="card">
      <h3>
        <Link to={`/knowledge-items/${item.id}`}>{item.title}</Link>
      </h3>
      <p>
        <strong>Document Code:</strong> {item.document_code ?? "N/A"}
      </p>
      <p>
        <strong>Type:</strong> {item.item_type}
      </p>
      <p>
        <strong>Status:</strong> {item.verification_status}
      </p>
      <p>
        <strong>Source Ref:</strong> {item.source_ref}
      </p>
      <p>
        <strong>Confidence:</strong> {formatConfidence(item.confidence)}
      </p>
      <p>
        <strong>Extracted Data:</strong>
      </p>
      <pre>{JSON.stringify(item.extracted_data, null, 2)}</pre>
      <p>
        <strong>Content:</strong> {item.content}
      </p>
    </article>
  );
}
