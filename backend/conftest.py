"""
Root conftest.py for the backend test suite.

Ensures backend/ is on sys.path and backend/.env is loaded
before any test module is imported.
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Make sure 'backend/' is importable as the root for app.*
backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Load env before any module-level code runs
env_file = backend_dir / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=str(env_file), override=True)
