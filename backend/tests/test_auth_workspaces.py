import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_auth_registration_login_flow():
    """Test user registration, login, and protected route access."""
    uid = uuid.uuid4().hex[:8]
    email = f"testuser_{uid}@example.com"
    password = "SecurePassword123!"

    # 1. Register user
    reg_response = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "full_name": "Test User"}
    )
    assert reg_response.status_code in [200, 201]
    reg_data = reg_response.json()
    assert "access_token" in reg_data
    token = reg_data["access_token"]

    # 2. Login user
    login_response = client.post(
        "/api/auth/login",
        data={"username": email, "password": password}
    )
    assert login_response.status_code == 200
    login_data = login_response.json()
    # Tokens are freshly issued each time (different iat), so verify the login
    # token is valid by using it to access a protected route
    assert "access_token" in login_data
    login_token = login_data["access_token"]

    # 3. Access protected route GET /api/auth/me (use login token)
    headers = {"Authorization": f"Bearer {login_token}"}
    me_response = client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 200
    me_data = me_response.json()
    assert me_data["email"] == email


def test_workspace_and_project_crud():
    """Test workspace creation and project creation."""
    uid = uuid.uuid4().hex[:8]
    email = f"wsp_user_{uid}@example.com"
    # Register user
    reg_response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "full_name": "WSP User"}
    )
    token = reg_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. List default workspace
    ws_list = client.get("/api/workspaces/", headers=headers).json()
    assert len(ws_list) >= 1
    ws_id = ws_list[0]["id"]

    # 2. Create new project
    proj_response = client.post(
        "/api/projects/",
        headers=headers,
        json={
            "name": "Hospital Booking System",
            "workspace_id": ws_id,
            "business_idea": "Hospital appointment booking is handled manually via phone calls."
        }
    )
    assert proj_response.status_code == 200
    proj_data = proj_response.json()
    assert proj_data["name"] == "Hospital Booking System"
    assert proj_data["status"] == "DRAFT"
