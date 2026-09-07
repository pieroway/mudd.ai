"""Local operator account bootstrap and administrator role management."""

import argparse
import asyncio
from getpass import getpass

from app.services.auth import register_account
from app.services.ai_preferences import set_admin
from app.db import engine, get_session_factory


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an account for an existing unowned character. Run only after verifying ownership."
    )
    parser.add_argument("username")
    parser.add_argument("--admin", choices=["on", "off"], help="Set an existing account's admin role.")
    args = parser.parse_args()
    password = ""
    if args.admin is None:
        password = getpass("New password (8–128 characters, including a number (0-9) and a special character): ")
        if password != getpass("Confirm password: "):
            raise SystemExit("Passwords do not match.")

    async def bootstrap() -> None:
        try:
            if args.admin is not None:
                await set_admin(get_session_factory(), args.username, args.admin == "on")
            else:
                await register_account(args.username, password, legacy=True)
        finally:
            await engine.dispose()

    try:
        asyncio.run(bootstrap())
    except ValueError as error:
        raise SystemExit(str(error)) from None
    print(f"Admin access is {args.admin}." if args.admin is not None
          else "Account created. Existing character state preserved.")


if __name__ == "__main__":
    main()
