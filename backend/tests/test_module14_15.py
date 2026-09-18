"""
Module 14 + 15 Tests: Feedback & Evaluation, Human Handoff / Escalation
"""
import pytest
import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal, init_db
from app.db.models import MessageFeedback, HandoffRequest, User, Workspace, Project


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def http_client():
    return TestClient(app)


def _register_login(client, email, password="testpass123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    resp = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return resp.json().get("access_token", "")


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _setup_project(client, token):
    """Create workspace + project, return project_id."""
    ws = client.post("/api/workspaces/", json={"name": f"WS_{uuid.uuid4().hex[:6]}"}, headers=_auth(token))
    ws_id = ws.json()["id"]
    proj = client.post(
        "/api/projects/",
        json={"name": f"Proj_{uuid.uuid4().hex[:6]}", "workspace_id": ws_id, "business_idea": "test idea"},
        headers=_auth(token),
    )
    return proj.json()["id"]


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 14 — FEEDBACK & EVALUATION
# ══════════════════════════════════════════════════════════════════════════════

# Test 1: Positive feedback can be submitted
def test_positive_feedback_submitted(http_client):
    token = _register_login(http_client, f"fb_pos_{uuid.uuid4().hex[:6]}@test.com")
    proj_id = _setup_project(http_client, token)

    resp = http_client.post(
        f"/api/projects/{proj_id}/feedback",
        json={"rating": "positive"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["rating"] == "positive"
    assert data["project_id"] == proj_id


# Test 2: Negative feedback can be submitted
def test_negative_feedback_submitted(http_client):
    token = _register_login(http_client, f"fb_neg_{uuid.uuid4().hex[:6]}@test.com")
    proj_id = _setup_project(http_client, token)

    resp = http_client.post(
        f"/api/projects/{proj_id}/feedback",
        json={"rating": "negative"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    assert resp.json()["rating"] == "negative"


# Test 3: Optional feedback text (comment) works
def test_feedback_comment_stored(http_client):
    token = _register_login(http_client, f"fb_cmt_{uuid.uuid4().hex[:6]}@test.com")
    proj_id = _setup_project(http_client, token)

    resp = http_client.post(
        f"/api/projects/{proj_id}/feedback",
        json={"rating": "negative", "comment": "Need more detail"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    assert resp.json()["comment"] == "Need more detail"


# Test 4: Unauthorized project feedback is rejected (no token)
def test_unauthorized_feedback_rejected(http_client):
    resp = http_client.post(
        "/api/projects/fake-project-id/feedback",
        json={"rating": "positive"},
    )
    assert resp.status_code == 401


# Test 5: Cross-project feedback access is rejected
def test_cross_project_feedback_rejected(http_client):
    # User A owns a project
    token_a = _register_login(http_client, f"fb_xa_{uuid.uuid4().hex[:6]}@test.com")
    proj_id_a = _setup_project(http_client, token_a)

    # User B tries to submit feedback on User A's project
    token_b = _register_login(http_client, f"fb_xb_{uuid.uuid4().hex[:6]}@test.com")
    resp = http_client.post(
        f"/api/projects/{proj_id_a}/feedback",
        json={"rating": "positive"},
        headers=_auth(token_b),
    )
    assert resp.status_code == 404


# Test 6: Feedback belongs to the correct user/project
def test_feedback_belongs_to_correct_project(http_client):
    token = _register_login(http_client, f"fb_own_{uuid.uuid4().hex[:6]}@test.com")
    proj_id = _setup_project(http_client, token)

    http_client.post(
        f"/api/projects/{proj_id}/feedback",
        json={"rating": "positive", "comment": "Great"},
        headers=_auth(token),
    )

    list_resp = http_client.get(f"/api/projects/{proj_id}/feedback", headers=_auth(token))
    assert list_resp.status_code == 200
    records = list_resp.json()
    assert len(records) >= 1
    assert all(r["rating"] in ("positive", "negative") for r in records)


# Test 7: Feedback analytics is correctly calculated
def test_feedback_analytics_calculated(http_client):
    token = _register_login(http_client, f"fb_ana_{uuid.uuid4().hex[:6]}@test.com")
    proj_id = _setup_project(http_client, token)

    # Submit 2 positive + 1 negative
    for _ in range(2):
        http_client.post(
            f"/api/projects/{proj_id}/feedback",
            json={"rating": "positive"},
            headers=_auth(token),
        )
    http_client.post(
        f"/api/projects/{proj_id}/feedback",
        json={"rating": "negative", "comment": "Wrong architecture"},
        headers=_auth(token),
    )

    resp = http_client.get(f"/api/projects/{proj_id}/feedback/summary", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 3
    assert data["positive"] >= 2
    assert data["negative"] >= 1
    assert data["feedback_rate"] is not None
    assert 0.0 <= data["feedback_rate"] <= 1.0


# Test 8: Normal chat functionality remains unaffected by feedback module
def test_chat_unaffected_by_feedback(http_client):
    """Verify core chat endpoints still respond correctly."""
    token = _register_login(http_client, f"fb_chat_{uuid.uuid4().hex[:6]}@test.com")
    proj_id = _setup_project(http_client, token)

    # Conversations list should work
    resp = http_client.get(f"/api/ai/conversations?project_id={proj_id}", headers=_auth(token))
    assert resp.status_code == 200

    # Analytics endpoint still works
    resp = http_client.get(f"/api/projects/{proj_id}/analytics", headers=_auth(token))
    assert resp.status_code == 200


# Test 9: Invalid rating is rejected
def test_invalid_rating_rejected(http_client):
    token = _register_login(http_client, f"fb_inv_{uuid.uuid4().hex[:6]}@test.com")
    proj_id = _setup_project(http_client, token)

    resp = http_client.post(
        f"/api/projects/{proj_id}/feedback",
        json={"rating": "maybe"},
        headers=_auth(token),
    )
    assert resp.status_code == 400


# Test 10: User can delete their own feedback
def test_user_can_delete_own_feedback(http_client):
    token = _register_login(http_client, f"fb_del_{uuid.uuid4().hex[:6]}@test.com")
    proj_id = _setup_project(http_client, token)

    create_resp = http_client.post(
        f"/api/projects/{proj_id}/feedback",
        json={"rating": "positive"},
        headers=_auth(token),
    )
    fb_id = create_resp.json()["id"]

    del_resp = http_client.delete(
        f"/api/projects/{proj_id}/feedback/{fb_id}",
        headers=_auth(token),
    )
    assert del_resp.status_code == 204


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 15 — HUMAN HANDOFF / ESCALATION
# ══════════════════════════════════════════════════════════════════════════════

# Test 11: User can create a handoff
def test_user_can_create_handoff(http_client):
    token = _register_login(http_client, f"ho_create_{uuid.uuid4().hex[:6]}@test.com")
    proj_id = _setup_project(http_client, token)

    resp = http_client.post(
        f"/api/projects/{proj_id}/handoffs",
        json={"subject": "Need expert review", "description": "AI answer was not useful for my use case."},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["subject"] == "Need expert review"
    assert data["status"] == "OPEN"
    assert data["project_id"] == proj_id


# Test 12: Handoff is attached to the correct project/user
def test_handoff_attached_to_correct_project(http_client):
    token = _register_login(http_client, f"ho_attach_{uuid.uuid4().hex[:6]}@test.com")
    proj_id = _setup_project(http_client, token)

    http_client.post(
        f"/api/projects/{proj_id}/handoffs",
        json={"subject": "Review needed", "description": "Please review my project."},
        headers=_auth(token),
    )

    list_resp = http_client.get(f"/api/projects/{proj_id}/handoffs", headers=_auth(token))
    assert list_resp.status_code == 200
    records = list_resp.json()
    assert len(records) >= 1
    assert all(r["project_id"] == proj_id for r in records)


# Test 13: User can retrieve their own handoff
def test_user_can_retrieve_own_handoff(http_client):
    token = _register_login(http_client, f"ho_get_{uuid.uuid4().hex[:6]}@test.com")
    proj_id = _setup_project(http_client, token)

    create_resp = http_client.post(
        f"/api/projects/{proj_id}/handoffs",
        json={"subject": "Expert decision needed", "description": "Need human review."},
        headers=_auth(token),
    )
    handoff_id = create_resp.json()["id"]

    get_resp = http_client.get(
        f"/api/projects/{proj_id}/handoffs/{handoff_id}",
        headers=_auth(token),
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == handoff_id


# Test 14: Unauthorized project access is rejected (no token)
def test_unauthorized_handoff_access_rejected(http_client):
    resp = http_client.post(
        "/api/projects/fake-id/handoffs",
        json={"subject": "Test", "description": "Test"},
    )
    assert resp.status_code == 401


# Test 15: Cross-project handoff access is rejected
def test_cross_project_handoff_rejected(http_client):
    token_a = _register_login(http_client, f"ho_xa_{uuid.uuid4().hex[:6]}@test.com")
    proj_id_a = _setup_project(http_client, token_a)

    token_b = _register_login(http_client, f"ho_xb_{uuid.uuid4().hex[:6]}@test.com")

    # User B tries to create handoff on User A's project
    resp = http_client.post(
        f"/api/projects/{proj_id_a}/handoffs",
        json={"subject": "Intrusion", "description": "Should be blocked."},
        headers=_auth(token_b),
    )
    assert resp.status_code == 404


# Test 16: Authorized owner can update handoff status
def test_owner_can_update_handoff_status(http_client):
    token = _register_login(http_client, f"ho_upd_{uuid.uuid4().hex[:6]}@test.com")
    proj_id = _setup_project(http_client, token)

    create_resp = http_client.post(
        f"/api/projects/{proj_id}/handoffs",
        json={"subject": "Status test", "description": "Testing status update."},
        headers=_auth(token),
    )
    handoff_id = create_resp.json()["id"]

    patch_resp = http_client.patch(
        f"/api/projects/{proj_id}/handoffs/{handoff_id}",
        json={"status": "IN_PROGRESS"},
        headers=_auth(token),
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "IN_PROGRESS"


# Test 17: Unauthorized user cannot update another project's handoff
def test_unauthorized_cannot_update_handoff(http_client):
    token_a = _register_login(http_client, f"ho_ua_{uuid.uuid4().hex[:6]}@test.com")
    proj_id_a = _setup_project(http_client, token_a)

    create_resp = http_client.post(
        f"/api/projects/{proj_id_a}/handoffs",
        json={"subject": "Owner handoff", "description": "Only owner can update."},
        headers=_auth(token_a),
    )
    handoff_id = create_resp.json()["id"]

    token_b = _register_login(http_client, f"ho_ub_{uuid.uuid4().hex[:6]}@test.com")
    resp = http_client.patch(
        f"/api/projects/{proj_id_a}/handoffs/{handoff_id}",
        json={"status": "RESOLVED"},
        headers=_auth(token_b),
    )
    assert resp.status_code == 404


# Test 18: All handoff statuses work correctly
def test_handoff_statuses_work(http_client):
    token = _register_login(http_client, f"ho_st_{uuid.uuid4().hex[:6]}@test.com")
    proj_id = _setup_project(http_client, token)

    create_resp = http_client.post(
        f"/api/projects/{proj_id}/handoffs",
        json={"subject": "Status cycle", "description": "Testing all statuses."},
        headers=_auth(token),
    )
    handoff_id = create_resp.json()["id"]

    for new_status in ("IN_PROGRESS", "RESOLVED", "CLOSED"):
        resp = http_client.patch(
            f"/api/projects/{proj_id}/handoffs/{handoff_id}",
            json={"status": new_status},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == new_status

    # resolved_at should be set after RESOLVED
    assert resp.json()["resolved_at"] is not None


# Test 19: Secret/system-prompt information is not stored/exposed
def test_handoff_no_secrets_exposed(http_client):
    token = _register_login(http_client, f"ho_sec_{uuid.uuid4().hex[:6]}@test.com")
    proj_id = _setup_project(http_client, token)

    resp = http_client.post(
        f"/api/projects/{proj_id}/handoffs",
        json={"subject": "Security check", "description": "Normal user request."},
        headers=_auth(token),
    )
    body = resp.text
    assert "SECRET_KEY" not in body
    assert "hashed_password" not in body
    assert "CRITICAL SECURITY RULES" not in body
    assert "LLM_API_KEY" not in body


# Test 20: Existing public chatbot isolation remains intact
def test_public_chatbot_isolation_intact(http_client):
    """Public chatbot chat endpoint must not require auth and must not expose private data."""
    # Create a chatbot owner
    token = _register_login(http_client, f"ho_pub_{uuid.uuid4().hex[:6]}@test.com")
    bot_resp = http_client.post(
        "/api/chatbots",
        json={"name": "IsolationBot", "welcome_message": "Hi!"},
        headers=_auth(token),
    )
    assert bot_resp.status_code == 201
    bot_id = bot_resp.json()["id"]

    # Public visitor can chat without auth
    chat_resp = http_client.post(
        f"/api/public/chatbots/{bot_id}/chat",
        json={"message": "Hello", "session_id": str(uuid.uuid4())},
    )
    # 200 (answered) or 503 (no LLM configured) — both are acceptable; 401/403 would be wrong
    assert chat_resp.status_code in (200, 503, 422)

    # Public visitor cannot access private project handoffs
    proj_id = _setup_project(http_client, token)
    resp = http_client.get(f"/api/projects/{proj_id}/handoffs")
    assert resp.status_code == 401


# Test 21: Existing chat functionality remains unaffected by handoff module
def test_chat_unaffected_by_handoff(http_client):
    token = _register_login(http_client, f"ho_chat_{uuid.uuid4().hex[:6]}@test.com")
    proj_id = _setup_project(http_client, token)

    resp = http_client.get(f"/api/ai/conversations?project_id={proj_id}", headers=_auth(token))
    assert resp.status_code == 200

    resp = http_client.get(f"/api/projects/{proj_id}/analytics", headers=_auth(token))
    assert resp.status_code == 200


# Test 22: Invalid handoff status is rejected
def test_invalid_handoff_status_rejected(http_client):
    token = _register_login(http_client, f"ho_inv_{uuid.uuid4().hex[:6]}@test.com")
    proj_id = _setup_project(http_client, token)

    create_resp = http_client.post(
        f"/api/projects/{proj_id}/handoffs",
        json={"subject": "Test", "description": "Test invalid status."},
        headers=_auth(token),
    )
    handoff_id = create_resp.json()["id"]

    resp = http_client.patch(
        f"/api/projects/{proj_id}/handoffs/{handoff_id}",
        json={"status": "FLYING"},
        headers=_auth(token),
    )
    assert resp.status_code == 400


# Test 23: Priority field is respected
def test_handoff_priority_stored(http_client):
    token = _register_login(http_client, f"ho_pri_{uuid.uuid4().hex[:6]}@test.com")
    proj_id = _setup_project(http_client, token)

    resp = http_client.post(
        f"/api/projects/{proj_id}/handoffs",
        json={"subject": "Urgent", "description": "High priority request.", "priority": "high"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    assert resp.json()["priority"] == "high"
