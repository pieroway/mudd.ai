"""Local operator account bootstrap and administrator role management."""

import argparse
import asyncio
from getpass import getpass

from app.services.auth import register_account
from app.services.roles import bootstrap_god, change_role
from app.db import engine, get_session_factory


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an account for an existing unowned character. Run only after verifying ownership."
    )
    parser.add_argument("username")
    roles = parser.add_mutually_exclusive_group()
    for role in ("admin", "moderator", "creator"):
        roles.add_argument(f"--{role}", choices=["on", "off"], help=f"Set an existing account's {role} role.")
    roles.add_argument("--bootstrap-god", action="store_true", help="Bind God to the existing Alan account.")
    args = parser.parse_args()
    role = next((name for name in ("admin", "moderator", "creator") if getattr(args, name)), "")
    if args.bootstrap_god and args.username.strip().casefold() != "alan":
        parser.error("--bootstrap-god requires the existing Alan account")
    password = ""
    if not role and not args.bootstrap_god:
        password = getpass("New password (8–128 characters, including a number (0-9) and a special character): ")
        if password != getpass("Confirm password: "):
            raise SystemExit("Passwords do not match.")

    async def bootstrap() -> None:
        try:
            if args.bootstrap_god:
                await bootstrap_god(get_session_factory())
            elif role:
                await change_role(get_session_factory(), None, args.username, role, getattr(args, role) == "on")
            else:
                await register_account(args.username, password, legacy=True)
        finally:
            await engine.dispose()

    try:
        asyncio.run(bootstrap())
    except ValueError as error:
        raise SystemExit(str(error)) from None
    if args.bootstrap_god:
        print("God is bound to the Alan account.")
    elif role:
        print(f"{role.capitalize()} access is {getattr(args, role)}.")
    else:
        print("Account created. Existing character state preserved.")


if __name__ == "__main__":
    main()
