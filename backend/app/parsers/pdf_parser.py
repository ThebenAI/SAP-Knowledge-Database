import io

from pypdf import PdfReader

from app.parsers.base import CandidateItem, DocumentParser, ParsedDocument, build_fragment_ref


class PdfParser(DocumentParser):
    def parse(self, source: str | bytes) -> ParsedDocument:
        reader = PdfReader(io.BytesIO(source)) if isinstance(source, bytes) else PdfReader(source)
        candidates: list[CandidateItem] = []
        raw_text_chunks: list[str] = []
        fragment_idx = 1

        for page in reader.pages:
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            raw_text_chunks.append(text)
            snippet = " ".join(text.split())
            if len(snippet) > 1200:
                snippet = snippet[:1200]
            candidates.append(
                CandidateItem(
                    item_type="page_text",
                    title="PDF fragment",
                    content=text,
                    source_ref=build_fragment_ref(fragment_idx),
                    confidence=None,
                    extracted_data={
                        "fragment_kind": "pdf",
                        "section_title": f"Page {fragment_idx}",
                        "parent_section_titles": [],
                        "nearby_text": snippet,
                    },
                )
            )
            fragment_idx += 1

        return ParsedDocument(raw_text="\n\n".join(raw_text_chunks), candidates=candidates)
