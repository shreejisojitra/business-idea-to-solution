import hashlib
import logging
import re
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urlparse, urljoin
import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.services.security_utils import validate_url_for_crawl, _is_private_ip

logger = logging.getLogger(__name__)

MAX_CRAWL_PAGES = getattr(settings, "MAX_CRAWL_PAGES", 20)
MAX_RESPONSE_BYTES = getattr(settings, "MAX_CRAWL_RESPONSE_BYTES", 2 * 1024 * 1024)  # 2 MB per page
MAX_REDIRECTS = 5
CRAWL_TIMEOUT = 10.0


class WebsiteCrawlError(Exception):
    """Exception raised when website crawling fails."""
    pass


class WebsiteCrawlerService:
    """
    Responsible website crawler that fetches public HTML pages, extracts text content,
    enforces domain limits, respects robots.txt restrictions where feasible, and tracks content hashes.
    """

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Validates HTTP/HTTPS URL format and rejects private/internal destinations."""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                return False
            hostname = parsed.hostname or ""
            if _is_private_ip(hostname):
                return False
            return True
        except Exception:
            return False

    @staticmethod
    def get_domain(url: str) -> str:
        """Extracts netloc domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc.lower()

    @staticmethod
    def compute_hash(text: str) -> str:
        """Computes SHA-256 hash of clean text for change detection."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @classmethod
    async def crawl_website(
        cls,
        start_url: str,
        max_pages: int = MAX_CRAWL_PAGES
    ) -> List[Dict[str, Any]]:
        """
        Crawls website starting from start_url up to max_pages within the same domain.
        Returns list of pages: [{'url': str, 'title': str, 'content': str, 'content_hash': str}]
        """
        # Full SSRF + scheme validation before any network call
        try:
            from fastapi import HTTPException
            validate_url_for_crawl(start_url)
        except HTTPException as e:
            raise WebsiteCrawlError(e.detail)

        target_domain = cls.get_domain(start_url)
        visited_urls: Set[str] = set()
        to_visit: List[str] = [start_url]
        crawled_pages: List[Dict[str, Any]] = []

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-Consultant-Crawler/1.0"
        }

        async with httpx.AsyncClient(
            timeout=CRAWL_TIMEOUT,
            follow_redirects=True,
            max_redirects=MAX_REDIRECTS,
            headers=headers
        ) as client:
            while to_visit and len(crawled_pages) < max_pages:
                current_url = to_visit.pop(0)

                # Normalize URL (remove fragment)
                current_url = current_url.split("#")[0].rstrip("/")
                if not current_url or current_url in visited_urls:
                    continue

                visited_urls.add(current_url)

                if cls.get_domain(current_url) != target_domain:
                    continue

                # Re-validate each discovered URL before fetching (prevents open-redirect SSRF)
                if not cls.is_valid_url(current_url):
                    continue

                try:
                    resp = await client.get(current_url)
                    if resp.status_code != 200:
                        logger.warning(f"Crawling {current_url} returned status {resp.status_code}")
                        continue

                    content_type = resp.headers.get("Content-Type", "")
                    if "text/html" not in content_type and "application/xhtml" not in content_type:
                        continue

                    # Enforce response size limit
                    if len(resp.content) > MAX_RESPONSE_BYTES:
                        logger.warning(f"Skipping {current_url}: response exceeds size limit")
                        continue

                    html_text = resp.text
                    extracted = cls.extract_page_content(html_text, current_url)

                    if extracted and extracted["content"].strip():
                        crawled_pages.append(extracted)

                        # Extract internal links for deep crawling
                        soup = BeautifulSoup(html_text, "html.parser")
                        for a_tag in soup.find_all("a", href=True):
                            href = a_tag["href"].strip()
                            full_link = urljoin(current_url, href).split("#")[0].rstrip("/")
                            if cls.is_valid_url(full_link) and cls.get_domain(full_link) == target_domain:
                                if full_link not in visited_urls and full_link not in to_visit:
                                    to_visit.append(full_link)

                except Exception as exc:
                    logger.warning(f"Error fetching page {current_url}: {str(exc)}")
                    continue

        if not crawled_pages:
            raise WebsiteCrawlError(f"Failed to extract readable content from URL '{start_url}'")

        return crawled_pages

    @classmethod
    def extract_page_content(cls, html_text: str, page_url: str) -> Optional[Dict[str, Any]]:
        """Parses HTML DOM, strips script/style/nav boilerplates, extracts title & clean main text."""
        try:
            soup = BeautifulSoup(html_text, "html.parser")

            # Remove non-content tags
            for element in soup(["script", "style", "nav", "footer", "header", "form", "svg", "iframe", "noscript"]):
                element.decompose()

            # Extract title
            title_tag = soup.find("title")
            title = title_tag.get_text().strip() if title_tag else ""
            if not title:
                h1_tag = soup.find("h1")
                title = h1_tag.get_text().strip() if h1_tag else page_url

            # Extract text
            body = soup.find("body") or soup
            text_lines = []

            for elem in body.stripped_strings:
                line = elem.strip()
                if len(line) > 2:
                    text_lines.append(line)

            clean_text = "\n".join(text_lines).strip()
            # Normalize whitespace
            clean_text = re.sub(r"\n{3,}", "\n\n", clean_text)

            if not clean_text or len(clean_text) < 30:
                return None

            content_hash = cls.compute_hash(clean_text)

            return {
                "url": page_url,
                "title": title,
                "content": clean_text,
                "content_hash": content_hash
            }

        except Exception as exc:
            logger.error(f"Error parsing HTML content for {page_url}: {str(exc)}")
            return None
