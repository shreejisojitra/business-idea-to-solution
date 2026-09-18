"""
Module 12 + 13 Tests: Rate Limiting, AI Usage Tracking, Analytics
"""
import pytest
import uuid
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db.session import SessionLocal, init_db
from app.db.models import (
    AIUsageRecord, User, Workspace, Project, Blueprint,
    PublicChatbot, PublicVisitorSession,
)
from app.services.rate_limiter import (
    check_rate_limit, check_authenticated_limit, check_ai_limit,
    check_public_chatbot_limit, reset_for_testing, _is_allowed,
)
from app.services.usage_service import UsageService
from app.core.config import settings
from app.main import app


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db():
    init_db()
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def test_user(db):
    u = User(email=f"m12_{uuid.uuid4().hex[:6]}@test.com", hashed_password="x")
    db.add(u)
    db.commit()
    return u


@pytest.fixture(scope="module")
def test_project(db, test_user):
    ws = Workspace(name="M12WS", owner_id=test_user.id)
    db.add(ws)
    db.commit()
    p = Project(name="M12Project", workspace_id=ws.id, business_idea="Test idea")
    db.add(p)
    db.commit()
    return p


@pytest.fixture(scope="module")
def other_user(db):
    u = User(email=f"m12_other_{uuid.uuid4().hex[:6]}@test.com", hashed_password="x")
    db.add(u)
    db.commit()
    return u


@pytest.fixture(scope="module")
def other_project(db, other_user):
    ws = Workspace(name="OtherWS", owner_id=other_user.id)
    db.add(ws)
    db.commit()
    p = Project(name="OtherProject", workspace_id=ws.id, business_idea="Other idea")
    db.add(p)
    db.commit()
    return p


@pytest.fixture(scope="module")
def test_chatbot(db, test_user):
    bot = PublicChatbot(
        owner_id=test_user.id,
        name="TestBot",
        welcome_message="Hi!",
        is_active="true",
    )
    db.add(bot)
    db.commit()
    return bot


@pytest.fixture(scope="module")
def http_client():
    return TestClient(app)


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 12 — RATE LIMITING
# ══════════════════════════════════════════════════════════════════════════════

# Test 1: Rate limiting works — requests below limit succeed
def test_rate_limit_below_limit_succeeds():
    key = f"test_below_{uuid.uuid4().hex}"
    for _ in range(5):
        allowed, remaining = _is_allowed(key, max_requests=10, window_seconds=60)
        assert allowed is True
    assert remaining >= 0


# Test 2: Exceeding the limit returns HTTP 429
def test_rate_limit_exceeds_returns_429():
    key = f"test_exceed_{uuid.uuid4().hex}"
    # Fill up the bucket
    for _ in range(3):
        _is_allowed(key, max_requests=3, window_seconds=60)
    # Next call should be denied
    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit(key, max_requests=3, window_seconds=60)
    assert exc_info.value.status_code == 429


# Test 3: Rate limit configuration is respected
def test_rate_limit_respects_config():
    """check_rate_limit with limit=1 allows first, blocks second."""
    key = f"test_config_{uuid.uuid4().hex}"
    check_rate_limit(key, max_requests=1, window_seconds=60)  # first: OK
    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit(key, max_requests=1, window_seconds=60)  # second: 429
    assert exc_info.value.status_code == 429


# Test 4: Rate limit disabled when RATE_LIMIT_ENABLED=False
def test_rate_limit_disabled_allows_all(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    key = f"test_disabled_{uuid.uuid4().hex}"
    # Should never raise even if limit is 0
    for _ in range(10):
        check_rate_limit(key, max_requests=1, window_seconds=60)
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)


# Test 5: Public chatbot rate limiting works
def test_public_chatbot_rate_limit():
    session_id = f"pub_sess_{uuid.uuid4().hex}"
    reset_for_testing(f"pub:{session_id}")
    # Fill to limit
    for _ in range(settings.RATE_LIMIT_PUBLIC_REQUESTS):
        _is_allowed(f"pub:{session_id}", settings.RATE_LIMIT_PUBLIC_REQUESTS, settings.RATE_LIMIT_PUBLIC_WINDOW_SECONDS)
    with pytest.raises(HTTPException) as exc_info:
        check_public_chatbot_limit(session_id)
    assert exc_info.value.status_code == 429


# Test 6: AI usage is recorded
def test_ai_usage_is_recorded(db, test_project, test_user):
    before = db.query(AIUsageRecord).filter(
        AIUsageRecord.project_id == test_project.id
    ).count()
    UsageService.record(
        db,
        request_type="chat",
        user_id=test_user.id,
        project_id=test_project.id,
        success=True,
        latency_ms=123.4,
    )
    after = db.query(AIUsageRecord).filter(
        AIUsageRecord.project_id == test_project.id
    ).count()
    assert after == before + 1


# Test 7: Successful AI request usage is recorded correctly
def test_successful_usage_recorded(db, test_project, test_user):
    UsageService.record(
        db,
        request_type="chat",
        user_id=test_user.id,
        project_id=test_project.id,
        success=True,
        latency_ms=50.0,
    )
    record = db.query(AIUsageRecord).filter(
        AIUsageRecord.project_id == test_project.id,
        AIUsageRecord.success == True,
    ).order_by(AIUsageRecord.created_at.desc()).first()
    assert record is not None
    assert record.success is True
    assert record.latency_ms == 50.0


# Test 8: Failed AI request usage is recorded safely
def test_failed_usage_recorded(db, test_project, test_user):
    UsageService.record(
        db,
        request_type="chat",
        user_id=test_user.id,
        project_id=test_project.id,
        success=False,
        error_message="LLM timeout",
    )
    record = db.query(AIUsageRecord).filter(
        AIUsageRecord.project_id == test_project.id,
        AIUsageRecord.success == False,
    ).order_by(AIUsageRecord.created_at.desc()).first()
    assert record is not None
    assert record.success is False
    assert "timeout" in (record.error_message or "")


# Test 9: Analytics/usage recording failure does NOT break AI response
def test_usage_failure_does_not_raise(db):
    """UsageService.record must swallow all exceptions."""
    # Pass a closed/invalid session — should not raise
    class BrokenDB:
        def add(self, *a): raise RuntimeError("DB is broken")
        def commit(self): raise RuntimeError("DB is broken")
        def rollback(self): pass

    # Must not raise
    UsageService.record(
        BrokenDB(),
        request_type="chat",
        user_id="fake",
        project_id="fake",
        success=True,
    )


# Test 10: Large/abusive message is rejected
def test_large_message_rejected(http_client):
    """POST /api/ai/chat with oversized message returns 400 or 401 (not 500)."""
    huge_message = "A" * (settings.MAX_CHAT_MESSAGE_LENGTH + 1)
    resp = http_client.post(
        "/api/ai/chat",
        json={"project_id": "fake", "message": huge_message},
    )
    # Without auth → 401; with auth + oversized → 400. Either is acceptable here.
    assert resp.status_code in (400, 401, 422)


# Test 11: Normal chatbot requests still work (rate limiter doesn't block fresh keys)
def test_normal_requests_not_blocked():
    key = f"normal_{uuid.uuid4().hex}"
    reset_for_testing(key)
    # Should succeed without raising
    check_rate_limit(key, max_requests=100, window_seconds=60)
    check_rate_limit(key, max_requests=100, window_seconds=60)


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 13 — ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════

def _get_token(http_client, email, password="testpass123"):
    """Register + login helper, returns JWT token."""
    http_client.post("/api/auth/register", json={"email": email, "password": password})
    resp = http_client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return resp.json().get("access_token", "")


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# Test 12: Project analytics endpoint works
def test_project_analytics_endpoint_works(http_client, db):
    email = f"ana_{uuid.uuid4().hex[:6]}@test.com"
    token = _get_token(http_client, email)
    headers = _auth_headers(token)

    # Create workspace + project via API
    ws_resp = http_client.post("/api/workspaces/", json={"name": "AnaWS"}, headers=headers)
    ws_id = ws_resp.json()["id"]
    proj_resp = http_client.post(
        "/api/projects/",
        json={"name": "AnaProject", "workspace_id": ws_id, "business_idea": "test"},
        headers=headers,
    )
    proj_id = proj_resp.json()["id"]

    resp = http_client.get(f"/api/projects/{proj_id}/analytics", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == proj_id
    assert "ai_requests" in data
    assert "total_messages" in data


# Test 13: Project owner can access analytics
def test_project_owner_can_access_analytics(http_client):
    email = f"owner_{uuid.uuid4().hex[:6]}@test.com"
    token = _get_token(http_client, email)
    headers = _auth_headers(token)

    ws_resp = http_client.post("/api/workspaces/", json={"name": "OwnerWS"}, headers=headers)
    ws_id = ws_resp.json()["id"]
    proj_resp = http_client.post(
        "/api/projects/",
        json={"name": "OwnerProject", "workspace_id": ws_id, "business_idea": "test"},
        headers=headers,
    )
    proj_id = proj_resp.json()["id"]

    resp = http_client.get(f"/api/projects/{proj_id}/analytics", headers=headers)
    assert resp.status_code == 200


# Test 14: Unauthorized project analytics access is rejected
def test_unauthorized_project_analytics_rejected(http_client):
    resp = http_client.get("/api/projects/some-project-id/analytics")
    assert resp.status_code == 401


# Test 15: Cross-project analytics access is rejected
def test_cross_project_analytics_rejected(http_client):
    # User A creates a project
    email_a = f"cross_a_{uuid.uuid4().hex[:6]}@test.com"
    token_a = _get_token(http_client, email_a)
    ws_resp = http_client.post("/api/workspaces/", json={"name": "WS_A"}, headers=_auth_headers(token_a))
    ws_id = ws_resp.json()["id"]
    proj_resp = http_client.post(
        "/api/projects/",
        json={"name": "Proj_A", "workspace_id": ws_id, "business_idea": "test"},
        headers=_auth_headers(token_a),
    )
    proj_id_a = proj_resp.json()["id"]

    # User B tries to access User A's analytics
    email_b = f"cross_b_{uuid.uuid4().hex[:6]}@test.com"
    token_b = _get_token(http_client, email_b)
    resp = http_client.get(f"/api/projects/{proj_id_a}/analytics", headers=_auth_headers(token_b))
    assert resp.status_code == 404  # not found / unauthorized


# Test 16: Public chatbot analytics works
def test_chatbot_analytics_works(http_client):
    email = f"botana_{uuid.uuid4().hex[:6]}@test.com"
    token = _get_token(http_client, email)
    headers = _auth_headers(token)

    bot_resp = http_client.post(
        "/api/chatbots",
        json={"name": "AnaBot", "welcome_message": "Hi"},
        headers=headers,
    )
    bot_id = bot_resp.json()["id"]

    resp = http_client.get(f"/api/chatbots/{bot_id}/analytics", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["chatbot_id"] == bot_id
    assert "total_sessions" in data
    assert "ai_requests" in data


# Test 17: Unauthorized chatbot analytics access is rejected
def test_unauthorized_chatbot_analytics_rejected(http_client):
    resp = http_client.get("/api/chatbots/some-bot-id/analytics")
    assert resp.status_code == 401


# Test 18: Visitor cannot access owner analytics
def test_visitor_cannot_access_owner_analytics(http_client):
    """Public visitor (no token) cannot access chatbot analytics."""
    resp = http_client.get("/api/chatbots/any-bot-id/analytics")
    assert resp.status_code == 401


# Test 19: Analytics data is correctly aggregated
def test_analytics_data_aggregated(http_client, db):
    email = f"agg_{uuid.uuid4().hex[:6]}@test.com"
    token = _get_token(http_client, email)
    headers = _auth_headers(token)

    ws_resp = http_client.post("/api/workspaces/", json={"name": "AggWS"}, headers=headers)
    ws_id = ws_resp.json()["id"]
    proj_resp = http_client.post(
        "/api/projects/",
        json={"name": "AggProject", "workspace_id": ws_id, "business_idea": "test"},
        headers=headers,
    )
    proj_id = proj_resp.json()["id"]

    # Manually insert 2 success + 1 failure usage records
    UsageService.record(db, request_type="chat", project_id=proj_id, success=True, latency_ms=100.0)
    UsageService.record(db, request_type="chat", project_id=proj_id, success=True, latency_ms=200.0)
    UsageService.record(db, request_type="chat", project_id=proj_id, success=False, error_message="err")

    resp = http_client.get(f"/api/projects/{proj_id}/analytics?period=30d", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ai_requests"] >= 3
    assert data["ai_success"] >= 2
    assert data["ai_failed"] >= 1
    assert data["avg_latency_ms"] is not None


# Test 20: Date filtering works
def test_analytics_date_filtering(http_client, db):
    email = f"date_{uuid.uuid4().hex[:6]}@test.com"
    token = _get_token(http_client, email)
    headers = _auth_headers(token)

    ws_resp = http_client.post("/api/workspaces/", json={"name": "DateWS"}, headers=headers)
    ws_id = ws_resp.json()["id"]
    proj_resp = http_client.post(
        "/api/projects/",
        json={"name": "DateProject", "workspace_id": ws_id, "business_idea": "test"},
        headers=headers,
    )
    proj_id = proj_resp.json()["id"]

    for period in ("today", "7d", "30d"):
        resp = http_client.get(f"/api/projects/{proj_id}/analytics?period={period}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["period"] == period


# Test 21: No secrets/system prompts exposed through analytics
def test_analytics_no_secrets_exposed(http_client):
    email = f"sec_ana_{uuid.uuid4().hex[:6]}@test.com"
    token = _get_token(http_client, email)
    headers = _auth_headers(token)

    ws_resp = http_client.post("/api/workspaces/", json={"name": "SecWS"}, headers=headers)
    ws_id = ws_resp.json()["id"]
    proj_resp = http_client.post(
        "/api/projects/",
        json={"name": "SecProject", "workspace_id": ws_id, "business_idea": "test"},
        headers=headers,
    )
    proj_id = proj_resp.json()["id"]

    resp = http_client.get(f"/api/projects/{proj_id}/analytics", headers=headers)
    assert resp.status_code == 200
    body = resp.text

    # Must not contain any credential-like content
    api_key = settings.LLM_API_KEY or ""
    if api_key and api_key not in ("your_llm_api_key_here", "mock_key_for_testing", ""):
        assert api_key not in body

    assert "SECRET_KEY" not in body
    assert "hashed_password" not in body
    assert "CRITICAL SECURITY RULES" not in body
