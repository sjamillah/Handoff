"""Authentication and role rules, enforced on the server."""

import uuid

import pytest

from app.main import app
from tests.conftest import login, set_status, status_of

PUBLIC_PATHS = {"/auth/login", "/health"}
PROTECTED_ROUTES = sorted(
    (method.upper(), path)
    for path, operations in app.openapi()["paths"].items()
    if path not in PUBLIC_PATHS
    for method in operations
)


def test_every_route_except_login_and_health_is_checked():
    assert len(PROTECTED_ROUTES) >= 15


@pytest.mark.parametrize(("method", "path"), PROTECTED_ROUTES)
def test_unauthenticated_request_is_rejected(anon, method, path):
    url = path.replace("{request_id}", "1").replace("{user_id}", "1")
    url = url.replace("{episode_id}", "EP-1")
    assert anon.request(method, url, json={}).status_code == 401


def test_client_cannot_read_another_clients_request(client_a, client_b, make_request):
    request_id = make_request(owner=client_b)
    assert client_a.get(f"/requests/{request_id}").status_code == 404
    assert request_id not in [r["id"] for r in client_a.get("/requests").json()]


def test_client_cannot_change_another_clients_request(client_a, client_b, make_request, db):
    request_id = make_request(owner=client_b)
    set_status(db, request_id, "delivered")
    response = client_a.post(f"/requests/{request_id}/transitions", json={"to_status": "accepted"})
    assert response.status_code == 404
    assert status_of(db, request_id) == "delivered"


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/episodes", None),
        ("GET", "/analytics?from=2026-08-01&to=2026-08-31", None),
        ("POST", "/requests/{id}/transitions", {"to_status": "in_progress"}),
        ("POST", "/requests/{id}/assignments", {"episode_ids": ["EP-T00001"]}),
        ("DELETE", "/requests/{id}/assignments/EP-T00001", None),
    ],
)
def test_client_cannot_call_operator_endpoints(client_a, make_request, method, path, body):
    url = path.replace("{id}", str(make_request()))
    assert client_a.request(method, url, json=body).status_code == 403


def test_client_cannot_import_episodes(client_a):
    response = client_a.post("/episodes/import", files={"file": ("e.csv", b"episode_id\n")})
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        (
            "POST",
            "/admin/users",
            {"email": "x@example.com", "name": "X", "password": "password1", "role": "operator"},
        ),
        ("POST", "/admin/users/4/deactivate", None),
        ("PUT", "/admin/users/4/role", {"role": "operator"}),
    ],
)
def test_operator_cannot_use_admin_endpoints(operator, method, path, body):
    assert operator.request(method, path, json=body).status_code == 403


def test_inactive_user_cannot_log_in(admin, anon):
    user_id, email = create_operator(admin)
    assert admin.post(f"/admin/users/{user_id}/deactivate").status_code == 200
    response = anon.post("/auth/login", json={"email": email, "password": "password1"})
    assert response.status_code == 401


def test_inactive_user_loses_an_existing_session(admin):
    user_id, email = create_operator(admin)
    session = login(email, "password1")
    assert session.get("/episodes").status_code == 200
    admin.post(f"/admin/users/{user_id}/deactivate")
    assert session.get("/episodes").status_code == 401


def create_operator(admin):
    """Create an operator with a unique email through the admin API and return id and email."""
    email = f"op-{uuid.uuid4().hex[:8]}@example.com"
    response = admin.post(
        "/admin/users",
        json={"email": email, "name": "Temp", "password": "password1", "role": "operator"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"], email
