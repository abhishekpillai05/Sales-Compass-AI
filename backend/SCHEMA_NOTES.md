# SalesCompass AI — Database Schema Notes

## Schema Management Approach

This project does **not** currently use Alembic or any other database migration framework.

`SQLAlchemy`'s `Base.metadata.create_all()` (called in `init_db.py`) creates **missing tables**
on a fresh database, but it **does not** modify existing tables, add columns, change constraints,
or remove columns. It is not a substitute for database migrations.

- **Fresh deployment** → `create_all()` creates all tables from the current ORM models correctly.
- **Existing database with schema changes** → requires explicit `ALTER TABLE` statements or a
  migration tool such as Alembic.

The current Neon database was manually migrated to be compatible with the Phase 6 ORM model
(see "One-Time Manual Migrations" below). No migration framework is configured.

> **Recommendation**: Introduce Alembic as a dedicated future task before production deployment.

---

## Current SQLAlchemy Models (`backend/app/database/models.py`)

| Table | Model Class | Key Notes |
|-------|-------------|-----------|
| `users` | `User` | Uses `password_hash` column (bcrypt). Legacy `password` column is nullable (unused). |
| `documents` | `Document` | FK → users.id |
| `products` | `Product` | SKU, name, category, manufacturer |
| `chunks` | `Chunk` | FK → documents.id, products.id |
| `query_logs` | `QueryLog` | FK → users.id, auto-timestamp |
| `user_sessions` | `UserSession` | session_token (indexed, unique), expires_at, is_active |
| `document_chunks` | *(via knowledge_indexing)* | chunk_id, metadata, qdrant_point_id |
| `conversations` | `Conversation` | FK → users.id (cascade), title, created_at, updated_at |
| `conversation_messages` | `ConversationMessage` | FK → conversations.id (cascade), role, content, sources (JSON), created_at |

---

## One-Time Manual Migrations Applied to Neon (2026-08-29)

These were applied once to the Neon PostgreSQL database to align the live
schema with the SQLAlchemy model after Phase 6 renamed `password` → `password_hash`.
`create_all()` alone could not perform these changes because the `users` table already existed.

### Migration 1 — Add `password_hash` column

```sql
-- Adds the new column and copies existing bcrypt data from 'password'
ALTER TABLE users ADD COLUMN password_hash VARCHAR(255);
UPDATE users SET password_hash = password WHERE password_hash IS NULL;
```

**Script**: `backend/migrate_users.py` (run once, idempotent check included)

### Migration 2 — Make legacy `password` column nullable

```sql
-- Required so new INSERT statements (which only write password_hash) do not
-- violate the original NOT NULL constraint on the legacy column.
ALTER TABLE users ALTER COLUMN password DROP NOT NULL;
```

**Script**: `backend/fix_password_col.py` (run once)

### Migration 3 — Create `conversations` and `conversation_messages` tables (2026-09-23)

```sql
-- Creates conversations and conversation_messages tables with CASCADE deletion and indexes
-- Handled idempotently via Base.metadata.create_all() in migrate_conversations.py
```

**Script**: `backend/migrate_conversations.py` (run once, verified)

---

## Fresh Database Deployment

For a **brand-new** deployment against an empty database, `create_all()` in
`backend/app/database/init_db.py` will create all tables correctly from the
current ORM models. The manual migrations above are **not needed** in that case —
they were only required to update the pre-existing Neon database that predated
the Phase 6 `password` → `password_hash` rename.

---

## Consistency Check (Verified 2026-08-29)

- `User.password_hash` — only ORM column, used by `auth/services.py` ✅
- `User.password` — **not** in ORM model; exists only as a nullable legacy DB column ✅
- No `user.password` access anywhere in `backend/app/**` ✅
- `UserSession` — present in model and Neon DB ✅
- `init_db.py` imports `UserSession` and includes it in `create_all()` ✅
