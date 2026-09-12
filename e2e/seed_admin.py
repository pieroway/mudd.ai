"""Create a deterministic admin account only in the isolated browser-test stack."""

import asyncio

from app.config import Settings
from app.db import engine, get_session_factory
from app.services.auth import register_account
from app.services.ai_preferences import set_admin


async def main():
    settings = Settings()
    if settings.app_env != "test" or "@postgres_e2e:5432/muddb_e2e" not in settings.database_url:
        raise RuntimeError("This fixture requires the isolated E2E database.")
    try:
        for username in ("NarrationAdmin", "CreditAdmin", "WorldAdmin", "NeighborhoodAdmin"):
            await register_account(username, "A long test-only passphrase1!")
            await set_admin(get_session_factory(), username, True)
    finally:
        await engine.dispose()


asyncio.run(main())
