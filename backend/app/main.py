from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Phase 9: configure logging before anything else runs
from app.logging.config import configure_logging

configure_logging()

# Phase 9: request logging middleware
from app.middleware.request_logging import RequestLoggingMiddleware

# Phase 1-5 routers
from app.api.upload import router as upload_router
from app.api.search import router as search_router

# Phase 6/7 routers
from app.api.auth import router as auth_router
from app.api.ask import router as ask_router
from app.api.query_logs import router as query_logs_router
from app.api.conversations import router as conversations_router
from app.api.admin_users import router as admin_users_router


app = FastAPI(
    title="SalesCompass AI",
    version="1.0.0",
    description=(
        "Sales Compass AI — Phases 1-9: "
        "Ingestion, Knowledge Indexing, Retrieval, "
        "Response Generation, Authentication, Query Logging, "
        "and Structured Request Logging."
    ),
)

# CORS — allow Vite dev server to make credentialed requests.
# Wildcard origins are intentionally NOT used because allow_credentials=True
# requires explicit origin(s) per the CORS specification.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phase 9: attach HTTP request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Phase 1-5
app.include_router(upload_router)
app.include_router(search_router)

# Phase 6/7
app.include_router(auth_router)
app.include_router(ask_router)
app.include_router(query_logs_router)
app.include_router(conversations_router)
app.include_router(admin_users_router)


@app.get("/")
def root():
    return {
        "message": "SalesCompass AI API is running",
        "phases": "1-9",
        "docs": "/docs",
    }