"""
backend/migrate_user_status.py

Migration script to add 'status' and 'created_at' columns to the 'users' table.
Ensures non-destructive schema evolution with default 'ACTIVE' status.
"""
import sys
from pathlib import Path
from sqlalchemy import text

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database.session import engine


def migrate():
    print("Running migration: adding 'status' and 'created_at' to 'users' table...")
    with engine.begin() as conn:
        # 1. Add status column if not exists
        conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR NOT NULL DEFAULT 'ACTIVE';"
            )
        )
        print("  - 'status' column verified/added.")

        # 2. Add created_at column if not exists
        conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();"
            )
        )
        print("  - 'created_at' column verified/added.")

        # 3. Ensure any existing rows have status='ACTIVE'
        conn.execute(
            text(
                "UPDATE users SET status = 'ACTIVE' WHERE status IS NULL;"
            )
        )
        print("  - verified all users have non-null status.")

    print("Migration completed successfully!")


if __name__ == "__main__":
    migrate()
