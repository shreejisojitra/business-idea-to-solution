import csv
import io
import logging
import re
from typing import List, Dict, Any, Optional
from pypdf import PdfReader
import docx
from pptx import Presentation

logger = logging.getLogger(__name__)


class DocumentExtractionError(Exception):
    """Exception raised when document text extraction fails."""
    pass


class DocumentService:
    """Extracts clean text content from PDF, DOCX, PPTX, TXT, CSV, and MD files, and chunks text cleanly."""

    @staticmethod
    def extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
        ext = filename.lower().split(".")[-1] if "." in filename else ""

        if ext == "pdf":
            raw = DocumentService._extract_pdf(file_bytes)
        elif ext in ["docx", "doc"]:
            raw = DocumentService._extract_docx(file_bytes)
        elif ext in ["pptx", "ppt"]:
            raw = DocumentService._extract_pptx(file_bytes)
        elif ext == "csv":
            raw = DocumentService._extract_csv(file_bytes)
        elif ext in ["txt", "md"]:
            raw = file_bytes.decode("utf-8", errors="ignore")
        else:
            raise DocumentExtractionError(
                f"Unsupported file format: '.{ext}'. Supported formats: PDF, DOCX, PPTX, TXT, CSV, MD."
            )
        
        return DocumentService.clean_text(raw)

    @staticmethod
    def _extract_pdf(file_bytes: bytes) -> str:
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            text_parts = []
            for page_idx, page in enumerate(reader.pages):
                extracted = page.extract_text()
                if extracted:
                    text_parts.append(f"--- Page {page_idx + 1} ---\n{extracted}")
            
            full_text = "\n\n".join(text_parts).strip()
            if not full_text:
                raise DocumentExtractionError("No readable text found in PDF file.")
            return full_text
        except Exception as exc:
            logger.error(f"PDF extraction error: {str(exc)}")
            raise DocumentExtractionError(f"Failed to parse PDF document: {str(exc)}") from exc

    @staticmethod
    def _extract_docx(file_bytes: bytes) -> str:
        try:
            doc = docx.Document(io.BytesIO(file_bytes))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            full_text = "\n".join(paragraphs).strip()
            if not full_text:
                raise DocumentExtractionError("No readable text found in DOCX file.")
            return full_text
        except Exception as exc:
            logger.error(f"DOCX extraction error: {str(exc)}")
            raise DocumentExtractionError(f"Failed to parse DOCX document: {str(exc)}") from exc

    @staticmethod
    def _extract_pptx(file_bytes: bytes) -> str:
        try:
            prs = Presentation(io.BytesIO(file_bytes))
            text_parts = []
            for slide_idx, slide in enumerate(prs.slides):
                slide_lines = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_lines.append(shape.text.strip())
                if slide_lines:
                    text_parts.append(f"--- Slide {slide_idx + 1} ---\n" + "\n".join(slide_lines))
            
            full_text = "\n\n".join(text_parts).strip()
            if not full_text:
                raise DocumentExtractionError("No readable text found in PPTX presentation.")
            return full_text
        except Exception as exc:
            logger.error(f"PPTX extraction error: {str(exc)}")
            raise DocumentExtractionError(f"Failed to parse PPTX document: {str(exc)}") from exc

    @staticmethod
    def _extract_csv(file_bytes: bytes) -> str:
        try:
            text_data = file_bytes.decode("utf-8", errors="ignore")
            reader = csv.reader(io.StringIO(text_data))
            rows = [", ".join(row) for row in reader if any(field.strip() for field in row)]
            full_text = "\n".join(rows).strip()
            if not full_text:
                raise DocumentExtractionError("No readable text found in CSV file.")
            return full_text
        except Exception as exc:
            logger.error(f"CSV extraction error: {str(exc)}")
            raise DocumentExtractionError(f"Failed to parse CSV document: {str(exc)}") from exc

    @staticmethod
    def clean_text(raw_text: str) -> str:
        """Cleans extracted text by normalizing whitespace while preserving structure, headings, lists."""
        if not raw_text:
            return ""
        # Replace non-standard whitespace characters with standard spaces
        text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        # Collapse 3+ consecutive newlines into 2 newlines (paragraph boundary)
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Collapse multi-spaces within a single line
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
        return "\n".join(lines).strip()

    @staticmethod
    def chunk_text(
        text: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        default_heading: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Splits clean text into metadata-aware chunks (preserving page markers and section headings).
        Returns a list of dicts: [{'content': str, 'chunk_index': int, 'page_number': int|None, 'section_heading': str|None}]
        """
        cleaned = DocumentService.clean_text(text)
        if not cleaned:
            return []

        # Split text into blocks while tracking page numbers and headings
        blocks = cleaned.split("\n")
        chunks = []
        current_chunk_words = []
        current_chunk_len = 0
        chunk_idx = 0
        current_page = None
        current_heading = default_heading

        page_marker_regex = re.compile(r"^---\s*(?:Page|Slide)\s*(\d+)\s*---", re.IGNORECASE)
        heading_regex = re.compile(r"^(?:#{1,6}\s+|[A-Z0-9\s_\-\.]{3,50}:?$)", re.ASCII)

        def flush_chunk(words, page, heading):
            nonlocal chunk_idx
            if not words:
                return None
            chunk_str = " ".join(words).strip()
            if len(chunk_str) < 10:  # Skip tiny noise chunks
                return None
            res = {
                "chunk_index": chunk_idx,
                "content": chunk_str,
                "page_number": page,
                "section_heading": heading
            }
            chunk_idx += 1
            return res

        for block in blocks:
            # Check for Page marker
            page_match = page_marker_regex.match(block)
            if page_match:
                current_page = int(page_match.group(1))
                continue

            # Check for section heading
            if heading_regex.match(block) and len(block) < 80:
                current_heading = block.lstrip("#").strip()

            words = block.split()
            for word in words:
                current_chunk_words.append(word)
                current_chunk_len += len(word) + 1

                if current_chunk_len >= chunk_size:
                    c = flush_chunk(current_chunk_words, current_page, current_heading)
                    if c:
                        chunks.append(c)
                    
                    # Keep overlap words
                    overlap_words = []
                    overlap_len = 0
                    for w in reversed(current_chunk_words):
                        if overlap_len + len(w) + 1 <= chunk_overlap:
                            overlap_words.insert(0, w)
                            overlap_len += len(w) + 1
                        else:
                            break
                    current_chunk_words = overlap_words
                    current_chunk_len = overlap_len

        # Flush final remaining words
        if current_chunk_words:
            c = flush_chunk(current_chunk_words, current_page, current_heading)
            if c:
                chunks.append(c)

        return chunks
