from app.parsers.base import DocumentParser
from app.parsers.docx_parser import DocxParser
from app.parsers.pdf_parser import PdfParser
from app.parsers.xlsx_parser import XlsxParser


def get_parser(file_type: str) -> DocumentParser:
    normalized = file_type.lower().replace(".", "")
    if normalized == "docx":
        return DocxParser()
    if normalized == "xlsx":
        return XlsxParser()
    if normalized == "pdf":
        return PdfParser()
    raise ValueError(f"Unsupported file type: {file_type}")
