"""Cookie authentication with bounded credential input and origin checks."""

import json
from collections import deque
from dataclasses import asdict
from time import monotonic

from fastapi import APIRouter, HTTPException, Request, Response

from app.config import Settings
from app.services import auth

router = APIRouter(prefix="/auth")
settings = Settings()
COOKIE_NAME = "mud_session"
attempts: dict[str, deque[float]] = {}


def require_origin(request: Request) -> None:
    if request.headers.get("origin") not in settings.allowed_origins:
        raise HTTPException(403, "Untrusted origin.")


def limit_attempts(request: Request) -> None:
    now = monotonic()
    cutoff = now - settings.auth_attempt_window_seconds
    for key in list(attempts):
        if not attempts[key] or attempts[key][-1] <= cutoff:
            del attempts[key]
    host = request.client.host if request.client else "unknown"
    if host not in attempts and len(attempts) >= settings.max_tracked_client_addresses:
        raise HTTPException(429, "Too many authentication attempts.")
    timestamps = attempts.setdefault(host, deque())
    while timestamps and timestamps[0] <= cutoff:
        timestamps.popleft()
    if len(timestamps) >= settings.auth_attempt_limit:
        raise HTTPException(429, "Too many authentication attempts.")
    timestamps.append(now)


async def credentials(request: Request) -> tuple[str, str]:
    require_origin(request)
    limit_attempts(request)
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise HTTPException(415, "Use JSON credentials.")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > 2048:
            raise HTTPException(413, "Request too large.")
        body.extend(chunk)
    try:
        data = json.loads(body)
        if not isinstance(data, dict) or set(data) != {"username", "password"}:
            raise ValueError()
        username, password = data["username"], data["password"]
        if not isinstance(username, str) or not isinstance(password, str):
            raise ValueError()
        if not username.strip() or len(username) > 50 or not 1 <= len(password) <= 128:
            raise ValueError()
        return username, password
    except (ValueError, TypeError, RecursionError):
        # FastAPI's default validation errors can echo credential input.
        raise HTTPException(400, "Invalid credentials format.") from None


async def set_session(request: Request, response: Response, identity: auth.Identity) -> dict:
    token = await auth.create_session(
        identity, settings.auth_session_seconds, request.cookies.get(COOKIE_NAME)
    )
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.auth_session_seconds,
        httponly=True,
        secure=settings.secure_auth_cookie,
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return asdict(identity)


@router.post("/register", status_code=201)
async def register(request: Request, response: Response):
    username, password = await credentials(request)
    try:
        identity = await auth.register_account(username, password)
    except auth.NameUnavailableError:
        raise HTTPException(409, "Username is unavailable.") from None
    except ValueError:
        raise HTTPException(
            400,
            "Use a valid username and a password of 8 to 128 characters, "
            "including a number (0-9) and a special character.",
        ) from None
    return await set_session(request, response, identity)


@router.post("/login")
async def login(request: Request, response: Response):
    username, password = await credentials(request)
    try:
        identity = await auth.authenticate(username, password)
    except ValueError:
        raise HTTPException(401, "Invalid username or password.") from None
    return await set_session(request, response, identity)


@router.get("/me")
async def me(request: Request, response: Response):
    identity = await auth.resolve_session(request.cookies.get(COOKIE_NAME))
    if identity is None:
        raise HTTPException(401, "Please sign in.", headers={"Cache-Control": "no-store"})
    response.headers["Cache-Control"] = "no-store"
    return asdict(identity)


@router.post("/logout", status_code=204)
async def logout(request: Request):
    require_origin(request)
    await auth.revoke_session(request.cookies.get(COOKIE_NAME))
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.delete_cookie(
        COOKIE_NAME, path="/", secure=settings.secure_auth_cookie, httponly=True, samesite="strict"
    )
    return response
