"""Password verification, atomic account creation, and session ownership."""

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.db import get_session_factory
from app.models import AccountRecord, AuthSessionRecord, PlayerRecord
from app.services.game import normalize_username

hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
dummy_hash = hasher.hash(token_urlsafe(32))
hash_slots = asyncio.Semaphore(4)


class AuthenticationError(ValueError):
    pass


class NameUnavailableError(ValueError):
    pass


@dataclass(frozen=True)
class Identity:
    account_id: str
    player_id: str
    username: str


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def validate_password(password: str) -> None:
    if (
        not 8 <= len(password) <= 128
        or not any(character in "0123456789" for character in password)
        or not any(not character.isalnum() and not character.isspace() for character in password)
    ):
        raise ValueError(
            "Use 8 to 128 characters, including a number (0-9) and a special character."
        )


async def hash_password(password: str) -> str:
    validate_password(password)
    async with hash_slots:
        return await asyncio.to_thread(hasher.hash, password)


async def register_account(username: str, password: str, *, legacy: bool = False) -> Identity:
    display, normalized = normalize_username(username)
    if len(normalized) > 50:
        raise ValueError("Username is too long after normalization.")
    password_hash = await hash_password(password)
    try:
        async with get_session_factory()() as session:
            async with session.begin():
                player = (
                    await session.scalars(
                        select(PlayerRecord)
                        .where(PlayerRecord.normalized_username == normalized)
                        .with_for_update()
                    )
                ).one_or_none()
                if legacy:
                    if player is None:
                        raise NameUnavailableError("Existing character not found.")
                elif player is not None:
                    raise NameUnavailableError("Username is unavailable.")
                else:
                    player = PlayerRecord(
                        id=str(uuid4()),
                        username=display,
                        normalized_username=normalized,
                        current_room_id="town_square",
                    )
                    session.add(player)
                    await session.flush()
                account = AccountRecord(
                    id=str(uuid4()),
                    normalized_username=normalized,
                    password_hash=password_hash,
                    player_id=player.id,
                )
                session.add(account)
                await session.flush()
                return Identity(account.id, player.id, player.username)
    except IntegrityError:
        raise NameUnavailableError("Username is unavailable.") from None


async def authenticate(username: str, password: str) -> Identity:
    _, normalized = normalize_username(username)
    async with get_session_factory()() as session:
        account = (
            await session.scalars(
                select(AccountRecord).where(AccountRecord.normalized_username == normalized)
            )
        ).one_or_none()
        async with hash_slots:
            try:
                await asyncio.to_thread(
                    hasher.verify, account.password_hash if account else dummy_hash, password
                )
            except (VerificationError, InvalidHashError):
                raise AuthenticationError("Invalid username or password.") from None
        if account is None:
            raise AuthenticationError("Invalid username or password.")
        player = await session.get(PlayerRecord, account.player_id)
        if player is None:
            raise AuthenticationError("Invalid username or password.")
        return Identity(account.id, player.id, player.username)


async def create_session(identity: Identity, seconds: int, previous_token: str | None) -> str:
    token = token_urlsafe(32)
    now = datetime.now(timezone.utc)
    async with get_session_factory()() as session:
        async with session.begin():
            await session.execute(
                delete(AuthSessionRecord).where(AuthSessionRecord.expires_at <= now)
            )
            if previous_token:
                await session.execute(
                    delete(AuthSessionRecord).where(
                        AuthSessionRecord.token_hash == token_digest(previous_token)
                    )
                )
            session.add(
                AuthSessionRecord(
                    token_hash=token_digest(token),
                    account_id=identity.account_id,
                    expires_at=now + timedelta(seconds=seconds),
                )
            )
    return token


async def resolve_session(token: str | None) -> Identity | None:
    if not token or len(token) != 43:
        return None
    async with get_session_factory()() as session:
        row = (
            await session.execute(
                select(AccountRecord, PlayerRecord)
                .join(AuthSessionRecord, AuthSessionRecord.account_id == AccountRecord.id)
                .join(PlayerRecord, AccountRecord.player_id == PlayerRecord.id)
                .where(
                    AuthSessionRecord.token_hash == token_digest(token),
                    AuthSessionRecord.expires_at > datetime.now(timezone.utc),
                )
            )
        ).one_or_none()
        if row is None:
            return None
        account, player = row
        return Identity(account.id, player.id, player.username)


async def revoke_session(token: str | None) -> None:
    if token:
        async with get_session_factory()() as session:
            async with session.begin():
                await session.execute(
                    delete(AuthSessionRecord).where(
                        AuthSessionRecord.token_hash == token_digest(token)
                    )
                )
