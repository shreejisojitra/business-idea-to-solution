"""
Module 4 Tests — Document Intelligence + RAG
Tests: document extraction, project-scoped RAG ingestion/search, project isolation, error handling.
"""
import io
import pytest
from unittest.mock import MagicMock, patch
from app.services.document_service import DocumentService, DocumentExtractionError
from app.services.ai.rag_service import RAGService, RAGError
from app.services.ai.embeddings import EmbeddingProvider
from app.db.models import Project, KnowledgeSource, KnowledgeChunk, Workspace, User


# ─── Document Extraction Tests ────────────────────────────────────────────────

def test_extract_txt():
    text = "Nutrition requirements: Vitamin C 90mg, Iron 18mg daily."
    result = DocumentService.extract_text_from_bytes(text.encode(), "nutrition.txt")
    assert "Nutrition requirements" in result
    assert "Vitamin C" in result


def test_extract_md():
    text = "# Inventory System\n\nManage stock levels and reorder points."
    result = DocumentService.extract_text_from_bytes(text.encode(), "inventory.md")
    assert "Inventory System" in result


def test_unsupported_format_raises_error():
    with pytest.raises(DocumentExtractionError) as exc_info:
        DocumentService.extract_text_from_bytes(b"binary data", "image.png")
    assert "Unsupported file format" in str(exc_info.value)


def test_unsupported_format_error_message_is_useful():
    """Error message should name the format and list supported ones."""
    with pytest.raises(DocumentExtractionError) as exc_info:
        DocumentService.extract_text_from_bytes(b"data", "file.xlsx")
    msg = str(exc_info.value)
    assert ".xlsx" in msg
    assert "PDF" in msg or "Supported" in msg


def test_chunk_text_basic():
    text = "The main users are doctors and patients. " * 20
    chunks = DocumentService.chunk_text(text, chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1
    for c in chunks:
        assert "content" in c
        assert "chunk_index" in c


def test_chunk_text_empty_returns_empty():
    assert DocumentService.chunk_text("") == []


def test_chunk_text_preserves_content():
    text = "Inventory management tracks stock levels and reorder points for warehouse operations."
    chunks = DocumentService.chunk_text(text, chunk_size=500)
    combined = " ".join(c["content"] for c in chunks)
    assert "Inventory" in combined
    assert "stock" in combined


# ─── RAG Service Tests ─────────────────────────────────────────────────────────

def _make_project(db, name="Test Project"):
    """Helper: create a workspace + project in the test DB."""
    user = User(email=f"{name.replace(' ','_')}@test.com", hashed_password="x", full_name=name)
    db.add(user)
    db.flush()
    ws = Workspace(name="WS", owner_id=user.id)
    db.add(ws)
    db.flush()
    proj = Project(name=name, workspace_id=ws.id, business_idea=f"Idea for {name}")
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj


def test_ingest_document_creates_knowledge_source(db):
    proj = _make_project(db, "Nutrition AI")
    rag = RAGService()
    txt = b"Daily nutrition requirements include Vitamin C, Iron, and Calcium for healthy adults."
    source = rag.ingest_document(db, proj.id, "nutrition.txt", txt)
    assert source.status == "READY"
    assert source.project_id == proj.id
    assert source.type == "DOCUMENT"
    chunks = db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_source_id == source.id).all()
    assert len(chunks) > 0


def test_ingest_document_chunks_have_project_id(db):
    proj = _make_project(db, "Inventory System")
    rag = RAGService()
    txt = b"Inventory management tracks stock levels, reorder points, and supplier lead times."
    source = rag.ingest_document(db, proj.id, "inventory.txt", txt)
    chunks = db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_source_id == source.id).all()
    for chunk in chunks:
        assert chunk.project_id == proj.id


def test_ingest_invalid_file_sets_failed_status(db):
    proj = _make_project(db, "Error Test Project")
    rag = RAGService()
    with pytest.raises(RAGError):
        rag.ingest_document(db, proj.id, "bad.xyz", b"garbage data")
    source = db.query(KnowledgeSource).filter(
        KnowledgeSource.project_id == proj.id
    ).first()
    assert source.status == "FAILED"


def test_ingest_nonexistent_project_raises_error(db):
    rag = RAGService()
    with pytest.raises(RAGError) as exc_info:
        rag.ingest_document(db, "nonexistent-project-id", "doc.txt", b"text")
    assert "not found" in str(exc_info.value).lower()


# ─── Project Isolation Tests ───────────────────────────────────────────────────

def test_rag_project_isolation(db):
    """
    Project A (nutrition) and Project B (inventory) must NOT share knowledge.
    Searching in Project A must NOT return Project B chunks and vice versa.
    """
    proj_a = _make_project(db, "Nutrition Assistant A")
    proj_b = _make_project(db, "Inventory System B")
    rag = RAGService()

    # Ingest nutrition doc into Project A
    nutrition_txt = b"Main users are nutritionists and patients tracking daily vitamin intake and dietary goals."
    rag.ingest_document(db, proj_a.id, "nutrition_req.txt", nutrition_txt)

    # Ingest inventory doc into Project B
    inventory_txt = b"Main users are warehouse managers and procurement officers tracking stock reorder levels."
    rag.ingest_document(db, proj_b.id, "inventory_req.txt", inventory_txt)

    # Search Project A for "users" — should return nutrition content
    results_a = rag.search_knowledge(db, proj_a.id, "main users", top_k=5)
    assert len(results_a) > 0
    combined_a = " ".join(r["content"] for r in results_a).lower()
    # Must NOT contain inventory-specific terms
    assert "warehouse" not in combined_a
    assert "procurement" not in combined_a

    # Search Project B for "users" — should return inventory content
    results_b = rag.search_knowledge(db, proj_b.id, "main users", top_k=5)
    assert len(results_b) > 0
    combined_b = " ".join(r["content"] for r in results_b).lower()
    # Must NOT contain nutrition-specific terms
    assert "nutritionist" not in combined_b
    assert "vitamin" not in combined_b


def test_search_empty_project_returns_empty(db):
    proj = _make_project(db, "Empty Knowledge Project")
    rag = RAGService()
    results = rag.search_knowledge(db, proj.id, "any query", top_k=5)
    assert results == []


def test_delete_knowledge_source_removes_chunks(db):
    proj = _make_project(db, "Delete Test Project")
    rag = RAGService()
    source = rag.ingest_document(db, proj.id, "delete_me.txt", b"Some content to be deleted from knowledge base.")
    source_id = source.id
    assert db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_source_id == source_id).count() > 0

    rag.delete_knowledge_source(db, source_id, proj.id)
    assert db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_source_id == source_id).count() == 0
    assert db.query(KnowledgeSource).filter(KnowledgeSource.id == source_id).first() is None


def test_delete_wrong_project_raises_error(db):
    proj_a = _make_project(db, "Owner Project")
    proj_b = _make_project(db, "Other Project")
    rag = RAGService()
    source = rag.ingest_document(db, proj_a.id, "doc.txt", b"Owner project content here.")

    with pytest.raises(RAGError):
        rag.delete_knowledge_source(db, source.id, proj_b.id)


# ─── Embedding Tests ───────────────────────────────────────────────────────────

def test_embedding_returns_correct_dimension():
    ep = EmbeddingProvider(api_key="mock-key")
    vec = ep.get_embedding("nutrition requirements for healthy adults")
    assert len(vec) == 128


def test_cosine_similarity_identical_vectors():
    ep = EmbeddingProvider(api_key="mock-key")
    vec = ep.get_embedding("inventory management system")
    sim = EmbeddingProvider.cosine_similarity(vec, vec)
    assert sim > 0.99


def test_cosine_similarity_different_vectors():
    ep = EmbeddingProvider(api_key="mock-key")
    vec1 = ep.get_embedding("nutrition vitamins health diet")
    vec2 = ep.get_embedding("warehouse inventory stock procurement")
    sim = EmbeddingProvider.cosine_similarity(vec1, vec2)
    # Different domain content should have lower similarity
    assert sim < 0.95
