import logging
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.models import KnowledgeSource, KnowledgeChunk, WebsitePage, Project
from app.services.document_service import DocumentService, DocumentExtractionError
from app.services.ai.embeddings import EmbeddingProvider
from app.services.ai.website_service import WebsiteCrawlerService, WebsiteCrawlError

logger = logging.getLogger(__name__)


class RAGError(Exception):
    """Exception raised when RAG operations fail."""
    pass


class RAGService:
    """
    RAG Service handling document ingestion, website crawling, semantic chunk embedding storage,
    hybrid knowledge retrieval, website refresh, and strict project isolation.
    """

    def __init__(self, embedding_provider: Optional[EmbeddingProvider] = None):
        self.embedding_provider = embedding_provider or EmbeddingProvider()

    def ingest_document(
        self,
        db: Session,
        project_id: str,
        filename: str,
        file_bytes: bytes,
        source_name: Optional[str] = None
    ) -> KnowledgeSource:
        """Processes document upload, extracts text, chunks, embeds, and stores knowledge."""
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise RAGError(f"Project '{project_id}' not found.")

        name = source_name or filename
        source = KnowledgeSource(
            project_id=project_id,
            type="DOCUMENT",
            name=name,
            filename=filename,
            status="PROCESSING"
        )
        db.add(source)
        db.commit()

        try:
            raw_text = DocumentService.extract_text_from_bytes(file_bytes, filename)
            source.extracted_text = raw_text

            chunks_data = DocumentService.chunk_text(raw_text)
            for idx, c in enumerate(chunks_data):
                chunk_text = c["content"]
                vec = self.embedding_provider.get_embedding(chunk_text)

                chunk = KnowledgeChunk(
                    knowledge_source_id=source.id,
                    project_id=project_id,
                    chunk_index=idx,
                    content=chunk_text,
                    page_number=c.get("page_number"),
                    section_heading=c.get("section_heading"),
                    source_url=None,
                    embedding=vec
                )
                db.add(chunk)

            source.status = "READY"
            db.commit()
            db.refresh(source)
            return source

        except Exception as exc:
            source.status = "FAILED"
            source.meta_data = {"error": str(exc)}
            db.commit()
            logger.error(f"Failed to ingest document '{filename}' for project {project_id}: {str(exc)}")
            raise RAGError(f"Document processing failed: {str(exc)}") from exc

    async def ingest_website(
        self,
        db: Session,
        project_id: str,
        start_url: str,
        source_name: Optional[str] = None,
        max_pages: int = 50
    ) -> KnowledgeSource:
        """Crawls website URL, processes pages, creates chunks, embeds, and stores knowledge."""
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise RAGError(f"Project '{project_id}' not found.")

        domain = WebsiteCrawlerService.get_domain(start_url)
        name = source_name or f"Website ({domain})"

        source = KnowledgeSource(
            project_id=project_id,
            type="WEBSITE",
            name=name,
            source_url=start_url,
            status="PROCESSING"
        )
        db.add(source)
        db.commit()

        try:
            pages = await WebsiteCrawlerService.crawl_website(start_url, max_pages=max_pages)
            combined_text_parts = []

            for page_idx, page in enumerate(pages):
                web_page = WebsitePage(
                    knowledge_source_id=source.id,
                    project_id=project_id,
                    url=page["url"],
                    title=page["title"],
                    content=page["content"],
                    content_hash=page["content_hash"],
                    status="READY"
                )
                db.add(web_page)
                combined_text_parts.append(f"--- URL: {page['url']} ({page['title']}) ---\n{page['content']}")

                # Chunk page content
                chunks_data = DocumentService.chunk_text(page["content"], default_heading=page["title"])
                for idx, c in enumerate(chunks_data):
                    chunk_text = c["content"]
                    vec = self.embedding_provider.get_embedding(chunk_text)

                    chunk = KnowledgeChunk(
                        knowledge_source_id=source.id,
                        project_id=project_id,
                        chunk_index=len(source.chunks) if source.chunks else idx,
                        content=chunk_text,
                        page_number=None,
                        section_heading=c.get("section_heading") or page["title"],
                        source_url=page["url"],
                        embedding=vec
                    )
                    db.add(chunk)

            source.extracted_text = "\n\n".join(combined_text_parts)
            source.status = "READY"
            db.commit()
            db.refresh(source)
            return source

        except Exception as exc:
            source.status = "FAILED"
            source.meta_data = {"error": str(exc)}
            db.commit()
            logger.error(f"Failed to ingest website '{start_url}' for project {project_id}: {str(exc)}")
            raise RAGError(f"Website ingestion failed: {str(exc)}") from exc

    async def refresh_website(self, db: Session, knowledge_source_id: str, project_id: str) -> KnowledgeSource:
        """Re-crawls website knowledge source, checks page content hashes, updates modified pages & chunks."""
        source = db.query(KnowledgeSource).filter(
            KnowledgeSource.id == knowledge_source_id,
            KnowledgeSource.project_id == project_id,
            KnowledgeSource.type == "WEBSITE"
        ).first()

        if not source:
            raise RAGError("Website knowledge source not found or project access denied.")

        source.status = "PROCESSING"
        db.commit()

        try:
            fresh_pages = await WebsiteCrawlerService.crawl_website(source.source_url)
            existing_pages = {p.url: p for p in db.query(WebsitePage).filter(WebsitePage.knowledge_source_id == source.id).all()}

            # Delete old chunks
            db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_source_id == source.id).delete()

            combined_text_parts = []
            for page in fresh_pages:
                url = page["url"]
                content_hash = page["content_hash"]

                if url in existing_pages:
                    wp = existing_pages[url]
                    wp.title = page["title"]
                    wp.content = page["content"]
                    wp.content_hash = content_hash
                    wp.status = "READY"
                else:
                    wp = WebsitePage(
                        knowledge_source_id=source.id,
                        project_id=project_id,
                        url=url,
                        title=page["title"],
                        content=page["content"],
                        content_hash=content_hash,
                        status="READY"
                    )
                    db.add(wp)

                combined_text_parts.append(f"--- URL: {page['url']} ({page['title']}) ---\n{page['content']}")

                # Create updated chunks
                chunks_data = DocumentService.chunk_text(page["content"], default_heading=page["title"])
                for idx, c in enumerate(chunks_data):
                    chunk_text = c["content"]
                    vec = self.embedding_provider.get_embedding(chunk_text)

                    chunk = KnowledgeChunk(
                        knowledge_source_id=source.id,
                        project_id=project_id,
                        chunk_index=idx,
                        content=chunk_text,
                        page_number=None,
                        section_heading=c.get("section_heading") or page["title"],
                        source_url=url,
                        embedding=vec
                    )
                    db.add(chunk)

            source.extracted_text = "\n\n".join(combined_text_parts)
            source.status = "READY"
            db.commit()
            db.refresh(source)
            return source

        except Exception as exc:
            source.status = "FAILED"
            source.meta_data = {"error": str(exc)}
            db.commit()
            raise RAGError(f"Website refresh failed: {str(exc)}") from exc

    def delete_knowledge_source(self, db: Session, knowledge_source_id: str, project_id: str):
        """Deletes a knowledge source and all its associated chunks and website pages."""
        source = db.query(KnowledgeSource).filter(
            KnowledgeSource.id == knowledge_source_id,
            KnowledgeSource.project_id == project_id
        ).first()

        if not source:
            raise RAGError("Knowledge source not found or project access denied.")

        db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_source_id == source.id).delete()
        db.query(WebsitePage).filter(WebsitePage.knowledge_source_id == source.id).delete()
        db.delete(source)
        db.commit()

    def search_knowledge(
        self,
        db: Session,
        project_id: str,
        query: str,
        top_k: int = 5,
        min_score: float = 0.02
    ) -> List[Dict[str, Any]]:
        """
        Performs project-scoped hybrid semantic vector search + keyword matching.
        Strictly filters by project_id for multi-tenant security isolation.
        """
        if not query.strip():
            return []

        # Enforce project-scoped query
        chunks = db.query(KnowledgeChunk).filter(
            KnowledgeChunk.project_id == project_id
        ).all()

        if not chunks:
            return []

        query_vec = self.embedding_provider.get_embedding(query)
        query_words = set(re.findall(r"\w+", query.lower()))

        scored_results = []
        for c in chunks:
            # 1. Semantic Similarity Score
            semantic_score = 0.0
            if c.embedding:
                semantic_score = EmbeddingProvider.cosine_similarity(query_vec, c.embedding)

            # 2. Keyword Match Score
            keyword_score = 0.0
            if query_words and c.content:
                chunk_words = set(re.findall(r"\w+", c.content.lower()))
                matches = query_words.intersection(chunk_words)
                keyword_score = len(matches) / max(len(query_words), 1)

            # Hybrid Score (70% Semantic + 30% Keyword)
            hybrid_score = (0.7 * semantic_score) + (0.3 * keyword_score)

            if hybrid_score >= min_score:
                # Fetch source details
                ks = c.knowledge_source
                source_name = ks.name if ks else "Document"
                source_type = ks.type if ks else "DOCUMENT"
                filename = ks.filename if ks else None

                scored_results.append({
                    "chunk_id": c.id,
                    "knowledge_source_id": c.knowledge_source_id,
                    "source_name": source_name,
                    "source_type": source_type,
                    "filename": filename,
                    "source_url": c.source_url or (ks.source_url if ks else None),
                    "page_number": c.page_number,
                    "section_heading": c.section_heading,
                    "content": c.content,
                    "score": round(float(hybrid_score), 4)
                })

        # Sort by hybrid score descending
        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return scored_results[:top_k]
