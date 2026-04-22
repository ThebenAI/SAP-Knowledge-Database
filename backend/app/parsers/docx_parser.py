import io

from docx import Document as DocxDocument

from app.parsers.base import CandidateItem, DocumentParser, ParsedDocument, build_fragment_ref


class DocxParser(DocumentParser):
    def parse(self, source: str | bytes) -> ParsedDocument:
        doc = DocxDocument(io.BytesIO(source)) if isinstance(source, bytes) else DocxDocument(source)
        candidates: list[CandidateItem] = []
        raw_text_chunks: list[str] = []
        fragment_idx = 1

        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue
            raw_text_chunks.append(text)
            candidates.append(
                CandidateItem(
                    item_type="text_snippet",
                    title="Text fragment",
                    content=text,
                    source_ref=build_fragment_ref(fragment_idx),
                    confidence=None,
                    extracted_data={"fragment_kind": "text"},
                )
            )
            fragment_idx += 1

        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if not row_text:
                    continue
                raw_text_chunks.append(row_text)
                candidates.append(
                    CandidateItem(
                        item_type="table_row",
                        title="Table fragment",
                        content=row_text,
                        source_ref=build_fragment_ref(fragment_idx),
                        confidence=None,
                        extracted_data={"fragment_kind": "table"},
                    )
                )
                fragment_idx += 1

        return ParsedDocument(raw_text="\n".join(raw_text_chunks), candidates=candidates)
