"""Manual demo-data entry point: python -m app.db.seed."""

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.database import SessionLocal
from app.services.seed import SeedPasswordError, seed_demo_data


def main() -> int:
    secret = get_settings().seed_password
    try:
        with SessionLocal() as db:
            result = seed_demo_data(db, secret.get_secret_value() if secret else None)
    except SeedPasswordError as error:
        print(str(error))
        return 1
    except SQLAlchemyError:
        print("Seed failed and was rolled back. Check database access and apply migrations first.")
        return 1
    print(
        f"Demo users created: {result.users_created}; refreshed: {result.users_updated}; "
        f"tickets created: {result.tickets_created}."
    )
    print("Demo account sessions were revoked. Log in again with the configured seed password.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
