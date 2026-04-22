from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CandidateItem:
    item_type: str
    title: str
    content: str
    source_ref: str
    confidence: float | None = None
    extracted_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    raw_text: str
    candidates: list[CandidateItem]


def build_fragment_ref(index: int) -> str:
    return f"fragment_{index:03d}"


class DocumentParser(ABC):
    """Parse from a filesystem path (folder import) or raw file bytes (batch upload)."""

    @abstractmethod
    def parse(self, source: str | bytes) -> ParsedDocument:
        raise NotImplementedError
