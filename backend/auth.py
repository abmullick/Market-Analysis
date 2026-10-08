from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Request


SESSION_COOKIE = "market_analysis_session"
SESSION_TTL_SECONDS = 12 * 60 * 60
MAX_FAILED_LOGINS = 5
LOCKOUT_SECONDS = 10 * 60
MAX_LOGIN_ATTEMPTS_WINDOW = 10 * 60


class AuthManager:
    """Small server-side session manager for the single-user Market Analysis app.

    Sessions live in SQLite so authentication continues to work when Gunicorn
    uses more than one worker. Only a SHA-256 hash of the random session token
    is persisted; the bearer token itself exists only in the HttpOnly cookie.
    """

    def __init__(self, settings):
        self.username = settings.app_username.strip()
        self.password = settings.app_password
        self.db_path = Path(settings.auth_session_db)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.secure_cookie = settings.app_env.lower() == "production"
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=5)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _init_db(self):
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS login_attempts (
                    client_key TEXT PRIMARY KEY,
                    first_failed_at REAL NOT NULL,
                    failed_count INTEGER NOT NULL,
                    locked_until REAL
                )
                """
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)"
            )

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _client_key(request: Request) -> str:
        return request.client.host if request.client else "unknown"

    @staticmethod
    def _safe_next(value: str | None) -> str:
        if not value:
            return "/"
        parsed = urlparse(value)
        if parsed.scheme or parsed.netloc or not value.startswith("/") or value.startswith("//"):
            return "/"
        return value

    def same_origin(self, request: Request) -> bool:
        origin = request.headers.get("origin") or request.headers.get("referer")
        if not origin:
            return True
        try:
            parsed = urlparse(origin)
            request_host = request.headers.get("host", "").split(":")[0].lower()
            return parsed.hostname and parsed.hostname.lower() == request_host
        except Exception:
            return False

    def configured(self) -> bool:
        return bool(self.username and self.password)

    def _rate_state(self, client_key: str):
        now = time.time()
        with self._connect() as db:
            row = db.execute(
                "SELECT first_failed_at, failed_count, locked_until FROM login_attempts WHERE client_key=?",
                (client_key,),
            ).fetchone()
            if not row:
                return 0, None
            first, count, locked = row
            if now - first > MAX_LOGIN_ATTEMPTS_WINDOW:
                db.execute("DELETE FROM login_attempts WHERE client_key=?", (client_key,))
                return 0, None
            if locked and locked > now:
                return count, locked
            return count, None

    def login(self, request: Request, username: str, password: str):
        if not self.configured():
            return None, "Application login is not configured on the server.", 503

        if not self.same_origin(request):
            return None, "Invalid login origin.", 403

        client_key = self._client_key(request)
        count, locked_until = self._rate_state(client_key)
        if locked_until:
            return None, "Too many failed attempts. Please try again in 10 minutes.", 429

        valid = hmac.compare_digest(username.strip(), self.username) and hmac.compare_digest(
            password, self.password
        )
        now = time.time()

        with self._connect() as db:
            if not valid:
                if count == 0:
                    first = now
                else:
                    first = db.execute(
                        "SELECT first_failed_at FROM login_attempts WHERE client_key=?",
                        (client_key,),
                    ).fetchone()[0]
                new_count = count + 1
                lock_until = now + LOCKOUT_SECONDS if new_count >= MAX_FAILED_LOGINS else None
                db.execute(
                    """
                    INSERT INTO login_attempts(client_key, first_failed_at, failed_count, locked_until)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(client_key) DO UPDATE SET
                      first_failed_at=excluded.first_failed_at,
                      failed_count=excluded.failed_count,
                      locked_until=excluded.locked_until
                    """,
                    (client_key, first, new_count, lock_until),
                )
                if lock_until:
                    return None, "Too many failed attempts. Please try again in 10 minutes.", 429
                return None, "Invalid username or password.", 401

            db.execute("DELETE FROM login_attempts WHERE client_key=?", (client_key,))
            db.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            token = secrets.token_urlsafe(32)
            db.execute(
                "INSERT INTO sessions(token_hash, username, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (self._hash(token), self.username, now, now + SESSION_TTL_SECONDS),
            )
            return token, None, 200

    def current_user(self, request: Request) -> str | None:
        token = request.cookies.get(SESSION_COOKIE)
        if not token:
            return None
        token_hash = self._hash(token)
        now = time.time()
        with self._connect() as db:
            row = db.execute(
                "SELECT username, expires_at FROM sessions WHERE token_hash=?",
                (token_hash,),
            ).fetchone()
            if not row:
                return None
            username, expires_at = row
            if expires_at <= now:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
                return None
            return username

    def logout(self, request: Request):
        token = request.cookies.get(SESSION_COOKIE)
        if token:
            with self._connect() as db:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (self._hash(token),))

    def cookie_kwargs(self):
        return {
            "key": SESSION_COOKIE,
            "httponly": True,
            "secure": self.secure_cookie,
            "samesite": "lax",
            "max_age": SESSION_TTL_SECONDS,
            "path": "/",
        }

    def clear_cookie_kwargs(self):
        return {
            "key": SESSION_COOKIE,
            "httponly": True,
            "secure": self.secure_cookie,
            "samesite": "lax",
            "path": "/",
        }


def protected_path(path: str) -> bool:
    # The login surface and its authentication API are the only public routes.
    # Everything else — HTML, CSS, JS, images, data files and application APIs —
    # is behind the same session gate.
    return not (
        path == "/login"
        or path.startswith("/api/auth/")
    )
