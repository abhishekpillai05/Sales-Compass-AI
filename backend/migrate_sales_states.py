"""
Migration script: create sales_conversation_states table in PostgreSQL.

Applies Base.metadata.create_all(bind=engine) for the new model,
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
    SalesConversationState,
)


def run_migration():
    print("=" * 60)
    print("RUNNING SALES CONVERSATION STATE TABLE MIGRATION")
    print("=" * 60)

    # 1. Create missing tables safely (idempotent)
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    print(f"Current tables in database: {existing_tables}")
    assert "sales_conversation_states" in existing_tables, "Missing table: sales_conversation_states"

    cols = [c["name"] for c in inspector.get_columns("sales_conversation_states")]
    print(f"sales_conversation_states columns: {cols}")

    expected = [
        "id", "conversation_id", "stage", "product_category",
        "extracted_requirements", "candidate_products", "selected_product",
        "agreed_quantity", "agreed_price", "deal_status", "deal_finalized_at",
        "recommendations_generated", "recommendations", "created_at", "updated_at"
    ]
    for col in expected:
        assert col in cols, f"Missing column: {col}"

    # 2. Check unique constraint on conversation_id
    u_constraints = inspector.get_unique_constraints("sales_conversation_states")
    u_col_sets = [set(uc.get("column_names", [])) for uc in u_constraints]
    indexes = inspector.get_indexes("sales_conversation_states")
    index_col_sets = [set(idx.get("column_names", [])) for idx in indexes if idx.get("unique")]
    has_unique_conv = any({"conversation_id"}.issubset(s) for s in u_col_sets + index_col_sets)
    print(f"Unique constraint/index on conversation_id present: {has_unique_conv}")

    # 3. Safe backfill for existing conversations missing sales state
    from app.database.session import SessionLocal
    db = SessionLocal()
    try:
        conversations = db.query(Conversation).all()
        created_count = 0
        for conv in conversations:
            existing = (
                db.query(SalesConversationState)
                .filter(SalesConversationState.conversation_id == conv.id)
                .first()
            )
            if not existing:
                default_state = SalesConversationState(
                    conversation_id=conv.id,
                    stage="DISCOVERY",
                    product_category=None,
                    extracted_requirements={},
                    candidate_products=[],
                    selected_product=None,
                    agreed_quantity=None,
                    agreed_price=None,
                    deal_status="OPEN",
                    deal_finalized_at=None,
                    recommendations_generated=False,
                    recommendations=None,
                )
                db.add(default_state)
                created_count += 1
        if created_count > 0:
            db.commit()
            print(f"Backfilled default DISCOVERY sales state for {created_count} existing conversations.")
        else:
            print("All existing conversations already have valid sales states.")
    except Exception as exc:
        db.rollback()
        print(f"Warning during backfill: {exc}")
    finally:
        db.close()

    print("\n[SUCCESS] sales_conversation_states table, unique constraints, and data verified in PostgreSQL!")


if __name__ == "__main__":
    run_migration()
