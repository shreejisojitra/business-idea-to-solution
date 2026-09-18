import pytest
from app.services.document_service import DocumentExtractionError, DocumentService


def test_extract_text_txt_file():
    """Test text extraction from plain text bytes."""
    sample_text = "Hospital appointment booking is handled manually via phone calls."
    extracted = DocumentService.extract_text_from_bytes(sample_text.encode("utf-8"), "sample.txt")
    assert extracted == sample_text


def test_unsupported_file_extension():
    """Test error handling for unsupported file extensions."""
    with pytest.raises(DocumentExtractionError):
        DocumentService.extract_text_from_bytes(b"dummy binary", "image.png")
