"""
migrate_document_hash.py

One-time migration: add the ``document_hash`` column and its UNIQUE
index to the existing ``documents`` table in PostgreSQL.

Usage (from backend/ directory):
    venv\\Scripts\\python.exe migrate_document_hash.py

Safe and idempotent:
  - If the column already exists the ALTER TABLE is skipped gracefully.
  - If the unique index already exists it is skipped gracefully.
  - No data is deleted or modified.

Background
----------
SQLAlchemy's ``create_all()`` only creates *missing tables*; it cannot
ADD columns to existing tables.  This script applies the schema change
directly via raw SQL, following the same pattern used by earlier
migrations in this project (migrate_users.py, fix_password_col.py,
migrate_conversations.py).
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure the backend/ directory is importable.
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

load_dotenv(backend_dir / ".env")

from sqlalchemy import inspect, text
from app.database.session import engine


def run_migration():
    print("=" * 60)
    print("RUNNING: add document_hash to documents table")
    print("=" * 60)

    inspector = inspect(engine)

    # -- Step 1: Add document_hash column if absent ---------------------------
    existing_columns = [c["name"] for c in inspector.get_columns("documents")]
    print(f"Existing 'documents' columns: {existing_columns}")

    if "document_hash" not in existing_columns:
        print("-> Adding column: document_hash VARCHAR(64) NULL ...")
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE documents "
                "ADD COLUMN document_hash VARCHAR(64) NULL"
            ))
        print("  [OK] Column added.")
    else:
        print("  [SKIP] Column 'document_hash' already exists.")

    # -- Step 2: Create UNIQUE index if absent --------------------------------
    # Re-inspect indexes AFTER the column is added so the inspector is fresh.
    inspector2 = inspect(engine)
    existing_indexes = {
        idx["name"]
        for idx in inspector2.get_indexes("documents")
    }
    print(f"Existing 'documents' indexes: {existing_indexes}")

    index_name = "uq_documents_document_hash"

    if index_name not in existing_indexes:
        print(f"-> Creating unique index: {index_name} ...")
        with engine.begin() as conn:
            conn.execute(text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} "
                f"ON documents (document_hash) "
                f"WHERE document_hash IS NOT NULL"
            ))
        print(f"  [OK] Unique index '{index_name}' created.")
    else:
        print(f"  [SKIP] Index '{index_name}' already exists.")

    # -- Verification ---------------------------------------------------------
    inspector3 = inspect(engine)
    final_columns = [c["name"] for c in inspector3.get_columns("documents")]
    final_indexes = {idx["name"] for idx in inspector3.get_indexes("documents")}

    assert "document_hash" in final_columns, \
        "ERROR: document_hash column missing after migration!"
    assert index_name in final_indexes, \
        f"ERROR: index '{index_name}' missing after migration!"

    print("\n[SUCCESS] documents.document_hash migration verified.")
    print(f"  Columns : {final_columns}")
    print(f"  Indexes : {final_indexes}")


if __name__ == "__main__":
    run_migration()
