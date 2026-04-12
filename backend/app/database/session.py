from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Use the synchronous DATABASE_URL from .env
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not SQLALCHEMY_DATABASE_URL:
    # Safe local default so the backend boots out-of-the-box.
    # Can be overridden by setting DATABASE_URL in `.env`.
    SQLALCHEMY_DATABASE_URL = "sqlite:///./finops.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def _sqlite_add_missing_columns():
    """Best-effort ALTER for existing SQLite DBs (create_all does not add new columns)."""
    if not SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        return
    alters = [
        "ALTER TABLE scheduler_action_logs ADD COLUMN estimated_savings_usd REAL",
        "ALTER TABLE ec2_schedules ADD COLUMN estimated_hourly_usd REAL",
    ]
    with engine.connect() as conn:
        for stmt in alters:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from app.models.aws_account import AwsAccount
    from app.models.resource import Resource
    from app.models.ec2_schedule_models import Ec2Schedule, SchedulerActionLog, AsgScalingRule
    from app.api.auth_endpoints import UserDB  # ensure auth_users table is created
    # Ensure system configuration table exists (used for feature flags like auto mode)
    from app.models.models import SystemConfiguration
    # Import migration advisor models to ensure their tables are created
    from app.services.migration_advisor.migration_advisor.models import (
        MigrationProject, OrganizationProfile, WorkloadProfile,
        PerformanceRequirements, ComplianceRequirements, BudgetConstraints,
        TechnicalRequirements, ProviderEvaluation, RecommendationReport,
        MigrationPlan, MigrationPhase, OrganizationalStructure,
        CategorizedResource, BaselineMetrics, MigrationReport,
    )
    Base.metadata.create_all(bind=engine)
    _sqlite_add_missing_columns()

