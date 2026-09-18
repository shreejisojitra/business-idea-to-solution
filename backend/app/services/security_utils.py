"""
Module 10: File upload security + URL/SSRF protection utilities.
Used by knowledge.py, public_chatbot.py, and website_service.py.
"""
import ipaddress
import logging
import os
import re
import socket
from typing import Optional
from urllib.parse import urlparse

from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── File Upload Security ───────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {"pdf", "docx", "pptx", "txt", "csv", "md"}

# Magic bytes for supported binary formats (first bytes of file)
_MAGIC = {
    "pdf":  [b"%PDF"],
    "docx": [b"PK\x03\x04"],   # ZIP-based (OOXML)
    "pptx": [b"PK\x03\x04"],
}

# Dangerous filename patterns (path traversal, absolute paths, null bytes)
_DANGEROUS_FILENAME = re.compile(
    r"(\.\.[\\/])"           # ../  ..\
    r"|^[a-zA-Z]:[\\\/]"     # C:\  C:/
    r"|^[\/\\]"              # /etc  \windows
    r"|\x00"                 # null byte
)


def sanitize_filename(filename: Optional[str]) -> str:
    """
    Returns a safe basename, stripping path components and dangerous characters.
    Raises HTTPException 400 if the filename is empty or has no valid extension.
    """
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    # Strip path components — keep only the final basename
    safe = os.path.basename(filename.replace("\\", "/"))

    # Reject if dangerous pattern survived basename stripping (e.g. null bytes)
    if _DANGEROUS_FILENAME.search(safe):
        raise HTTPException(status_code=400, detail="Filename contains unsafe characters.")

    if not safe or safe.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    return safe


def validate_upload(file_bytes: bytes, filename: str) -> str:
    """
    Validates an uploaded file for:
    - Non-empty content
    - File size limit (uses settings.MAX_FILE_SIZE_BYTES)
    - Allowed extension
    - Magic bytes for binary formats (PDF, DOCX, PPTX)

    Returns the sanitized filename.
    Raises HTTPException with an appropriate status code on failure.
    """
    safe_name = sanitize_filename(filename)

    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(file_bytes) > settings.MAX_FILE_SIZE_BYTES:
        max_mb = settings.MAX_FILE_SIZE_BYTES / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum allowed size of {max_mb:.0f} MB.",
        )

    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
        )

    # Magic-byte check for binary formats
    if ext in _MAGIC:
        if not any(file_bytes.startswith(sig) for sig in _MAGIC[ext]):
            raise HTTPException(
                status_code=400,
                detail=f"File content does not match the declared '{ext}' format.",
            )

    return safe_name


# ── URL / SSRF Protection ──────────────────────────────────────────────────────

_BLOCKED_SCHEMES = {"file", "ftp", "javascript", "data", "gopher", "dict", "ldap", "ldaps"}

# Private / loopback / link-local IPv4 and IPv6 ranges
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # loopback
    ipaddress.ip_network("10.0.0.0/8"),       # private
    ipaddress.ip_network("172.16.0.0/12"),    # private
    ipaddress.ip_network("192.168.0.0/16"),   # private
    ipaddress.ip_network("169.254.0.0/16"),   # link-local
    ipaddress.ip_network("0.0.0.0/8"),        # "this" network
    ipaddress.ip_network("100.64.0.0/10"),    # shared address space
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]


def _is_private_ip(addr: str) -> bool:
    """Returns True if the IP address falls within a private/loopback/link-local range."""
    try:
        ip = ipaddress.ip_address(addr)
        return any(ip in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        return False


def validate_url_for_crawl(url: str) -> str:
    """
    Validates a URL before crawling:
    - Must be http or https
    - Must not use a blocked scheme
    - Must have a non-empty netloc
    - Hostname must not resolve to a private/loopback IP (SSRF protection)

    Returns the validated URL string.
    Raises HTTPException 400 on any violation.
    """
    url = url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required.")

    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed URL.")

    scheme = (parsed.scheme or "").lower()

    if scheme in _BLOCKED_SCHEMES:
        raise HTTPException(
            status_code=400,
            detail=f"URL scheme '{scheme}://' is not allowed.",
        )

    if scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail="Only http:// and https:// URLs are accepted.",
        )

    hostname = parsed.hostname or ""
    if not hostname:
        raise HTTPException(status_code=400, detail="URL must include a valid hostname.")

    # Reject bare IP addresses that are private
    if _is_private_ip(hostname):
        raise HTTPException(
            status_code=400,
            detail="Requests to private/internal network addresses are not allowed.",
        )

    # DNS resolution check — prevent hostname → private IP bypass
    try:
        resolved_addrs = socket.getaddrinfo(hostname, None)
        for addr_info in resolved_addrs:
            ip_str = addr_info[4][0]
            if _is_private_ip(ip_str):
                raise HTTPException(
                    status_code=400,
                    detail="URL resolves to a private/internal network address.",
                )
    except HTTPException:
        raise
    except OSError:
        # DNS resolution failed — let the crawler handle the connection error
        pass

    return url
