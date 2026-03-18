"""
Database configuration — Supabase optional, falls back gracefully.
"""

import os
from dotenv import load_dotenv
import structlog

load_dotenv()

logger = structlog.get_logger(__name__)

# Re-export Base from session so all existing imports work
from app.database.session import Base  # noqa: F401

logger = structlog.get_logger(__name__)

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

supabase = None

if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client, Client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized")
    except Exception as e:
        logger.warning("Supabase init failed, running without it", error=str(e))


def get_supabase():
    if supabase is None:
        raise Exception("Supabase is not configured")
    return supabase


def get_db_session():
    return get_supabase()


def get_db():
    return get_supabase()


def AsyncSessionLocal():
    return get_supabase()


async def initialize_database():
    if supabase:
        logger.info("Supabase connection available")
    else:
        logger.info("Running without Supabase — using SQLAlchemy only")


async def database_health_check() -> dict:
    if supabase is None:
        return {"status": "healthy", "backend": "SQLAlchemy (no Supabase)"}
    try:
        supabase.table("health_check").select("*").limit(1).execute()
        return {"status": "healthy", "backend": "Supabase"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
