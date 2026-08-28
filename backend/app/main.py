from fastapi import FastAPI

# Phase 1-5 routers
from app.api.upload import router as upload_router
from app.api.search import router as search_router

# Phase 6/7 routers
from app.api.auth import router as auth_router
from app.api.ask import router as ask_router
from app.api.query_logs import router as query_logs_router


app = FastAPI(
    title="SalesCompass AI",
    version="1.0.0",
    description=(
        "Sales Compass AI — Phases 1-7: "
        "Ingestion, Knowledge Indexing, Retrieval, "
        "Response Generation, Authentication, and Query Logging."
    ),
)


# Phase 1-5
app.include_router(upload_router)
app.include_router(search_router)

# Phase 6/7
app.include_router(auth_router)
app.include_router(ask_router)
app.include_router(query_logs_router)


@app.get("/")
def root():
    return {
        "message": "SalesCompass AI API is running",
        "phases": "1-7",
        "docs": "/docs",
    }