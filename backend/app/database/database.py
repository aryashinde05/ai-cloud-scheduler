"""
Database configuration for FinOps Platform using Supabase
"""

import os
from typing import Generator
from dotenv import load_dotenv
from supabase import create_client, Client
import structlog

load_dotenv()

logger = structlog.get_logger(__name__)

# Supabase configuration
SUPABASE_URL: str = os.getenv("SUPABASE_URL")
SUPABASE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY")  # Use service key for server-side operations

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")

# Create Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class Base:
    """Mock Base class for SQLAlchemy compatibility"""
    pass

def get_supabase() -> Client:
    """
    Dependency for FastAPI to access Supabase client
    """
    return supabase


def get_db_session() -> Client:
    """
    Compatibility function for older code using get_db_session
    """
    return supabase


def get_db() -> Client:
    """
    Compatibility function for older code using get_db
    """
    return supabase

def AsyncSessionLocal():
    """Compatibility shim for AsyncSessionLocal"""
    return supabase

async def database_health_check() -> dict:
    """
    Check Supabase connection health
    """
    try:
        # Simple query to verify connection
        response = supabase.table("health_check").select("*").limit(1).execute()

        return {
            "status": "healthy",
            "database": "supabase",
            "message": "Supabase connection successful"
        }

    except Exception as e:
        logger.error("Supabase health check failed", error=str(e))

        return {
            "status": "unhealthy",
            "database": "supabase",
            "error": str(e)
        }

async def initialize_database():
    """
    Create required tables if they do not exist.
    """
    try:
        supabase.rpc("create_tables_if_not_exist").execute()
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))