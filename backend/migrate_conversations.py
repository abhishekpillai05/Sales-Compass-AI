"""
Migration script: create conversations and conversation_messages tables in PostgreSQL.

Applies Base.metadata.create_all(bind=engine) for the new models,
then verifies table creation and columns. Safe and idempotent.
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

load_dotenv(backend_dir / ".env")

from sqlalchemy import inspect
from app.database.base import Base
from app.database.session import engine
from app.database.models import (
    User,
    Document,
    Product,
    Chunk,
    QueryLog,
    UserSession,
    Conversation,
    ConversationMessage,
)


def run_migration():
    print("=" * 60)
    print("RUNNING CONVERSATION TABLES MIGRATION")
    print("=" * 60)

    # Create missing tables
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    print(f"Current tables in database: {existing_tables}")

    assert "conversations" in existing_tables, "Missing table: conversations"
    assert "conversation_messages" in existing_tables, "Missing table: conversation_messages"

    conv_cols = [c["name"] for c in inspector.get_columns("conversations")]
    msg_cols = [c["name"] for c in inspector.get_columns("conversation_messages")]

    print(f"conversations columns: {conv_cols}")
    print(f"conversation_messages columns: {msg_cols}")

    print("\n[SUCCESS] Conversation tables verified in PostgreSQL!")


if __name__ == "__main__":
    run_migration()
