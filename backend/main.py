"""
FinOps Platform - Main API Entry Point
"""

import os
import time
import uuid
import structlog
from datetime import datetime
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

import uvicorn

# Load environment variables
load_dotenv()

# Import database health check (Supabase)
from app.database.database import database_health_check, initialize_database
from app.database.session import init_db as init_sql_db

# Import routers
from app.api.auth_endpoints import auth_router
from app.api.resources_router import router as resources_router
from app.api.cloud_endpoints import cloud_router
from app.api.health_endpoints import router as health_router
from app.api.ai_assistant_endpoints import router as ai_assistant_router
from app.api.aws_cost_endpoints import router as aws_cost_router
from app.api.azure_cost_router import router as azure_cost_router
from app.api.aws_cost_alerts_endpoints import router as aws_cost_alerts_router
from app.api.webhook_endpoints import router as webhook_router
from app.api.automation_endpoints import router as automation_router
from app.api.anomaly_detection import router as anomaly_detection_router
from app.api.multi_cloud import router as multi_cloud_router
from app.api.onboarding import router as onboarding_router
from app.api.scheduler_endpoints import router as scheduler_router
from app.api.scaling_rules_endpoints import router as scaling_rules_router
from app.api.aws_simple_endpoints import router as aws_simple_router
from app.api.budgets_endpoints import router as budgets_router
from app.api.compliance_endpoints import router as compliance_router
from app.api.reports_endpoints import router as reports_router
from app.api.automation_stats_endpoints import router as automation_stats_router

# Optional routers (some repos/branches omit these modules)
def _optional_router(import_path: str, attr: str = "router"):
    try:
        module = __import__(import_path, fromlist=[attr])
        return getattr(module, attr)
    except Exception:
        return None

gnn_router = _optional_router("app.api.graph_neural_network_endpoints", "router")
ai_monitoring_router = _optional_router("app.api.ai_system_monitoring_endpoints", "router")
collaboration_router = _optional_router("app.api.collaboration_endpoints", "router")
communication_router = _optional_router("app.api.communication_endpoints", "router")
video_router = _optional_router("app.api.video_endpoints", "router")

# Migration Advisor routers
try:
    from app.services.migration_advisor.migration_advisor.assessment_endpoints import router as migration_assessment_router
    from app.services.migration_advisor.migration_advisor.requirements_endpoints import router as migration_requirements_router
    from app.services.migration_advisor.migration_advisor.recommendation_endpoints import router as migration_recommendation_router
    from app.services.migration_advisor.migration_advisor.migration_planning_endpoints import router as migration_planning_router
    _migration_routers_loaded = True
except Exception as _e:
    _migration_routers_loaded = False
    migration_assessment_router = None
    migration_requirements_router = None
    migration_recommendation_router = None
    migration_planning_router = None

# Structured logging config
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger(__name__)


# Application lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events: Startup and Shutdown
    """
    # Startup
    logger.info("Starting up FinOps Platform API...")
    
    # Initialize SQLAlchemy tables
    try:
        init_sql_db()
        logger.info("SQLAlchemy tables initialized")
    except Exception as e:
        logger.error("Failed to initialize SQLAlchemy tables", error=str(e))

    # Initialize Supabase connection
    await initialize_database()
    
    yield
    
    # Shutdown
    logger.info("Shutting down FinOps Platform API")

    try:
        from app.services.webhook_integration import stop_webhook_system
        await stop_webhook_system()
    except Exception as e:
        logger.warning("Webhook shutdown error", error=str(e))

    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="FinOps Platform API",
    description="Enterprise Cloud Financial Operations Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=os.getenv(
        "ALLOWED_HOSTS",
        "localhost,127.0.0.1,0.0.0.0"
    ).split(","),
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000"
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):

    start_time = time.time()
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))

    request.state.correlation_id = correlation_id

    logger.info(
        "Request started",
        method=request.method,
        path=request.url.path,
        correlation_id=correlation_id,
    )

    response = await call_next(request)

    duration = time.time() - start_time

    logger.info(
        "Request completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration=duration,
        correlation_id=correlation_id,
    )

    response.headers["X-Correlation-ID"] = correlation_id

    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):

    correlation_id = getattr(request.state, "correlation_id", "unknown")

    logger.error(
        "Unhandled exception",
        error=str(exc),
        correlation_id=correlation_id,
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "correlation_id": correlation_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
        },
    )


# HTTP exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):

    correlation_id = getattr(request.state, "correlation_id", "unknown")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
                "status_code": exc.status_code,
                "correlation_id": correlation_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
        },
    )


# Include routers
app.include_router(auth_router)
app.include_router(health_router)
app.include_router(aws_simple_router)
app.include_router(budgets_router)
app.include_router(compliance_router)
app.include_router(reports_router)
app.include_router(automation_stats_router)
app.include_router(aws_cost_router)
app.include_router(azure_cost_router)
app.include_router(aws_cost_alerts_router)
app.include_router(webhook_router, prefix="/api/v1")
app.include_router(anomaly_detection_router)
app.include_router(multi_cloud_router, prefix="/api/v1")
app.include_router(onboarding_router, prefix="/api/v1")
app.include_router(scheduler_router, prefix="/api")
app.include_router(scaling_rules_router, prefix="/api/v1")
app.include_router(resources_router)
app.include_router(ai_assistant_router)

# Optional feature routers (loaded only if present)
for _r in [gnn_router, ai_monitoring_router, collaboration_router, communication_router, video_router]:
    if _r is not None:
        app.include_router(_r)

# Migration Advisor
if _migration_routers_loaded:
    app.include_router(migration_assessment_router)
    app.include_router(migration_requirements_router)
    app.include_router(migration_recommendation_router)
    app.include_router(migration_planning_router)


# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "FinOps Platform API",
        "version": "1.0.0",
        "docs": "/docs",
    }


# Health endpoint
@app.get("/health")
async def health():

    db_health = await database_health_check()

    return {
        "status": "healthy" if db_health["status"] == "healthy" else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": db_health
        }
    }


# Development server
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )