"""
Database Models for Startup Migration Module
"""

from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.types import JSON as JSONB, Uuid as UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum
import uuid

from app.database.database import Base


class ProjectStatus(str, Enum):
    """Migration project status"""
    ASSESSMENT = "assessment"
    COMPARISON = "comparison"
    PLANNING = "planning"
    SETUP = "setup"
    COMPLETED = "completed"


class DatabaseType(str, Enum):
    """Supported database types"""
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    MONGODB = "mongodb"
    SQL_SERVER = "sql_server"
    ORACLE = "oracle"
    MARIADB = "mariadb"


class CloudProvider(str, Enum):
    """Cloud providers"""
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"


class StartupMigrationProject(Base):
    """Startup migration project"""
    __tablename__ = "startup_migration_projects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(50))
    status = Column(SQLEnum(ProjectStatus), nullable=False, default=ProjectStatus.ASSESSMENT)
    
    # Relationships
    assessment = relationship("StartupDatabaseAssessment", back_populates="project", uselist=False)
    recommendations = relationship("StartupCloudRecommendation", back_populates="project")
    migration_plan = relationship("StartupMigrationPlan", back_populates="project", uselist=False)
    finops_integration = relationship("StartupFinOpsIntegration", back_populates="project", uselist=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<StartupMigrationProject(company='{self.company_name}', status='{self.status}')>"


class StartupDatabaseAssessment(Base):
    """Database assessment information"""
    __tablename__ = "startup_database_assessments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("startup_migration_projects.id"), nullable=False)
    
    # Database details
    database_type = Column(SQLEnum(DatabaseType), nullable=False)
    database_version = Column(String(50))
    database_size_gb = Column(Numeric(10, 2), nullable=False)
    number_of_databases = Column(Integer, default=1)
    
    # Performance metrics
    transaction_volume_tps = Column(Integer, nullable=False)
    peak_connections = Column(Integer)
    read_write_ratio = Column(JSONB)  # {"read": 70, "write": 30}
    
    # Current infrastructure
    current_monthly_cost = Column(Numeric(10, 2))
    current_infrastructure = Column(JSONB)  # Details about current setup
    
    # Requirements
    high_availability_required = Column(Boolean, default=False)
    multi_region_required = Column(Boolean, default=False)
    compliance_requirements = Column(JSONB)  # ["GDPR", "HIPAA", "SOC2"]
    
    # Backup and recovery
    backup_retention_days = Column(Integer, default=7)
    backup_frequency_hours = Column(Integer, default=24)
    rto_hours = Column(Integer)  # Recovery Time Objective
    rpo_hours = Column(Integer)  # Recovery Point Objective
    
    # Growth projections
    growth_rate_gb_per_month = Column(Numeric(10, 2))
    expected_tps_growth_percentage = Column(Numeric(5, 2))
    
    # Additional requirements
    additional_requirements = Column(JSONB)
    
    # Relationship
    project = relationship("StartupMigrationProject", back_populates="assessment")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<DatabaseAssessment(type='{self.database_type}', size={self.database_size_gb}GB)>"


class StartupCloudRecommendation(Base):
    """Cloud provider recommendation with pricing"""
    __tablename__ = "startup_cloud_recommendations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("startup_migration_projects.id"), nullable=False)
    
    # Provider details
    provider = Column(SQLEnum(CloudProvider), nullable=False)
    service_name = Column(String(100), nullable=False)  # RDS, Cloud SQL, Azure Database
    instance_type = Column(String(100), nullable=False)
    region = Column(String(50), default="us-east-1")
    
    # Cost breakdown
    instance_cost = Column(Numeric(10, 2), nullable=False)
    storage_cost = Column(Numeric(10, 2), nullable=False)
    backup_cost = Column(Numeric(10, 2), nullable=False)
    data_transfer_cost = Column(Numeric(10, 2), nullable=False)
    total_monthly_cost = Column(Numeric(10, 2), nullable=False)
    
    # Scores (0-100)
    cost_score = Column(Numeric(5, 2), nullable=False)
    performance_score = Column(Numeric(5, 2), nullable=False)
    feature_score = Column(Numeric(5, 2), nullable=False)
    compliance_score = Column(Numeric(5, 2), nullable=False)
    migration_complexity_score = Column(Numeric(5, 2), nullable=False)
    overall_score = Column(Numeric(5, 2), nullable=False)
    
    # Flags
    is_recommended = Column(Boolean, default=False)
    is_best_value = Column(Boolean, default=False)
    is_best_performance = Column(Boolean, default=False)
    is_easiest_migration = Column(Boolean, default=False)
    
    # Features and capabilities
    features = Column(JSONB)  # List of features
    compliance_certifications = Column(JSONB)  # List of certifications
    
    # Justification
    recommendation_reason = Column(String(500))
    pros = Column(JSONB)  # List of pros
    cons = Column(JSONB)  # List of cons
    
    # Relationship
    project = relationship("StartupMigrationProject", back_populates="recommendations")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<CloudRecommendation(provider='{self.provider}', score={self.overall_score})>"


class StartupMigrationPlan(Base):
    """Migration plan with timeline and checklist"""
    __tablename__ = "startup_migration_plans"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("startup_migration_projects.id"), nullable=False)
    
    # Selected provider
    selected_provider = Column(SQLEnum(CloudProvider), nullable=False)
    selected_service = Column(String(100), nullable=False)
    selected_instance_type = Column(String(100), nullable=False)
    
    # Timeline
    timeline_weeks = Column(Integer, nullable=False)
    estimated_downtime_hours = Column(Numeric(5, 2))
    start_date = Column(DateTime(timezone=True))
    target_completion_date = Column(DateTime(timezone=True))
    
    # Costs
    migration_cost = Column(Numeric(10, 2), nullable=False)
    first_month_cost = Column(Numeric(10, 2), nullable=False)
    ongoing_monthly_cost = Column(Numeric(10, 2), nullable=False)
    annual_savings = Column(Numeric(10, 2))
    
    # Migration phases
    phases = Column(JSONB, nullable=False)  # Detailed phase breakdown
    checklist = Column(JSONB, nullable=False)  # Migration checklist
    
    # Risk assessment
    risks = Column(JSONB)  # List of risks with mitigation
    rollback_plan = Column(JSONB)  # Rollback procedures
    
    # Resources
    required_tools = Column(JSONB)  # Tools needed for migration
    documentation_links = Column(JSONB)  # Helpful documentation
    
    # Relationship
    project = relationship("StartupMigrationProject", back_populates="migration_plan")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<MigrationPlan(provider='{self.selected_provider}', weeks={self.timeline_weeks})>"


class StartupFinOpsIntegration(Base):
    """FinOps platform integration configuration"""
    __tablename__ = "startup_finops_integrations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("startup_migration_projects.id"), nullable=False)
    
    # FinOps organization
    finops_organization_id = Column(UUID(as_uuid=True))
    organization_name = Column(String(255), nullable=False)
    team_size = Column(Integer)
    
    # Budget configuration
    monthly_budget = Column(Numeric(10, 2), nullable=False)
    alert_threshold_percentage = Column(Integer, default=80)
    
    # Notification preferences
    notification_email = Column(String(255), nullable=False)
    notification_preferences = Column(JSONB)  # Email, Slack, etc.
    
    # Features enabled
    cost_tracking_enabled = Column(Boolean, default=True)
    budget_alerts_enabled = Column(Boolean, default=True)
    optimization_recommendations_enabled = Column(Boolean, default=True)
    performance_monitoring_enabled = Column(Boolean, default=True)
    
    # Integration status
    integration_status = Column(String(50), default="pending")  # pending, active, failed
    integration_error = Column(String(500))
    
    # Relationship
    project = relationship("StartupMigrationProject", back_populates="finops_integration")
    
    integrated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<FinOpsIntegration(org='{self.organization_name}', budget=${self.monthly_budget})>"

# Re-export models for compatibility with migration_advisor module
try:
    from app.services.migration_advisor.migration_advisor.models import (
        MigrationProject,
        MigrationStatus,
        OrganizationProfile,
        CompanySize,
        InfrastructureType,
        ExperienceLevel,
        WorkloadProfile,
        PerformanceRequirements,
        ComplianceRequirements,
        BudgetConstraints,
        TechnicalRequirements,
        ProviderEvaluation,
        RecommendationReport,
        MigrationPlan,
        MigrationPhase,
        CategorizedResource,
        OrganizationalStructure
    )
    from app.models.models import (
        User,
        CostData,
        Budget,
        BudgetAlert,
        OptimizationRecommendation,
        AuditLog,
        SystemConfiguration,
        UserRole,
        ProviderType,
        BudgetType,
        RecommendationType,
        RecommendationStatus,
        BaseModel,
        CloudProvider,
    )
except ImportError:
    pass

# Backwards-compatibility shims: some modules historically imported
# anomaly-related and forecasting models from this startup_migration
# package. Re-export them from the canonical `app.models.models`
# so older import sites keep working.
try:
    from app.models.models import (
        AnomalyEvent,
        CostForecast,
        AnomalyConfiguration,
    )
    # expose them at this module level
    __all__ = globals().get("__all__", []) + [
        "AnomalyEvent",
        "CostForecast",
        "AnomalyConfiguration",
    ]
except ImportError:
    # If the canonical models module is unavailable, skip silently.
    pass
