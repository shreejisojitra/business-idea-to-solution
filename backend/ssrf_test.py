"""Temporary SSRF + security validation script for Module 23 testing."""
import sys
sys.path.insert(0, '.')

from fastapi import HTTPException
from app.services.security_utils import validate_url_for_crawl, validate_upload

# SSRF tests
ssrf_blocked = [
    'file:///etc/passwd',
    'ftp://x.com',
    'javascript:alert(1)',
    'data:text/html,x',
    'http://localhost',
    'http://127.0.0.1',
    'http://192.168.1.1',
    'http://10.0.0.1',
    'http://169.254.169.254',
]

print("=== SSRF Protection Tests ===")
all_pass = True
for url in ssrf_blocked:
    try:
        validate_url_for_crawl(url)
        print(f"FAIL - not blocked: {url}")
        all_pass = False
    except HTTPException:
        print(f"PASS - blocked: {url}")

# File upload security tests
print("\n=== File Upload Security Tests ===")
try:
    validate_upload(b"", "test.txt")
    print("FAIL - empty file not rejected")
    all_pass = False
except HTTPException:
    print("PASS - empty file rejected")

try:
    validate_upload(b"content", "../../etc/passwd")
    print("FAIL - path traversal not rejected")
    all_pass = False
except HTTPException:
    print("PASS - path traversal rejected")

try:
    validate_upload(b"content", "malware.exe")
    print("FAIL - .exe not rejected")
    all_pass = False
except HTTPException:
    print("PASS - .exe rejected")

try:
    validate_upload(b"content", "test.txt")
    print("PASS - valid txt accepted")
except HTTPException as e:
    print(f"FAIL - valid txt rejected: {e.detail}")
    all_pass = False

print(f"\n{'ALL PASS' if all_pass else 'SOME FAILURES'}")
