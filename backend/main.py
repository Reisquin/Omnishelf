"""OmniShelf persistence API foundation.

Local development: DATABASE_URL=sqlite:///./omnishelf-dev.db uvicorn backend.main:app --reload
Production: set DATABASE_URL to PostgreSQL, COOKIE_SECURE=true, FRONTEND_ORIGIN and PUBLIC_APP_ORIGIN.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Generator

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session as DBSession, mapped_column, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
COOKIE_NAME = "omnishelf_session"
SESSION_TTL_SECONDS = max(600, int(os.getenv("SESSION_TTL_SECONDS", "2592000")))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").strip().lower() in {"1", "true", "yes", "on"}
# Public registration is closed by default. Enable explicitly for local development or a controlled pre-launch test.
REGISTRATION_ENABLED = os.getenv("REGISTRATION_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
MAX_STATE_BYTES = max(1024 * 1024, int(os.getenv("MAX_STATE_BYTES", str(20 * 1024 * 1024))))
MAX_WORKS = 50_000
MAX_RECORDS = 100_000
PUBLIC_APP_ORIGIN = os.getenv("PUBLIC_APP_ORIGIN", "").strip().rstrip("/")
FRONTEND_ORIGINS = {x.strip().rstrip("/") for x in os.getenv("FRONTEND_ORIGIN", "").split(",") if x.strip()}

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'omnishelf-dev.db'}")
# Render and some managed providers may supply the legacy postgres:// form.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine: Engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
password_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class LoginSession(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

class StateSnapshot(Base):
    __tablename__ = "state_snapshots"
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    state_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

# Database schema is created/changed only by the versioned Alembic migrations.
# This prevents each web-worker startup from racing to mutate production schema.

app = FastAPI(title="OmniShelf API", version="1.3.8", docs_url=None, redoc_url=None, openapi_url=None)
if FRONTEND_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(FRONTEND_ORIGINS),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Requested-With"],
        expose_headers=["ETag"],
    )

@app.middleware("http")
async def safety_headers_and_body_limits(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_STATE_BYTES + 1024 * 1024:
                return JSONResponse({"detail": "Request body is too large."}, status_code=413)
        except ValueError:
            return JSONResponse({"detail": "Invalid content length."}, status_code=400)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.url.path.startswith("/api/auth") or request.url.path.startswith("/api/me"):
        response.headers["Cache-Control"] = "no-store"
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

class RegisterBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=32)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=256)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9_][a-z0-9_-]{2,31}", value):
            raise ValueError("Username must be 3–32 characters using letters, numbers, underscores or hyphens.")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address.")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 12:
            raise ValueError("Password must contain at least 12 characters.")
        if value.strip() != value:
            raise ValueError("Password must not begin or end with whitespace.")
        return value

class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identifier: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

class CloudStateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0)
    state: dict[str, Any]

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value.get("profile"), dict) or not isinstance(value.get("works"), list):
            raise ValueError("State must contain a profile object and works array.")
        if len(value["works"]) > MAX_WORKS:
            raise ValueError(f"Library is limited to {MAX_WORKS:,} works per account.")
        for i, work in enumerate(value["works"]):
            if not isinstance(work, dict) or not isinstance(work.get("title"), str) or not work["title"].strip():
                raise ValueError(f"Work {i + 1} must have a non-empty title.")
            if len(work["title"]) > 500:
                raise ValueError(f"Work {i + 1} title is too long.")
        for section in ("reviews", "activity", "customLists"):
            rows = value.get(section, [])
            if rows is not None and (not isinstance(rows, list) or len(rows) > MAX_RECORDS):
                raise ValueError(f"{section} must be an array with no more than {MAX_RECORDS:,} records.")
        try:
            encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError):
            raise ValueError("State contains values that cannot be saved as JSON.")
        if len(encoded) > MAX_STATE_BYTES:
            raise ValueError(f"State is larger than the {MAX_STATE_BYTES // (1024 * 1024)} MB cloud-save limit.")
        return value

# Basic process-local throttling to slow automated auth abuse on a single instance.
# Use a shared rate-limit store (e.g. Redis) before scaling to multiple instances.
_rate_buckets: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_RATE_LIMITS = {"register": (5, 3600), "login": (10, 900)}

def _rate_limit(request: Request, action: str) -> None:
    limit, window = _RATE_LIMITS[action]
    key = (action, request.client.host if request.client else "unknown")
    queue = _rate_buckets[key]
    now = time.monotonic()
    while queue and now - queue[0] > window:
        queue.popleft()
    if len(queue) >= limit:
        retry = max(1, int(window - (now - queue[0])))
        raise HTTPException(status_code=429, detail=f"Too many {action} attempts. Try again later.", headers={"Retry-After": str(retry)})
    queue.append(now)

def _verify_origin(request: Request) -> None:
    origin = request.headers.get("origin", "").rstrip("/")
    expected = PUBLIC_APP_ORIGIN or f"{request.url.scheme}://{request.url.netloc}"
    allowed = set(FRONTEND_ORIGINS) | {expected}
    if not origin or origin not in allowed:
        raise HTTPException(status_code=403, detail="Request origin was not allowed. Reload OmniShelf and try again.")

def get_db() -> Generator[DBSession, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def _public_user(user: User) -> dict[str, Any]:
    return {"id": user.id, "username": user.username, "email": user.email, "created_at": _iso(user.created_at)}

def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def _issue_session(response: Response, db: DBSession, user: User) -> None:
    raw_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db.query(LoginSession).filter(LoginSession.expires_at < now).delete(synchronize_session=False)
    db.add(LoginSession(user_id=user.id, token_hash=_token_hash(raw_token), expires_at=now + timedelta(seconds=SESSION_TTL_SECONDS)))
    db.commit()
    response.set_cookie(
        key=COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )

def get_current_user(request: Request, db: DBSession = Depends(get_db)) -> User | None:
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        return None
    session = db.scalar(select(LoginSession).where(LoginSession.token_hash == _token_hash(raw)))
    if not session:
        return None
    expiry = session.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        return None
    return db.get(User, session.user_id)

def require_user(user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to access your cloud library.")
    return user

@app.get("/healthz")
def healthz(db: DBSession = Depends(get_db)):
    try:
        db.execute(select(User.id).limit(1))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database unavailable.")
    return {"status": "ok", "database": "ok", "version": "1.3.8"}

@app.post("/api/auth/register", status_code=201)
def register(payload: RegisterBody, request: Request, response: Response, db: DBSession = Depends(get_db)):
    if not REGISTRATION_ENABLED:
        raise HTTPException(status_code=403, detail="Account registration is temporarily disabled. Sign-in remains available for existing accounts.")
    _verify_origin(request)
    _rate_limit(request, "register")
    existing = db.scalar(select(User).where((User.username == payload.username) | (User.email == payload.email)))
    if existing:
        raise HTTPException(status_code=409, detail="That username or email is already registered.")
    user = User(username=payload.username, email=payload.email, password_hash=password_hasher.hash(payload.password))
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That username or email is already registered.")
    _issue_session(response, db, user)
    return {"user": _public_user(user)}

@app.post("/api/auth/login")
def login(payload: LoginBody, request: Request, response: Response, db: DBSession = Depends(get_db)):
    _verify_origin(request)
    _rate_limit(request, "login")
    identifier = payload.identifier.strip().lower()
    user = db.scalar(select(User).where((User.username == identifier) | (User.email == identifier)))
    valid = False
    if user:
        try:
            valid = password_hasher.verify(user.password_hash, payload.password)
        except (VerifyMismatchError, VerificationError, ValueError):
            valid = False
    if not user or not valid:
        raise HTTPException(status_code=401, detail="The username/email or password was incorrect.")
    _issue_session(response, db, user)
    return {"user": _public_user(user)}

@app.post("/api/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: DBSession = Depends(get_db)):
    _verify_origin(request)
    raw = request.cookies.get(COOKIE_NAME)
    if raw:
        record = db.scalar(select(LoginSession).where(LoginSession.token_hash == _token_hash(raw)))
        if record:
            db.delete(record)
            db.commit()
    response.delete_cookie(key=COOKIE_NAME, path="/", httponly=True, secure=COOKIE_SECURE, samesite="lax")
    response.status_code = 204
    return response

@app.get("/api/auth/me")
def whoami(user: User | None = Depends(get_current_user)):
    return {"user": _public_user(user) if user else None}

@app.get("/api/me/state/meta")
def state_meta(user: User = Depends(require_user), db: DBSession = Depends(get_db)):
    snapshot = db.get(StateSnapshot, user.id)
    return {
        "exists": snapshot is not None,
        "revision": snapshot.revision if snapshot else 0,
        "updated_at": _iso(snapshot.updated_at) if snapshot else None,
        "work_count": len(snapshot.state_json.get("works", [])) if snapshot else 0,
        "review_count": len(snapshot.state_json.get("reviews", [])) if snapshot else 0,
    }

@app.get("/api/me/state")
def get_state(response: Response, user: User = Depends(require_user), db: DBSession = Depends(get_db)):
    snapshot = db.get(StateSnapshot, user.id)
    if not snapshot:
        return {"exists": False, "revision": 0, "updated_at": None, "state": None}
    if response is not None:
        response.headers["ETag"] = f'"{snapshot.revision}"'
    return {"exists": True, "revision": snapshot.revision, "updated_at": _iso(snapshot.updated_at), "state": snapshot.state_json}

@app.put("/api/me/state")
def put_state(payload: CloudStateBody, request: Request, user: User = Depends(require_user), db: DBSession = Depends(get_db)):
    _verify_origin(request)
    try:
        # Lock the user's stable row first. Locking only an existing snapshot cannot
        # serialize two first-time uploads when no snapshot row exists yet.
        # PostgreSQL holds this row lock until commit, so the next request observes
        # the committed revision and returns 409 if it submitted a stale revision.
        db.scalar(select(User.id).where(User.id == user.id).with_for_update())
        snapshot = db.scalar(select(StateSnapshot).where(StateSnapshot.user_id == user.id).with_for_update())
        current_revision = snapshot.revision if snapshot else 0
        if payload.expected_revision != current_revision:
            raise HTTPException(status_code=409, detail="Cloud data changed since you loaded it. Restore the latest cloud copy or review the conflict before uploading.")
        now = datetime.now(timezone.utc)
        if snapshot:
            snapshot.state_json = payload.state
            snapshot.revision = current_revision + 1
            snapshot.updated_at = now
        else:
            snapshot = StateSnapshot(user_id=user.id, state_json=payload.state, revision=1, updated_at=now)
            db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Cloud data could not be saved. Your local library is unchanged.")
    return {"exists": True, "revision": snapshot.revision, "updated_at": _iso(snapshot.updated_at), "work_count": len(payload.state.get("works", [])), "review_count": len(payload.state.get("reviews", []))}

@app.get("/api")
def api_root():
    return {"name": "OmniShelf API", "version": "1.3.8", "health": "/healthz", "account": "/api/auth/me", "cloud_state": "/api/me/state"}


# Temporary, single-use preview QA hook. Set OMNISHELF_TEMP_QA_TOKEN only for a controlled
# acceptance run, then clear it and remove this route immediately afterward.
_OMNISHELF_TEMP_QA_TOKEN = os.getenv("OMNISHELF_TEMP_QA_TOKEN", "").strip()
_OMNISHELF_TEMP_QA_USED = False


@app.get("/__private/qa-check/{token}", include_in_schema=False)
def temporary_preview_qa_check(token: str):
    global _OMNISHELF_TEMP_QA_USED
    if (
        not _OMNISHELF_TEMP_QA_TOKEN
        or _OMNISHELF_TEMP_QA_USED
        or not secrets.compare_digest(token, _OMNISHELF_TEMP_QA_TOKEN)
    ):
        raise HTTPException(status_code=404, detail="Not found.")
    _OMNISHELF_TEMP_QA_USED = True

    from concurrent.futures import ThreadPoolExecutor
    from http.cookies import SimpleCookie
    from threading import Barrier

    report: dict[str, Any] = {"status": "ok", "checks": {}}
    qa_user_ids: list[str] = []
    app_host = os.getenv("RENDER_EXTERNAL_HOSTNAME", "omnishelf-1-3-8-free.onrender.com")
    app_origin = f"https://{app_host}"
    _rate_buckets.clear()

    def request_for(path: str, method: str = "GET", cookie: str | None = None) -> Request:
        headers = [
            (b"host", app_host.encode("ascii")),
            (b"origin", app_origin.encode("ascii")),
            (b"x-forwarded-proto", b"https"),
        ]
        if cookie:
            headers.append((b"cookie", f"{COOKIE_NAME}={cookie}".encode("ascii")))
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": method,
            "scheme": "https",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "headers": headers,
            "server": (app_host, 443),
            "client": ("127.0.0.1", 43210),
        }
        return Request(scope)

    def make_user(db: DBSession, label: str) -> tuple[User, str]:
        username = f"qa_{label}_{secrets.token_hex(3)}"
        password = secrets.token_urlsafe(24)
        user = User(
            username=username,
            email=f"{username}@example.invalid",
            password_hash=password_hasher.hash(password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        qa_user_ids.append(user.id)
        return user, password

    def sign_in(db: DBSession, username: str, password: str) -> tuple[str, str]:
        response = Response()
        result = login(
            LoginBody(identifier=username, password=password),
            request_for("/api/auth/login", "POST"),
            response,
            db,
        )
        if not result.get("user"):
            raise AssertionError("Login handler did not return a user.")
        set_cookie = response.headers.get("set-cookie", "")
        jar = SimpleCookie()
        jar.load(set_cookie)
        if COOKIE_NAME not in jar:
            raise AssertionError("Login did not issue the OmniShelf session cookie.")
        cookie = jar[COOKIE_NAME].value
        flags = set_cookie.lower()
        for required in ("secure", "httponly", "samesite=lax"):
            if required not in flags:
                raise AssertionError(f"Session cookie is missing the {required} attribute.")
        return cookie, set_cookie

    def payload(title: str, revision: int = 0) -> CloudStateBody:
        return CloudStateBody(
            expected_revision=revision,
            state={
                "profile": {"name": "Temporary QA"},
                "works": [{"title": title, "medium": "Novella", "status": "In Progress"}],
                "reviews": [],
                "activity": [],
                "customLists": [],
            },
        )

    def save(db: DBSession, cookie: str, title: str, revision: int = 0) -> int:
        request = request_for("/api/me/state", "PUT", cookie)
        user = get_current_user(request, db)
        if user is None:
            raise AssertionError("Session cookie did not resolve to the QA account.")
        result = put_state(payload(title, revision), request, user, db)
        return int(result["revision"])

    try:
        with SessionLocal() as db:
            owner, owner_password = make_user(db, "owner")
            cookie, set_cookie = sign_in(db, owner.username, owner_password)
            report["checks"]["secure_session_cookie"] = {
                "passed": True,
                "secure": "secure" in set_cookie.lower(),
                "httponly": "httponly" in set_cookie.lower(),
                "samesite_lax": "samesite=lax" in set_cookie.lower(),
            }

            revision = save(db, cookie, "Preview cloud persistence", 0)
            if revision != 1:
                raise AssertionError("First snapshot did not create revision 1.")
            read_request = request_for("/api/me/state", "GET", cookie)
            authenticated_owner = get_current_user(read_request, db)
            restored = get_state(Response(), authenticated_owner, db) if authenticated_owner else {}
            if (
                not restored.get("exists")
                or restored.get("revision") != 1
                or restored.get("state", {}).get("works", [{}])[0].get("title") != "Preview cloud persistence"
            ):
                raise AssertionError("Cloud snapshot write/read round-trip failed.")
            report["checks"]["cloud_save_read"] = {"passed": True, "revision": revision}

            try:
                save(db, cookie, "This stale write must not win", 0)
                raise AssertionError("Stale revision unexpectedly succeeded.")
            except HTTPException as exc:
                if exc.status_code != 409:
                    raise
            latest = get_state(Response(), authenticated_owner, db) if authenticated_owner else {}
            if latest.get("revision") != 1 or latest.get("state", {}).get("works", [{}])[0].get("title") != "Preview cloud persistence":
                raise AssertionError("Stale write changed the saved snapshot.")
            report["checks"]["stale_revision_conflict"] = {"passed": True, "http_status": 409}

            logout_response = logout(request_for("/api/auth/logout", "POST", cookie), Response(), db)
            if logout_response.status_code != 204:
                raise AssertionError("Logout handler did not return 204.")
            if get_current_user(request_for("/api/auth/me", cookie=cookie), db) is not None:
                raise AssertionError("Logout did not revoke the session.")
            new_cookie, _ = sign_in(db, owner.username, owner_password)
            relogged_owner = get_current_user(request_for("/api/me/state", cookie=new_cookie), db)
            after_relogin = get_state(Response(), relogged_owner, db) if relogged_owner else {}
            if not after_relogin.get("exists") or after_relogin.get("revision") != 1:
                raise AssertionError("Snapshot did not persist across sign-out/sign-in.")
            report["checks"]["logout_relogin_persistence"] = {"passed": True, "revision": 1}

            other, other_password = make_user(db, "other")
            other_cookie, _ = sign_in(db, other.username, other_password)
            other_user = get_current_user(request_for("/api/me/state", cookie=other_cookie), db)
            other_state = get_state(Response(), other_user, db) if other_user else {}
            if other_state != {"exists": False, "revision": 0, "updated_at": None, "state": None}:
                raise AssertionError("A second account can see the first account's snapshot.")
            report["checks"]["account_isolation"] = {"passed": True}

            race_user, race_password = make_user(db, "race")
            race_cookie, _ = sign_in(db, race_user.username, race_password)

        start_together = Barrier(2)

        def concurrent_save(title: str) -> int:
            with SessionLocal() as race_db:
                start_together.wait(timeout=10)
                try:
                    return save(race_db, race_cookie, title, 0)
                except HTTPException as exc:
                    return exc.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(concurrent_save, ["Concurrent preview write A", "Concurrent preview write B"]))
        if sorted(results) != [1, 409]:
            # save() returns revision 1 for the successful request and HTTP 409 for the stale concurrent request.
            raise AssertionError(f"Concurrent first saves produced unexpected results: {results!r}")
        report["checks"]["concurrent_first_snapshot"] = {
            "passed": True,
            "outcomes": ["revision 1 committed", "stale request rejected"],
        }

    except Exception as exc:
        report["status"] = "failed"
        report["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    finally:
        try:
            with SessionLocal() as cleanup_db:
                if qa_user_ids:
                    cleanup_db.query(StateSnapshot).filter(StateSnapshot.user_id.in_(qa_user_ids)).delete(synchronize_session=False)
                    cleanup_db.query(LoginSession).filter(LoginSession.user_id.in_(qa_user_ids)).delete(synchronize_session=False)
                    cleanup_db.query(User).filter(User.id.in_(qa_user_ids)).delete(synchronize_session=False)
                    cleanup_db.commit()
                remaining = {
                    "qa_users": int(cleanup_db.query(User).filter(User.id.in_(qa_user_ids)).count()) if qa_user_ids else 0,
                    "qa_sessions": int(cleanup_db.query(LoginSession).filter(LoginSession.user_id.in_(qa_user_ids)).count()) if qa_user_ids else 0,
                    "qa_snapshots": int(cleanup_db.query(StateSnapshot).filter(StateSnapshot.user_id.in_(qa_user_ids)).count()) if qa_user_ids else 0,
                }
                report["cleanup"] = remaining
                if any(remaining.values()):
                    report["status"] = "failed"
                    report["error"] = "Temporary QA records were not fully removed."
        except Exception as cleanup_exc:
            report["status"] = "failed"
            report["cleanup_error"] = f"{type(cleanup_exc).__name__}: {str(cleanup_exc)[:200]}"
        _rate_buckets.clear()
    return JSONResponse(report, status_code=200 if report["status"] == "ok" else 500)

@app.get("/{asset_path:path}", include_in_schema=False)
def frontend_fallback(asset_path: str):
    # This project currently ships as one self-contained HTML frontend. Hash routes
    # are client-side; unknown root-level routes return the app shell.
    if asset_path.startswith("api/") or asset_path == "healthz":
        raise HTTPException(status_code=404, detail="Not found")
    candidate = ROOT / asset_path
    if candidate.is_file() and ROOT in candidate.resolve().parents:
        return FileResponse(candidate)
    return FileResponse(ROOT / "index.html")
