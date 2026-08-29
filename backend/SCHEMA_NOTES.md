# SalesCompass AI — Database Schema Notes

## Migration Framework

This project does **not** currently use Alembic or any other migration framework.
Schema management is handled by SQLAlchemy `create_all()` at startup.

> **Note**: Formal migration management should be introduced as a dedicated task
> before production deployment. Consider `alembic init` with autogenerate.

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

---

## One-Time Manual Migrations Applied to Neon (2026-08-29)

These were applied once to the Neon PostgreSQL database to align the live
schema with the SQLAlchemy model after Phase 6 renamed `password` → `password_hash`.

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

---

## Running `create_all()` on a Fresh Database

For a brand-new deployment, `create_all()` in `backend/app/database/init_db.py`
will create all tables correctly from the current models — **no manual SQL needed**.

The manual migrations above are only needed when upgrading an **existing** database
that was originally created with the pre-Phase-6 schema (which had `password` instead
of `password_hash`).

---

## Consistency Check (Verified 2026-08-29)

- `User.password_hash` — only ORM column, used by `auth/services.py` ✅
- `User.password` — **not** in ORM model; exists only as a nullable legacy DB column ✅
- No `user.password` access anywhere in `backend/app/**` ✅
- `UserSession` — present in model and Neon DB ✅
- `init_db.py` imports `UserSession` and includes it in `create_all()` ✅
