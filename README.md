# SalesCompass AI — AI-Powered Product Intelligence Platform

SalesCompass AI is a production-grade enterprise sales assistant and product catalog intelligence platform. Built with a **FastAPI** backend and **React 19 + TypeScript + Vite** frontend, it leverages **Retrieval-Augmented Generation (RAG)** powered by **Qdrant Vector Database**, **Groq LLM (Qwen)**, and **PostgreSQL** with multi-turn conversation memory, granular **Role-Based Access Control (RBAC)**, and an **Admin User Management** suite.

---

## Architecture & Features

- **Conversational AI Sales Assistant**: Multi-turn contextual chat powered by Groq LLMs with persistent PostgreSQL conversation history.
- **Semantic Product Search**: Vector-based product search powered by Qdrant vector embeddings and relevance scoring.
- **Document Ingestion (RAG Pipeline)**: Chunking, embedding generation (`sentence-transformers`), and vector index ingestion for product catalogs and manuals.
- **Enterprise RBAC**:
  - **ADMIN**: Complete access to Chat, Search, Document Ingestion, Query Logs, and User Management.
  - **SALESMAN**: Dedicated access to Chat, Search, and personal conversation management; administrative endpoints are strictly blocked.
- **Admin User Management**:
  - Search, filter, and view all registered users with role and activity metrics.
  - Promote salesmen to admins and demote admins to salesmen with confirmation dialogs.
  - Revoke and restore access with immediate session termination on revocation.
  - Backend self-protection safeguards: prevents self-demotion, self-revocation, and demoting/revoking the last active administrator.
- **Modern Glassmorphic Frontend**: Fully responsive, dark-mode design system with keyboard navigation, confirmation modals, and reactive state management.

---

## Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend** | Python 3.10+, FastAPI, Uvicorn, SQLAlchemy, Pydantic v2 |
| **Database** | PostgreSQL, pgvector (optional) |
| **Vector Store** | Qdrant Cloud / Qdrant Local |
| **LLM & Embeddings** | Groq API (`qwen/qwen3.6-27b`), `sentence-transformers` |
| **Frontend** | React 19, TypeScript, Vite, Vanilla CSS Design System, Lucide Icons |
| **Authentication** | Secure HTTP-only cookie session management, bcrypt password hashing |

---

## Prerequisites

Before running the project, ensure you have installed:

- **Python**: version 3.10, 3.11, or 3.12 (`python --version`)
- **Node.js**: version 18+ and `npm` (`node -v`, `npm -v`)
- **PostgreSQL**: running locally or hosted (e.g. Supabase, Neon, AWS RDS)
- **Qdrant**: cluster URL and API key from [cloud.qdrant.io](https://cloud.qdrant.io) (or local Docker container)
- **Groq API Key**: obtained from [console.groq.com](https://console.groq.com)

---

## Quick Start Guide

### 1. Clone the Repository & Checkout Development Branch

```bash
git clone https://github.com/Abhishek-megtech/Sales-Compass-AI.git
cd Sales-Compass-AI
git checkout frontend
```

---

### 2. Backend Setup & Configuration

#### A. Create and Activate Virtual Environment

**Windows (PowerShell / Command Prompt):**
```powershell
python -m venv venv
.\venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

#### B. Install Python Dependencies

```bash
pip install -r backend/requirements.txt
```

#### C. Configure Environment Variables

Create your environment configuration file from the template:

**Windows (PowerShell):**
```powershell
Copy-Item backend\.env.example backend\.env
```

**macOS / Linux:**
```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` with your actual credentials:

```dotenv
# PostgreSQL Database URL
DATABASE_URL=postgresql://sales_user:your_password@localhost:5432/sales_compass_ai

# Qdrant Vector Database
QDRANT_URL=https://your-cluster-id.us-west-1-0.aws.cloud.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key_here
QDRANT_COLLECTION_NAME=product_chunks

# Groq LLM
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=qwen/qwen3.6-27b
GENERATION_TEMPERATURE=0.2

# Chunking & Retrieval
CHUNK_SIZE=500
CHUNK_OVERLAP=50
RETRIEVAL_TOP_K=5
RETRIEVAL_SCORE_THRESHOLD=0.0
RETRIEVAL_MINIMUM_SCORE=0.5

# Logging
LOG_LEVEL=INFO
```

#### D. Database Migration / Schema Update

Run the schema update script to ensure the `users` table has all required columns (`status`, `created_at`):

```bash
python backend/migrate_user_status.py
```

#### E. Start the FastAPI Backend Server

```bash
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

The backend will be available at:
- **API Base**: `http://127.0.0.1:8000`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

---

### 3. Frontend Setup & Configuration

Open a new terminal window or tab.

#### A. Navigate to Frontend Directory

```bash
cd frontend
```

#### B. Install Node Dependencies

```bash
npm install
```

#### C. Configure Frontend Environment

Create a `.env.local` file (or copy `.env.example`):

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env.local
```

**macOS / Linux:**
```bash
cp .env.example .env.local
```

Ensure `frontend/.env.local` points to your backend URL:
```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

#### D. Start the Frontend Development Server

```bash
npm run dev
```

The application will be accessible at:
👉 **`http://localhost:5173`**

---

## User Roles & Capabilities

| Feature / Page | ADMIN | SALESMAN | Unauthenticated |
| :--- | :---: | :---: | :---: |
| **AI Assistant (Chat & Memory)** | Full Access | Full Access | Login Required |
| **Product Search** | Full Access | Full Access | Login Required |
| **Document Ingestion (`/upload`)** | Full Access | Blocked (403) | Login Required |
| **Query Logs (`/admin`)** | Full Access | Blocked (403) | Login Required |
| **User Management (`/admin/users`)** | Full Access | Blocked (403) | Login Required |
| **Role Promotion & Demotion** | Full Access | Blocked (403) | Login Required |
| **Account Revocation & Restoration** | Full Access | Blocked (403) | Login Required |

> **Note on Self-Registration**: Any new user created via the public registration form (`/register`) is strictly registered with the `SALESMAN` role to prevent privilege escalation. Administrators can promote users to `ADMIN` from the **Management** tab.

---

## Testing & Quality Assurance

### Run Backend Unit & Integration Tests

From the project root with the virtual environment activated:

```bash
# Run all test suites
pytest backend/tests -v

# Run targeted RBAC and User Management tests
pytest backend/tests/test_admin_management.py backend/tests/test_rbac.py -v
```

### Run Live Server Verification Script

With the FastAPI backend running on port 8000:

```bash
python backend/verify_admin_management_live.py
```

### Build Frontend for Production

```bash
cd frontend
npm run build
```

The production bundle will be generated in `frontend/dist/`.

---

## Project Structure

```
salescompass-ai/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── admin_users.py     # Admin User Management API
│   │   │   ├── auth.py            # Authentication & session endpoints
│   │   │   ├── conversations.py   # Persistent conversation memory API
│   │   │   ├── query_logs.py      # Admin query logs API
│   │   │   ├── search.py          # Semantic product search API
│   │   │   └── upload.py          # Document ingestion API
│   │   ├── auth/
│   │   │   ├── dependencies.py    # Auth, session, and role guards
│   │   │   ├── roles.py           # UserRole & UserStatus enums
│   │   │   ├── schemas.py         # Pydantic request/response schemas
│   │   │   └── services.py        # User & session service logic
│   │   ├── database/
│   │   │   ├── connection.py      # SQLAlchemy engine & session factory
│   │   │   └── models.py          # User, UserSession, Conversation, Message models
│   │   ├── rag/                   # Chunking, embeddings, retrieval & generation
│   │   └── main.py                # FastAPI app & CORS configuration
│   ├── tests/                     # Pytest automated test suites
│   ├── migrate_user_status.py     # Database evolution script
│   ├── requirements.txt           # Backend Python dependencies
│   └── .env.example               # Environment variables template
├── frontend/
│   ├── src/
│   │   ├── api/                   # Typed API client modules
│   │   ├── components/            # Reusable UI components & modals
│   │   ├── contexts/              # Auth & Conversation context providers
│   │   ├── pages/
│   │   │   ├── AdminPage.tsx      # Query Logs page
│   │   │   ├── ChatPage.tsx       # AI Assistant & Conversation Memory
│   │   │   ├── LoginPage.tsx      # User authentication
│   │   │   ├── ManagementPage.tsx # Admin User Management
│   │   │   ├── RegisterPage.tsx   # Self-registration
│   │   │   ├── SearchPage.tsx     # Semantic Product Search
│   │   │   └── UploadPage.tsx     # Document Upload & Ingestion
│   │   ├── App.tsx                # Route definitions & guards
│   │   └── index.css              # Glassmorphic design system
│   ├── package.json
│   ├── vite.config.ts
│   └── .env.example
├── README.md
└── .gitignore
```

---

