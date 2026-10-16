"""OmniShelf persistence API foundation.

Local development: DATABASE_URL=sqlite:///./omnishelf-dev.db uvicorn backend.main:app --reload
Production: set DATABASE_URL to PostgreSQL, COOKIE_SECURE=true, FRONTEND_ORIGIN and PUBLIC_APP_ORIGIN.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Generator

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, case, create_engine, delete, select, text
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
RENDER_ENVIRONMENT = os.getenv("RENDER", "").strip().lower() == "true"
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

class AuthRateLimit(Base):
    """Shared fixed-window counter keyed by action and an HMAC of the client address."""
    __tablename__ = "auth_rate_limits"
    action: Mapped[str] = mapped_column(String(16), primary_key=True)
    client_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_started: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

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

class DeleteAccountBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
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

# Shared database-backed auth throttles: 5 registrations/hour and 10 logins/15 minutes.
# The HMAC key is consistent across instances because DATABASE_URL is shared; deployments may
# set RATE_LIMIT_HASH_KEY explicitly to decouple address-hash rotation from database credentials.
_RATE_LIMITS = {"register": (5, 3600), "login": (10, 900)}
_RATE_LIMIT_HASH_KEY = os.getenv("RATE_LIMIT_HASH_KEY", DATABASE_URL).encode("utf-8")

def _rate_limit_client_host(request: Request) -> str:
    # Render's edge sets the real client address as the first X-Forwarded-For entry.
    # Only trust this provider-specific behavior when Render explicitly marks the runtime.
    # For local/self-hosted deployments, caller-supplied forwarding headers are ignored.
    if RENDER_ENVIRONMENT:
        forwarded = request.headers.get("x-forwarded-for", "")
        candidate = forwarded.split(",", 1)[0].strip()
        if candidate:
            try:
                return str(ipaddress.ip_address(candidate))
            except ValueError:
                pass
    return request.client.host if request.client else "unknown"

def _rate_limit(request: Request, action: str, db: DBSession) -> None:
    limit, window = _RATE_LIMITS[action]
    remote_host = _rate_limit_client_host(request)
    client_key = hmac.new(_RATE_LIMIT_HASH_KEY, remote_host.encode("utf-8"), hashlib.sha256).hexdigest()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=window)

    try:
        # Occasionally prune old keys so a stream of distinct client addresses cannot
        # grow the table forever. Most requests avoid an extra DELETE.
        if secrets.randbelow(100) == 0:
            db.execute(delete(AuthRateLimit).where(AuthRateLimit.window_started < now - timedelta(days=1)))

        dialect = db.get_bind().dialect.name
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as dialect_insert
        elif dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as dialect_insert
        else:
            raise HTTPException(status_code=503, detail="Shared authentication rate limiting is unavailable.")

        inserted = dialect_insert(AuthRateLimit).values(
            action=action,
            client_key=client_key,
            window_started=now,
            attempts=1,
        )
        statement = inserted.on_conflict_do_update(
            index_elements=["action", "client_key"],
            set_={
                "window_started": case(
                    (AuthRateLimit.window_started <= cutoff, now),
                    else_=AuthRateLimit.window_started,
                ),
                # Cap repeated blocked requests at limit+1; Retry-After is based on
                # the original window start and the counter cannot grow without bound.
                "attempts": case(
                    (AuthRateLimit.window_started <= cutoff, 1),
                    (AuthRateLimit.attempts < limit + 1, AuthRateLimit.attempts + 1),
                    else_=limit + 1,
                ),
            },
        ).returning(AuthRateLimit.window_started, AuthRateLimit.attempts)

        window_started, attempts = db.execute(statement).one()
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        # Fail closed rather than bypassing abuse controls when the shared store fails.
        raise HTTPException(status_code=503, detail="Authentication protection is temporarily unavailable.")

    if window_started.tzinfo is None:
        window_started = window_started.replace(tzinfo=timezone.utc)
    remaining = max(1, int((window_started + timedelta(seconds=window) - now).total_seconds()))
    if attempts > limit:
        raise HTTPException(
            status_code=429,
            detail=f"Too many {action} attempts. Try again later.",
            headers={"Retry-After": str(remaining)},
        )

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
    _rate_limit(request, "register", db)
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
    _rate_limit(request, "login", db)
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


@app.get("/api/me/export")
def export_account_data(
    response: Response,
    user: User = Depends(require_user),
    db: DBSession = Depends(get_db),
):
    """Download the authenticated user's account metadata and saved cloud library."""
    snapshot = db.get(StateSnapshot, user.id)
    export_document = {
        "format": "omnishelf-account-export",
        "version": 1,
        "exported_at": _iso(datetime.now(timezone.utc)),
        "account": _public_user(user),
        "cloud_library": {
            "exists": snapshot is not None,
            "revision": snapshot.revision if snapshot else 0,
            "updated_at": _iso(snapshot.updated_at) if snapshot else None,
            "state": snapshot.state_json if snapshot else None,
        },
    }
    response.headers["Content-Disposition"] = 'attachment; filename="omnishelf-account-export.json"'
    response.headers["Cache-Control"] = "no-store"
    return export_document


@app.delete("/api/me/account", status_code=204)
def delete_account(
    payload: DeleteAccountBody,
    request: Request,
    response: Response,
    user: User = Depends(require_user),
    db: DBSession = Depends(get_db),
):
    """Delete the current account, cloud snapshot and every server-side session."""
    _verify_origin(request)
    try:
        valid_password = password_hasher.verify(user.password_hash, payload.password)
    except (VerifyMismatchError, VerificationError, ValueError):
        valid_password = False
    if not valid_password:
        raise HTTPException(status_code=403, detail="Password confirmation failed.")

    # Explicit child deletion also works in SQLite tests where FK enforcement may be off.
    db.query(StateSnapshot).filter(StateSnapshot.user_id == user.id).delete(synchronize_session=False)
    db.query(LoginSession).filter(LoginSession.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()
    response.delete_cookie(key=COOKIE_NAME, path="/", httponly=True, secure=COOKIE_SECURE, samesite="lax")
    response.status_code = 204
    return response


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


# A narrow test-account bootstrap for the dedicated staging deployment only.
# It is absent from the regular preview unless explicitly enabled in that service's env.
STAGING_ACCEPTANCE_SWITCH = os.getenv("OMNISHELF_STAGING_ACCEPTANCE_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
STAGING_ACCEPTANCE_ORIGIN = "https://omnishelf-1-3-8-auth-staging.onrender.com"
STAGING_ACCEPTANCE_AUDIENCE = "omnishelf-auth-staging"
STAGING_ACCEPTANCE_WORKFLOW_REF = (
    "Reisquin/Omnishelf/.github/workflows/omnishelf-1-3-8-live-smoke.yml"
    "@refs/heads/deploy/1.3.8-https-preview"
)
if STAGING_ACCEPTANCE_SWITCH and (
    REGISTRATION_ENABLED
    or not COOKIE_SECURE
    or PUBLIC_APP_ORIGIN != STAGING_ACCEPTANCE_ORIGIN
):
    # Fail closed rather than accidentally enabling this control path on a regular app.
    raise RuntimeError("Staging acceptance hook requires the isolated staging origin, HTTPS cookies, and closed registration.")

STAGING_ACCEPTANCE_ENABLED = STAGING_ACCEPTANCE_SWITCH
_STAGING_GITHUB_JWKS = (
    jwt.PyJWKClient("https://token.actions.githubusercontent.com/.well-known/jwks")
    if STAGING_ACCEPTANCE_ENABLED
    else None
)


def _validated_staging_actions_claims(token: str) -> dict[str, Any]:
    if not STAGING_ACCEPTANCE_ENABLED or _STAGING_GITHUB_JWKS is None:
        raise HTTPException(status_code=404, detail="Not found.")
    try:
        signing_key = _STAGING_GITHUB_JWKS.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=STAGING_ACCEPTANCE_AUDIENCE,
            issuer="https://token.actions.githubusercontent.com",
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except Exception:
        raise HTTPException(status_code=401, detail="A valid staging workflow identity is required.")
    if (
        claims.get("repository") != "Reisquin/Omnishelf"
        or claims.get("ref") != "refs/heads/deploy/1.3.8-https-preview"
        or claims.get("workflow_ref") != STAGING_ACCEPTANCE_WORKFLOW_REF
        or claims.get("event_name") != "push"
    ):
        raise HTTPException(status_code=403, detail="This workflow is not authorized for staging acceptance.")
    run_id = str(claims.get("run_id", ""))
    run_attempt = str(claims.get("run_attempt", ""))
    if not re.fullmatch(r"[0-9]{1,20}", run_id) or not re.fullmatch(r"[0-9]{1,5}", run_attempt):
        raise HTTPException(status_code=403, detail="The staging workflow identity is incomplete.")
    return claims


def _staging_workflow_identity(request: Request) -> dict[str, Any]:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="A valid staging workflow identity is required.")
    return _validated_staging_actions_claims(token.strip())


class StagingAcceptancePrepareBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot: str = Field(pattern="^[ps]$")
    password: str = Field(min_length=32, max_length=256)


def _cleanup_staging_workflow_users(db: DBSession, run_id: str, slot: str | None = None) -> int:
    username_pattern = re.compile(rf"^e2e_{re.escape(run_id)}_[0-9]+_[ps]$")
    email_pattern = re.compile(rf"^e2e-{re.escape(run_id)}-[0-9]+-[ps]@example\.invalid$")
    candidates = db.scalars(
        select(User).where(User.username.like(f"e2e!_{run_id}!_%", escape="!"))
    ).all()
    matched = [
        user for user in candidates
        if username_pattern.fullmatch(user.username)
        and email_pattern.fullmatch(user.email)
        and (slot is None or user.username.endswith(f"_{slot}"))
    ]
    for user in matched:
        db.query(StateSnapshot).filter(StateSnapshot.user_id == user.id).delete(synchronize_session=False)
        db.query(LoginSession).filter(LoginSession.user_id == user.id).delete(synchronize_session=False)
        db.delete(user)
    return len(matched)


if STAGING_ACCEPTANCE_ENABLED:
    @app.post("/__staging/acceptance/prepare", status_code=201, include_in_schema=False)
    def staging_acceptance_prepare(
        payload: StagingAcceptancePrepareBody,
        request: Request,
        response: Response,
        db: DBSession = Depends(get_db),
    ):
        claims = _staging_workflow_identity(request)
        run_id = str(claims["run_id"])
        attempt = str(claims["run_attempt"])
        slot = payload.slot
        # Also remove this slot from an interrupted earlier attempt of the same workflow run.
        _cleanup_staging_workflow_users(db, run_id, slot=slot)
        username = f"e2e_{run_id}_{attempt}_{slot}"
        email = f"e2e-{run_id}-{attempt}-{slot}@example.invalid"
        user = User(username=username, email=email, password_hash=password_hasher.hash(payload.password))
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="The staging test account already exists.")
        response.headers["Cache-Control"] = "no-store"
        return {"username": username, "email": email, "run_id": run_id, "slot": slot}

    @app.post("/__staging/acceptance/cleanup", include_in_schema=False)
    def staging_acceptance_cleanup(
        request: Request,
        response: Response,
        db: DBSession = Depends(get_db),
    ):
        claims = _staging_workflow_identity(request)
        deleted = _cleanup_staging_workflow_users(db, str(claims["run_id"]))
        db.commit()
        response.headers["Cache-Control"] = "no-store"
        return {"deleted_accounts": deleted}


@app.get("/api")
def api_root():
    return {"name": "OmniShelf API", "version": "1.3.8", "health": "/healthz", "account": "/api/auth/me", "cloud_state": "/api/me/state"}


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
