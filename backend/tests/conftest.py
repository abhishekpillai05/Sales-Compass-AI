"""
conftest.py -- pytest session configuration.

Loads backend/.env before any test runs, so all modules
(postgres_service, qdrant_service, retriever, etc.) pick up
the correct DATABASE_URL, QDRANT_URL, etc. regardless of the
directory pytest is launched from.
"""
import os
from pathlib import Path
from dotenv import load_dotenv


def pytest_configure(config):
    """Load backend/.env at pytest startup, before any module is imported."""
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=str(env_file), override=True)
