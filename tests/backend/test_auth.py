from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.testclient import TestClient

from backend.auth import AuthManager, SESSION_COOKIE
from backend.config.settings import Settings


def _request(client: TestClient, path: str = "/"):
    return client.build_request("GET", path)


def test_auth_manager_login_logout(tmp_path: Path):
    settings = Settings(
        app_username="tester",
        app_password="secret",
        auth_session_db=str(tmp_path / "auth.sqlite3"),
        app_env="test",
    )
    auth = AuthManager(settings)

    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI()

    @app.get("/")
    async def protected(request: Request):
        if not auth.current_user(request):
            return JSONResponse({"detail": "Authentication required."}, status_code=401)
        return {"ok": True}

    @app.post("/login")
    async def login(request: Request):
        token, error, status = auth.login(request, "tester", "secret")
        assert error is None
        response = JSONResponse({"ok": True})
        response.set_cookie(value=token, **auth.cookie_kwargs())
        return response

    @app.post("/logout")
    async def logout(request: Request):
        auth.logout(request)
        response = JSONResponse({"ok": True})
        response.delete_cookie(**auth.clear_cookie_kwargs())
        return response

    client = TestClient(app)
    assert client.get("/").status_code == 401

    login = client.post("/login")
    assert login.status_code == 200
    assert SESSION_COOKIE in client.cookies

    assert client.get("/").status_code == 200

    logout = client.post("/logout")
    assert logout.status_code == 200
    assert client.get("/").status_code == 401


def test_auth_manager_rejects_wrong_password(tmp_path: Path):
    settings = Settings(
        app_username="tester",
        app_password="secret",
        auth_session_db=str(tmp_path / "auth.sqlite3"),
        app_env="test",
    )
    auth = AuthManager(settings)

    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI()

    @app.post("/login")
    async def login(request: Request):
        _, error, status = auth.login(request, "tester", "wrong")
        return JSONResponse({"detail": error}, status_code=status)

    client = TestClient(app)
    response = client.post("/login")
    assert response.status_code == 401
    assert "Invalid username or password" in response.json()["detail"]


def test_auth_manager_locks_after_five_failures(tmp_path: Path):
    settings = Settings(
        app_username="tester",
        app_password="secret",
        auth_session_db=str(tmp_path / "auth.sqlite3"),
        app_env="test",
    )
    auth = AuthManager(settings)

    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI()

    @app.post("/login")
    async def login(request: Request):
        _, error, status = auth.login(request, "tester", "wrong")
        return JSONResponse({"detail": error}, status_code=status)

    client = TestClient(app)
    for _ in range(4):
        assert client.post("/login").status_code == 401
    assert client.post("/login").status_code == 429
