"""Create an authorised user (the only way to get an account — there is no sign-up).

Run from the backend/ folder:
    ..\\.venv\\Scripts\\python -m scripts.create_user --email jane@example.com --name "Jane Smith" --role engineer

You will be asked for the password (it is not shown while typing).
"""

import argparse
import getpass
import sys

from sqlalchemy import select

from app.auth import hash_password
from app.db import SessionLocal
from app.models import User

MIN_PASSWORD_LENGTH = 8


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Slope Monitor user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="")
    parser.add_argument("--role", choices=["admin", "engineer"], default="engineer")
    args = parser.parse_args()

    email = args.email.strip().lower()
    password = getpass.getpass("Password: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
        return 1
    if getpass.getpass("Repeat password: ") != password:
        print("Passwords do not match.")
        return 1

    with SessionLocal() as db:
        if db.scalars(select(User).where(User.email == email)).first():
            print(f"A user with email {email} already exists.")
            return 1
        db.add(
            User(
                email=email,
                name=args.name or email.split("@")[0],
                role=args.role,
                password_hash=hash_password(password),
            )
        )
        db.commit()
    print(f"Created {args.role} {email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
