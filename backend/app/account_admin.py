"""Local operator bootstrap for a preserved, unowned character."""

import argparse
import asyncio
from getpass import getpass

from app.services.auth import register_account
from app.db import engine


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an account for an existing unowned character. Run only after verifying ownership."
    )
    parser.add_argument("username")
    args = parser.parse_args()
    password = getpass("New password (8–128 characters, including a number (0-9) and a special character): ")
    if password != getpass("Confirm password: "):
        raise SystemExit("Passwords do not match.")

    async def bootstrap() -> None:
        try:
            await register_account(args.username, password, legacy=True)
        finally:
            await engine.dispose()

    try:
        asyncio.run(bootstrap())
    except ValueError as error:
        raise SystemExit(str(error)) from None
    print("Account created. Existing character state preserved.")


if __name__ == "__main__":
    main()
