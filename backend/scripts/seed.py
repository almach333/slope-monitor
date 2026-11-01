"""Create the demo admin account (and optionally wipe all data first).

Run from the backend/ folder, after `alembic upgrade head`:
    ..\\.venv\\Scripts\\python -m scripts.seed            # create the demo admin if missing
    ..\\.venv\\Scripts\\python -m scripts.seed --reset    # delete ALL nodes, readings and alerts first

The demo nodes themselves are registered by the simulator
(simulator/simulate.py setup), through the same API the New Device page
uses, so the simulator receives their API keys.
"""

import argparse

from sqlalchemy import delete, select

from app.auth import hash_password
from app.db import SessionLocal
from app.models import Alert, AlertRule, AlertRuleChange, Node, Reading, User

DEMO_EMAIL = "admin@example.com"
DEMO_PASSWORD = "slope-demo-2026"
DEMO_NAME = "Demo Admin"


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Slope Monitor database")
    parser.add_argument("--reset", action="store_true", help="delete all nodes, readings and alerts first")
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.reset:
            for table in (Alert, AlertRuleChange, AlertRule, Reading, Node):
                db.execute(delete(table))
            db.commit()
            print("Deleted all nodes, readings, rules and alerts.")
            print("Also delete simulator/keys.json so the simulator registers the nodes again.")

        if db.scalars(select(User).where(User.email == DEMO_EMAIL)).first() is None:
            db.add(
                User(
                    email=DEMO_EMAIL,
                    name=DEMO_NAME,
                    role="admin",
                    password_hash=hash_password(DEMO_PASSWORD),
                )
            )
            db.commit()
            print("Created demo admin user.")
        else:
            print("Demo admin user already exists.")

    print()
    print("  Demo login (local prototype only):")
    print(f"    email:    {DEMO_EMAIL}")
    print(f"    password: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
