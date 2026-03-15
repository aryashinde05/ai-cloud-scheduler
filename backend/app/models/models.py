"""
SQLAlchemy models for FinOps Platform
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Dict, Any, List, Optional

from sqlalchemy import (
    Column, String, DateTime, Boolean, Text, Date, Numeric, Float,
    ForeignKey, Index, JSON, Enum, Integer, UniqueConstraint, Uuid
)
from sqlalchemy.types import JSON as JSONB, Uuid as UUID
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from app.database.database import Base

# Import automation models
from app.models.automation_models import (
    AutomationPolicy, OptimizationAction, AutomationAuditLog,
    ActionApproval, SafetyCheckResult, AutomationLevel, ActionType,
    ActionStatus, RiskLevel, ApprovalStatus
)

# Import collaboration models
from app.models.collaboration_models import (
    CollaborativeSession, SessionParticipant, SessionStateUpdate,
    SessionChatMessage, SessionAnnotation, SessionInvitation,
    SessionType, ParticipantRole, ParticipantStatus, PermissionLevel
)

class UserRole(PyEnum):
    """User roles for role-based access control"""
    ADMIN = "admin"
    FINANCE_MANAGER = "finance_manager"
    ANALYST = "analyst"
    VIEWER = "viewer"

class ProviderType(PyEnum):
    """Supported cloud provider types"""
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    OTHER = "other"

class BudgetType(PyEnum):
    """Budget types"""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    PROJECT = "project"

class AlertType(PyEnum):
    """Budget alert types"""
    BUDGET_THRESHOLD = "budget_threshold"
    COST_SPIKE = "cost_spike"
    ANOMALY_DETECTED = "anomaly_detected"
    FORECAST_OVERRUN = "forecast_overrun"

class AnomalyType(PyEnum):
    """Types of cost anomalies"""
    POINT = "point"
    CONTEXTUAL = "contextual"
    COLLECTIVE = "collective"

class AnomalyStatus(PyEnum):
    """Status of anomaly events"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"
    THRESHOLD = "threshold"
    FORECAST = "forecast"
    ANOMALY = "anomaly"

class RecommendationType(PyEnum):
    """Optimization recommendation types"""
    RIGHTSIZING = "rightsizing"
    RESERVED_INSTANCE = "reserved_instance"
    UNUSED_RESOURCE = "unused_resource"
    UNDERUTILIZED = "underutilized"

class RecommendationStatus(PyEnum):
    """Recommendation status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"

class RiskLevel(PyEnum):
    """Risk levels for recommendations"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class BaseModel(Base):
    """Base model with common fields"""
    __abstract__ = True
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class User(BaseModel):
    """User model for authentication and authorization"""
    __tablename__ = "users"
    
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.VIEWER)
    is_active = Column(Boolean, nullable=False, default=True)
    last_login = Column(DateTime(timezone=True))
    password_changed_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    cloud_providers = relationship("CloudProvider", back_populates="created_by_user")
    budgets = relationship("Budget", back_populates="created_by_user")
    audit_logs = relationship("AuditLog", back_populates="user")
    acknowledged_alerts = relationship("BudgetAlert", back_populates="acknowledged_by_user")
    
    @validates('email')
    def validate_email(self, key, email):
        """Validate email format"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise ValueError("Invalid email format")
        return email.lower()
    
    def __repr__(self):
        return f"<User(email='{self.email}', role='{self.role.value}')>"

class CloudProvider(BaseModel):
    """Cloud provider configuration and credentials"""
    __tablename__ = "cloud_providers"
    
    name = Column(String(100), nullable=False)
    provider_type = Column(Enum(ProviderType), nullable=False)
    credentials_encrypted = Column(Text, nullable=False)  # JSON encrypted credentials
    is_active = Column(Boolean, nullable=False, default=True)
    last_sync = Column(DateTime(timezone=True))
    sync_frequency_hours = Column(Integer, default=24)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Relationships
    created_by_user = relationship("User", back_populates="cloud_providers")
    cost_data = relationship("CostData", back_populates="provider")
    optimization_recommendations = relationship("OptimizationRecommendation", back_populates="provider")
    
    # Indexes
    __table_args__ = (
        Index('ix_cloud_providers_type_active', 'provider_type', 'is_active'),
    )
    
    def __repr__(self):
        return f"<CloudProvider(name='{self.name}', type='{self.provider_type.value}')>"

class CostData(BaseModel):
    """Cost data from cloud providers"""
    __tablename__ = "cost_data"
    
    provider_id = Column(UUID(as_uuid=True), ForeignKey("cloud_providers.id"), nullable=False, index=True)
    resource_id = Column(String(255), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False, index=True)
    service_name = Column(String(100), nullable=False, index=True)
    cost_amount = Column(Numeric(precision=12, scale=4), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    cost_date = Column(Date, nullable=False, index=True)
    usage_quantity = Column(Numeric(precision=12, scale=4))
    usage_unit = Column(String(50))
    tags = Column(JSONB, default={})
    resource_metadata = Column(JSONB, default={})
    
    # Relationships
    provider = relationship("CloudProvider", back_populates="cost_data")
    
    # Indexes for time-series queries
    __table_args__ = (
        Index('ix_cost_data_provider_date', 'provider_id', 'cost_date'),
        Index('ix_cost_data_resource_date', 'resource_id', 'cost_date'),
        Index('ix_cost_data_service_date', 'service_name', 'cost_date'),
        Index('ix_cost_data_tags_gin', 'tags', postgresql_using='gin'),
    )
    
    def __repr__(self):
        return f"<CostData(resource='{self.resource_id}', cost={self.cost_amount}, date='{self.cost_date}')>"

class Budget(BaseModel):
    """Budget management"""
    __tablename__ = "budgets"
    
    name = Column(String(200), nullable=False)
    amount = Column(Numeric(precision=12, scale=2), nullable=False)
    budget_type = Column(Enum(BudgetType), nullable=False)
    scope_filters = Column(JSONB, nullable=False)  # Filters for cost data
    alert_thresholds = Column(JSONB, nullable=False)  # List of threshold percentages
    notification_emails = Column(JSONB, default=[])  # List of email addresses
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Relationships
    created_by_user = relationship("User", back_populates="budgets")
    alerts = relationship("BudgetAlert", back_populates="budget")
    
    # Indexes
    __table_args__ = (
        Index('ix_budgets_active_dates', 'is_active', 'start_date', 'end_date'),
    )
    
    @validates('amount')
    def validate_amount(self, key, amount):
        """Validate budget amount is positive"""
        if amount <= 0:
            raise ValueError("Budget amount must be positive")
        return amount
    
    def __repr__(self):
        return f"<Budget(name='{self.name}', amount={self.amount}, type='{self.budget_type.value}')>"

class BudgetAlert(BaseModel):
    """Budget alerts and notifications"""
    __tablename__ = "budget_alerts"
    
    budget_id = Column(UUID(as_uuid=True), ForeignKey("budgets.id"), nullable=False, index=True)
    threshold_percentage = Column(Integer, nullable=False)
    current_spend = Column(Numeric(precision=12, scale=2), nullable=False)
    budget_amount = Column(Numeric(precision=12, scale=2), nullable=False)
    alert_type = Column(Enum(AlertType), nullable=False, default=AlertType.BUDGET_THRESHOLD)
    message = Column(Text)
    acknowledged = Column(Boolean, nullable=False, default=False)
    acknowledged_at = Column(DateTime(timezone=True))
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    budget = relationship("Budget", back_populates="alerts")
    acknowledged_by_user = relationship("User", back_populates="acknowledged_alerts")
    
    # Indexes
    __table_args__ = (
        Index('ix_budget_alerts_budget_ack', 'budget_id', 'acknowledged'),
    )
    
    def __repr__(self):
        return f"<BudgetAlert(budget_id='{self.budget_id}', threshold={self.threshold_percentage}%)>"

class OptimizationRecommendation(BaseModel):
    """Stores AI-generated optimization recommendations"""
    __tablename__ = "optimization_recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("cloud_providers.id"), nullable=True)
    resource_id = Column(String(255), index=True, nullable=False) 
    resource_type = Column(String(100), nullable=False) # 'EC2', 'EBS', 'RDS', etc.
    recommendation_type = Column(String(100), nullable=False) # 'Rightsizing', 'Idle', 'Reserved Instance'
    description = Column(String(500), nullable=True)
    current_cost = Column(Float, nullable=True)
    projected_cost = Column(Float, nullable=True)
    potential_savings = Column(Float, nullable=False)
    confidence_score = Column(Float, nullable=True)
    status = Column(String(50), default="pending") # pending, applied, rejected
    generated_at = Column(DateTime, default=datetime.utcnow)
    applied_at = Column(DateTime, nullable=True)
    
    # Relationships
    provider = relationship("CloudProvider", back_populates="optimization_recommendations")
    
    # Optional foreign key for structured relationships
    ec2_instance_id = Column(Integer, ForeignKey("ec2_instances.id"), nullable=True)
    ec2_instance = relationship("EC2Instance", back_populates="recommendations")

class CostHistory(Base):
    """Tracks historical cost data for resources"""
    __tablename__ = "cost_history"

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(String, index=True, nullable=False)
    service_type = Column(String, nullable=False)
    date = Column(DateTime, nullable=False)
    cost = Column(Float, nullable=False)
    usage_amount = Column(Float, nullable=True)
    unit = Column(String, nullable=True)
    currency = Column(String, default="USD")
    
    # Optional FK
    ec2_instance_id = Column(Integer, ForeignKey("ec2_instances.id"), nullable=True)
    ec2_instance = relationship("EC2Instance", back_populates="cost_history")

class AuditLog(BaseModel):
    """Audit log for security and compliance"""
    __tablename__ = "audit_logs"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(255))
    old_values = Column(JSONB)
    new_values = Column(JSONB)
    ip_address = Column(String(45))  # IPv6 compatible
    user_agent = Column(Text)
    session_id = Column(String(255))
    correlation_id = Column(String(255), index=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    # Indexes
    __table_args__ = (
        Index('ix_audit_logs_user_action', 'user_id', 'action'),
        Index('ix_audit_logs_resource', 'resource_type', 'resource_id'),
        Index('ix_audit_logs_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<AuditLog(user_id='{self.user_id}', action='{self.action}', resource='{self.resource_type}')>"

class SystemConfiguration(BaseModel):
    """System configuration and settings"""
    __tablename__ = "system_configurations"
    
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(JSONB, nullable=False)
    description = Column(Text)
    is_encrypted = Column(Boolean, nullable=False, default=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    def __repr__(self):
        return f"<SystemConfiguration(key='{self.key}')>"

# AI-Powered Cost Anomaly Detection Models

class AnomalyEvent(BaseModel):
    """Cost anomaly detection events"""
    __tablename__ = "anomaly_events"
    
    event_id = Column(String(255), unique=True, nullable=False, index=True)
    account_id = Column(String(100), nullable=False, index=True)
    detection_time = Column(DateTime(timezone=True), nullable=False, default=func.now())
    # Backwards-compatible alias used by older code: `detected_at`
    detected_at = detection_time
    anomaly_type = Column(Enum(AnomalyType), nullable=False)
    service = Column(String(100), nullable=False, index=True)
    resource_id = Column(String(255))
    anomaly_score = Column(Numeric(precision=5, scale=2), nullable=False)  # 0.00 to 100.00
    cost_impact = Column(Numeric(precision=12, scale=2), nullable=False)
    percentage_deviation = Column(Numeric(precision=8, scale=2), nullable=False)
    baseline_value = Column(Numeric(precision=12, scale=2), nullable=False)
    actual_value = Column(Numeric(precision=12, scale=2), nullable=False)
    feature_importance = Column(JSONB, default={})
    explanation = Column(Text, nullable=False)
    status = Column(Enum(AnomalyStatus), nullable=False, default=AnomalyStatus.ACTIVE)
    alert_sent = Column(Boolean, nullable=False, default=False)
    resolution_time = Column(DateTime(timezone=True))
    confidence = Column(Numeric(precision=3, scale=2), nullable=False)  # 0.00 to 1.00
    
    # Indexes
    __table_args__ = (
        Index('ix_anomaly_events_account_service', 'account_id', 'service'),
        Index('ix_anomaly_events_detection_time', 'detection_time'),
        Index('ix_anomaly_events_status', 'status'),
        Index('ix_anomaly_events_cost_impact', 'cost_impact'),
    )
    
    @validates('anomaly_score')
    def validate_anomaly_score(self, key, score):
        """Validate anomaly score is between 0 and 100"""
        if not 0 <= score <= 100:
            raise ValueError("Anomaly score must be between 0 and 100")
        return score
    
    @validates('confidence')
    def validate_confidence(self, key, confidence):
        """Validate confidence is between 0 and 1"""
        if not 0 <= confidence <= 1:
            raise ValueError("Confidence must be between 0 and 1")
        return confidence
    
    def __repr__(self):
        return f"<AnomalyEvent(event_id='{self.event_id}', service='{self.service}', impact=${self.cost_impact})>"

class CostForecast(BaseModel):
    """AI-generated cost forecasts"""
    __tablename__ = "cost_forecasts"
    
    forecast_id = Column(String(255), unique=True, nullable=False, index=True)
    account_id = Column(String(100), nullable=False, index=True)
    generated_time = Column(DateTime(timezone=True), nullable=False, default=func.now())
    forecast_period_days = Column(Integer, nullable=False)
    forecast_values = Column(JSONB, nullable=False)  # List of daily forecast values
    confidence_intervals = Column(JSONB)  # Upper and lower bounds
    accuracy_score = Column(Numeric(precision=3, scale=2), nullable=False)
    model_version = Column(String(50), nullable=False)
    key_assumptions = Column(JSONB, default=[])
    risk_factors = Column(JSONB, default=[])
    budget_overrun_probability = Column(Numeric(precision=3, scale=2))
    expected_total_cost = Column(Numeric(precision=12, scale=2), nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('ix_cost_forecasts_account_generated', 'account_id', 'generated_time'),
        Index('ix_cost_forecasts_accuracy', 'accuracy_score'),
    )
    
    @validates('accuracy_score')
    def validate_accuracy_score(self, key, score):
        """Validate accuracy score is between 0 and 1"""
        if not 0 <= score <= 1:
            raise ValueError("Accuracy score must be between 0 and 1")
        return score
    
    def __repr__(self):
        return f"<CostForecast(forecast_id='{self.forecast_id}', account='{self.account_id}', accuracy={self.accuracy_score})>"

class AnomalyConfiguration(BaseModel):
    """Anomaly detection configuration per account"""
    __tablename__ = "anomaly_configurations"
    
    config_id = Column(String(255), unique=True, nullable=False, index=True)
    account_id = Column(String(100), unique=True, nullable=False, index=True)
    sensitivity_level = Column(String(20), nullable=False, default='balanced')  # conservative, balanced, aggressive
    alert_thresholds = Column(JSONB, default={})
    baseline_period_days = Column(Integer, nullable=False, default=30)
    excluded_services = Column(JSONB, default=[])
    maintenance_windows = Column(JSONB, default=[])
    notification_channels = Column(JSONB, default=[])
    auto_acknowledge_threshold = Column(Numeric(precision=3, scale=2), default=0.5)
    escalation_rules = Column(JSONB, default={})
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Indexes
    __table_args__ = (
        Index('ix_anomaly_config_account_active', 'account_id', 'is_active'),
    )
    
    def __repr__(self):
        return f"<AnomalyConfiguration(account_id='{self.account_id}', sensitivity='{self.sensitivity_level}')>"

class MLModelMetrics(BaseModel):
    """ML model performance metrics and monitoring"""
    __tablename__ = "ml_model_metrics"
    
    model_name = Column(String(100), nullable=False, index=True)
    model_version = Column(String(50), nullable=False)
    account_id = Column(String(100), nullable=False, index=True)
    training_date = Column(DateTime(timezone=True), nullable=False)
    accuracy_score = Column(Numeric(precision=5, scale=4), nullable=False)
    precision_score = Column(Numeric(precision=5, scale=4), nullable=False)
    recall_score = Column(Numeric(precision=5, scale=4), nullable=False)
    false_positive_rate = Column(Numeric(precision=5, scale=4), nullable=False)
    detection_latency_ms = Column(Integer, nullable=False)
    training_data_points = Column(Integer, nullable=False)
    feature_count = Column(Integer, nullable=False)
    hyperparameters = Column(JSONB, default={})
    performance_notes = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Indexes
    __table_args__ = (
        Index('ix_ml_metrics_model_account', 'model_name', 'account_id'),
        Index('ix_ml_metrics_training_date', 'training_date'),
        Index('ix_ml_metrics_accuracy', 'accuracy_score'),
        UniqueConstraint('model_name', 'model_version', 'account_id', name='uq_model_version_account'),
    )
    
    def __repr__(self):
        return f"<MLModelMetrics(model='{self.model_name}', version='{self.model_version}', accuracy={self.accuracy_score})>"

# Multi-Cloud Cost Comparison Models

class WorkloadSpecification(BaseModel):
    """Workload specifications for multi-cloud cost comparison"""
    __tablename__ = "workload_specifications"
    
    name = Column(String(200), nullable=False)
    description = Column(Text)
    compute_spec = Column(JSONB, nullable=False)  # CPU, memory, instance preferences
    storage_spec = Column(JSONB, nullable=False)  # Storage requirements
    network_spec = Column(JSONB, nullable=False)  # Network requirements
    database_spec = Column(JSONB)  # Optional database requirements
    additional_services = Column(JSONB, default=[])  # Additional service requirements
    usage_patterns = Column(JSONB, nullable=False)  # Usage patterns and scaling
    compliance_requirements = Column(JSONB, default=[])  # Compliance needs
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Relationships
    created_by_user = relationship("User")
    cost_comparisons = relationship("MultiCloudCostComparison", back_populates="workload")
    
    # Indexes
    __table_args__ = (
        Index('ix_workload_specs_created_by', 'created_by'),
        Index('ix_workload_specs_name', 'name'),
    )
    
    def __repr__(self):
        return f"<WorkloadSpecification(name='{self.name}')>"

class MultiCloudCostComparison(BaseModel):
    """Multi-cloud cost comparison results"""
    __tablename__ = "multi_cloud_cost_comparisons"
    
    workload_id = Column(UUID(as_uuid=True), ForeignKey("workload_specifications.id"), nullable=False, index=True)
    comparison_date = Column(DateTime(timezone=True), nullable=False, default=func.now())
    aws_monthly_cost = Column(Numeric(precision=12, scale=2))
    gcp_monthly_cost = Column(Numeric(precision=12, scale=2))
    azure_monthly_cost = Column(Numeric(precision=12, scale=2))
    aws_annual_cost = Column(Numeric(precision=12, scale=2))
    gcp_annual_cost = Column(Numeric(precision=12, scale=2))
    azure_annual_cost = Column(Numeric(precision=12, scale=2))
    cost_breakdown = Column(JSONB, nullable=False)  # Detailed cost breakdown by service
    recommendations = Column(JSONB, default=[])  # Cost optimization recommendations
    pricing_data_version = Column(String(50))  # Version of pricing data used
    
    # Relationships
    workload = relationship("WorkloadSpecification", back_populates="cost_comparisons")
    
    # Indexes
    __table_args__ = (
        Index('ix_cost_comparisons_workload_date', 'workload_id', 'comparison_date'),
    )
    
    def __repr__(self):
        return f"<MultiCloudCostComparison(workload_id='{self.workload_id}', date='{self.comparison_date}')>"

class TCOAnalysis(BaseModel):
    """Total Cost of Ownership analysis results"""
    __tablename__ = "tco_analyses"
    
    workload_id = Column(UUID(as_uuid=True), ForeignKey("workload_specifications.id"), nullable=False, index=True)
    analysis_date = Column(DateTime(timezone=True), nullable=False, default=func.now())
    time_horizon_years = Column(Integer, nullable=False)
    aws_tco = Column(JSONB, nullable=False)  # TCO breakdown for AWS
    gcp_tco = Column(JSONB, nullable=False)  # TCO breakdown for GCP
    azure_tco = Column(JSONB, nullable=False)  # TCO breakdown for Azure
    hidden_costs = Column(JSONB, nullable=False)  # Hidden costs analysis
    operational_costs = Column(JSONB, nullable=False)  # Operational overhead
    cost_projections = Column(JSONB, nullable=False)  # Year-by-year projections
    
    # Relationships
    workload = relationship("WorkloadSpecification")
    
    # Indexes
    __table_args__ = (
        Index('ix_tco_analyses_workload_date', 'workload_id', 'analysis_date'),
    )
    
    def __repr__(self):
        return f"<TCOAnalysis(workload_id='{self.workload_id}', years={self.time_horizon_years})>"

class MigrationAnalysis(BaseModel):
    """Migration cost analysis between cloud providers"""
    __tablename__ = "migration_analyses"
    
    workload_id = Column(UUID(as_uuid=True), ForeignKey("workload_specifications.id"), nullable=False, index=True)
    source_provider = Column(String(20), nullable=False)  # aws, gcp, azure
    target_provider = Column(String(20), nullable=False)  # aws, gcp, azure
    analysis_date = Column(DateTime(timezone=True), nullable=False, default=func.now())
    migration_cost = Column(Numeric(precision=12, scale=2), nullable=False)
    migration_timeline_days = Column(Integer, nullable=False)
    break_even_months = Column(Integer)
    risk_assessment = Column(JSONB, nullable=False)
    cost_breakdown = Column(JSONB, nullable=False)  # Data transfer, downtime, etc.
    recommendations = Column(JSONB, nullable=False)
    
    # Relationships
    workload = relationship("WorkloadSpecification")
    
    # Indexes
    __table_args__ = (
        Index('ix_migration_analyses_workload_providers', 'workload_id', 'source_provider', 'target_provider'),
        Index('ix_migration_analyses_date', 'analysis_date'),
    )
    
    def __repr__(self):
        return f"<MigrationAnalysis(workload_id='{self.workload_id}', {self.source_provider}->{self.target_provider})>"

class ProviderPricing(BaseModel):
    """Provider pricing data for multi-cloud comparison"""
    __tablename__ = "provider_pricing"
    
    provider = Column(String(20), nullable=False, index=True)  # aws, gcp, azure
    service_name = Column(String(100), nullable=False, index=True)
    service_category = Column(String(50), nullable=False, index=True)
    region = Column(String(50), nullable=False, index=True)
    pricing_unit = Column(String(20), nullable=False)  # hour, gb-month, request
    price_per_unit = Column(Numeric(precision=10, scale=6), nullable=False)
    currency = Column(String(3), nullable=False, default='USD')
    effective_date = Column(DateTime(timezone=True), nullable=False)
    last_updated = Column(DateTime(timezone=True), nullable=False, default=func.now())
    pricing_details = Column(JSONB, default={})  # Additional pricing metadata
    
    # Indexes
    __table_args__ = (
        Index('ix_provider_pricing_provider_service', 'provider', 'service_name'),
        Index('ix_provider_pricing_region_date', 'region', 'effective_date'),
        Index('ix_provider_pricing_category', 'service_category'),
    )
    
    def __repr__(self):
        return f"<ProviderPricing(provider='{self.provider}', service='{self.service_name}', price={self.price_per_unit})>"
# Service Equivalency Models

class ServiceEquivalency(BaseModel):
    """Service equivalency mappings across cloud providers"""
    __tablename__ = "service_equivalencies"
    
    source_provider = Column(String(20), nullable=False, index=True)
    source_service = Column(String(100), nullable=False, index=True)
    target_provider = Column(String(20), nullable=False, index=True)
    target_service = Column(String(100), nullable=False, index=True)
    service_category = Column(String(50), nullable=False, index=True)
    confidence_score = Column(Numeric(precision=3, scale=2), nullable=False)  # 0.00 to 1.00
    feature_parity_score = Column(Numeric(precision=3, scale=2), nullable=False)  # 0.00 to 1.00
    performance_ratio = Column(Numeric(precision=4, scale=2), nullable=False)  # Relative performance
    cost_efficiency_score = Column(Numeric(precision=3, scale=2), nullable=False)  # 0.00 to 1.00
    migration_complexity = Column(String(20), nullable=False)  # low, medium, high
    limitations = Column(JSONB, default=[])  # List of limitations
    additional_features = Column(JSONB, default=[])  # Additional features
    mapping_notes = Column(Text)
    
    # Indexes
    __table_args__ = (
        Index('ix_service_equiv_source', 'source_provider', 'source_service'),
        Index('ix_service_equiv_target', 'target_provider', 'target_service'),
        Index('ix_service_equiv_category', 'service_category'),
        UniqueConstraint('source_provider', 'source_service', 'target_provider', 'target_service', 
                        name='uq_service_equivalency'),
    )
    
    @validates('confidence_score', 'feature_parity_score', 'cost_efficiency_score')
    def validate_scores(self, key, score):
        """Validate scores are between 0 and 1"""
        if not 0 <= score <= 1:
            raise ValueError(f"{key} must be between 0 and 1")
        return score


class ResourceMetrics(Base):
    """Resource performance and utilization metrics"""
    __tablename__ = "resource_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource_id = Column(String(255), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Performance metrics
    cpu_utilization = Column(Numeric(5, 2))  # Percentage
    memory_utilization = Column(Numeric(5, 2))  # Percentage
    network_in = Column(Numeric(15, 2))  # Bytes
    network_out = Column(Numeric(15, 2))  # Bytes
    disk_read = Column(Numeric(15, 2))  # Bytes
    disk_write = Column(Numeric(15, 2))  # Bytes
    
    # Application metrics
    request_count = Column(Integer)
    response_time = Column(Numeric(10, 3))  # Milliseconds
    error_rate = Column(Numeric(5, 2))  # Percentage
    
    # Metadata
    resource_metadata = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('ix_resource_metrics_resource_time', 'resource_id', 'timestamp'),
        Index('ix_resource_metrics_type_time', 'resource_type', 'timestamp'),
    )


class ScalingEvent(Base):
    """Record of scaling events and their outcomes"""
    __tablename__ = "scaling_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource_id = Column(String(255), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False)
    
    # Scaling details
    scaling_action = Column(String(50), nullable=False)  # scale_up, scale_down, etc.
    previous_capacity = Column(Integer, nullable=False)
    target_capacity = Column(Integer, nullable=False)
    actual_capacity = Column(Integer)  # What was actually achieved
    
    # Execution details
    triggered_by = Column(String(100))  # predictive_engine, manual, etc.
    trigger_reason = Column(Text)
    execution_time = Column(DateTime(timezone=True), nullable=False)
    completion_time = Column(DateTime(timezone=True))
    
    # Results
    success = Column(Boolean, nullable=False)
    error_message = Column(Text)
    cost_impact = Column(Numeric(10, 2))  # Dollar impact
    performance_impact = Column(JSONB, default=dict)
    
    # Metadata
    scaling_metadata = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('ix_scaling_events_resource', 'resource_id'),
        Index('ix_scaling_events_time', 'execution_time'),
        Index('ix_scaling_events_success', 'success'),
    )
    
    def __repr__(self):
        return f"<ServiceEquivalency({self.source_provider}:{self.source_service} -> {self.target_provider}:{self.target_service})>"

class FeatureParityAnalysis(BaseModel):
    """Feature parity analysis results between equivalent services"""
    __tablename__ = "feature_parity_analyses"
    
    analysis_id = Column(String(255), unique=True, nullable=False, index=True)
    reference_service = Column(String(100), nullable=False)
    reference_provider = Column(String(20), nullable=False)
    comparison_services = Column(JSONB, nullable=False)  # List of services being compared
    feature_matrix = Column(JSONB, nullable=False)  # Feature comparison matrix
    missing_features = Column(JSONB, nullable=False)  # Missing features by provider
    additional_features = Column(JSONB, nullable=False)  # Additional features by provider
    overall_parity_score = Column(Numeric(precision=3, scale=2), nullable=False)
    analysis_date = Column(DateTime(timezone=True), nullable=False, default=func.now())
    workload_context = Column(JSONB)  # Optional workload context
    
    # Indexes
    __table_args__ = (
        Index('ix_feature_parity_reference', 'reference_provider', 'reference_service'),
        Index('ix_feature_parity_date', 'analysis_date'),
    )
    
    @validates('overall_parity_score')
    def validate_parity_score(self, key, score):
        """Validate parity score is between 0 and 1"""
        if not 0 <= score <= 1:
            raise ValueError("Overall parity score must be between 0 and 1")
        return score
    
    def __repr__(self):
        return f"<FeatureParityAnalysis(id='{self.analysis_id}', reference={self.reference_provider}:{self.reference_service})>"


# ML Model Management Models

class MLExperiment(BaseModel):
    """ML experiment tracking"""
    __tablename__ = "ml_experiments"
    
    experiment_name = Column(String(200), nullable=False, index=True)
    description = Column(Text)
    created_by = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False, default="created")
    tags = Column(JSONB, default={})
    
    # Relationships
    runs = relationship("MLExperimentRun", back_populates="experiment")
    
    # Indexes
    __table_args__ = (
        Index('ix_ml_experiments_name_status', 'experiment_name', 'status'),
        Index('ix_ml_experiments_created_by', 'created_by'),
    )
    
    def __repr__(self):
        return f"<MLExperiment(name='{self.experiment_name}', status='{self.status}')>"

class MLExperimentRun(BaseModel):
    """ML experiment run tracking"""
    __tablename__ = "ml_experiment_runs"
    
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("ml_experiments.id"), nullable=False, index=True)
    run_name = Column(String(200), nullable=False)
    status = Column(String(50), nullable=False, default="running")
    start_time = Column(DateTime(timezone=True), nullable=False, default=func.now())
    end_time = Column(DateTime(timezone=True))
    parameters = Column(JSONB, default={})
    metrics = Column(JSONB, default={})
    tags = Column(JSONB, default={})
    mlflow_run_id = Column(String(255), index=True)
    
    # Relationships
    experiment = relationship("MLExperiment", back_populates="runs")
    artifacts = relationship("MLArtifact", back_populates="run")
    
    # Indexes
    __table_args__ = (
        Index('ix_ml_runs_experiment_status', 'experiment_id', 'status'),
        Index('ix_ml_runs_start_time', 'start_time'),
    )
    
    def __repr__(self):
        return f"<MLExperimentRun(name='{self.run_name}', status='{self.status}')>"

class MLArtifact(BaseModel):
    """ML experiment artifacts"""
    __tablename__ = "ml_artifacts"
    
    run_id = Column(UUID(as_uuid=True), ForeignKey("ml_experiment_runs.id"), nullable=False, index=True)
    artifact_name = Column(String(200), nullable=False)
    artifact_type = Column(String(50), nullable=False)  # model, dataset, plot, report, config
    file_path = Column(String(500), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    artifact_metadata = Column(JSONB, default={})
    
    # Relationships
    run = relationship("MLExperimentRun", back_populates="artifacts")
    
    # Indexes
    __table_args__ = (
        Index('ix_ml_artifacts_run_type', 'run_id', 'artifact_type'),
    )
    
    def __repr__(self):
        return f"<MLArtifact(name='{self.artifact_name}', type='{self.artifact_type}')>"

class ABTest(BaseModel):
    """A/B test tracking"""
    __tablename__ = "ab_tests"
    
    test_name = Column(String(200), nullable=False, index=True)
    description = Column(Text)
    test_type = Column(String(50), nullable=False)  # model_comparison, feature_comparison, etc.
    status = Column(String(50), nullable=False, default="draft")
    primary_metric = Column(String(100), nullable=False)
    secondary_metrics = Column(JSONB, default=[])
    minimum_sample_size = Column(Integer, nullable=False, default=1000)
    significance_level = Column(Numeric(precision=3, scale=2), nullable=False, default=0.05)
    power = Column(Numeric(precision=3, scale=2), nullable=False, default=0.8)
    traffic_split_strategy = Column(String(50), nullable=False, default="random")
    duration_days = Column(Integer, nullable=False, default=14)
    started_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))
    winning_variant_id = Column(String(255))
    conclusion_reason = Column(Text)
    account_id = Column(String(100), nullable=False, index=True)
    
    # Relationships
    variants = relationship("ABTestVariant", back_populates="test")
    results = relationship("ABTestResult", back_populates="test")
    
    # Indexes
    __table_args__ = (
        Index('ix_ab_tests_account_status', 'account_id', 'status'),
        Index('ix_ab_tests_started_at', 'started_at'),
    )
    
    def __repr__(self):
        return f"<ABTest(name='{self.test_name}', status='{self.status}')>"

class ABTestVariant(BaseModel):
    """A/B test variant configuration"""
    __tablename__ = "ab_test_variants"
    
    test_id = Column(UUID(as_uuid=True), ForeignKey("ab_tests.id"), nullable=False, index=True)
    variant_id = Column(String(255), nullable=False)
    variant_name = Column(String(200), nullable=False)
    description = Column(Text)
    model_id = Column(String(255), nullable=False)
    traffic_percentage = Column(Numeric(precision=5, scale=2), nullable=False)
    configuration = Column(JSONB, default={})
    
    # Relationships
    test = relationship("ABTest", back_populates="variants")
    
    # Indexes
    __table_args__ = (
        Index('ix_ab_variants_test_variant', 'test_id', 'variant_id'),
        UniqueConstraint('test_id', 'variant_id', name='uq_test_variant'),
    )
    
    def __repr__(self):
        return f"<ABTestVariant(name='{self.variant_name}', traffic={self.traffic_percentage}%)>"

class ABTestResult(BaseModel):
    """A/B test results tracking"""
    __tablename__ = "ab_test_results"
    
    test_id = Column(UUID(as_uuid=True), ForeignKey("ab_tests.id"), nullable=False, index=True)
    variant_id = Column(String(255), nullable=False)
    sample_size = Column(Integer, nullable=False, default=0)
    conversions = Column(Integer, nullable=False, default=0)
    conversion_rate = Column(Numeric(precision=5, scale=4), nullable=False, default=0)
    average_response_time = Column(Numeric(precision=8, scale=2), nullable=False, default=0)
    error_rate = Column(Numeric(precision=5, scale=4), nullable=False, default=0)
    custom_metrics = Column(JSONB, default={})
    confidence_interval_lower = Column(Numeric(precision=5, scale=4))
    confidence_interval_upper = Column(Numeric(precision=5, scale=4))
    last_updated = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # Relationships
    test = relationship("ABTest", back_populates="results")
    
    # Indexes
    __table_args__ = (
        Index('ix_ab_results_test_variant', 'test_id', 'variant_id'),
        Index('ix_ab_results_updated', 'last_updated'),
        UniqueConstraint('test_id', 'variant_id', name='uq_test_variant_result'),
    )
    
    def __repr__(self):
        return f"<ABTestResult(test_id='{self.test_id}', variant='{self.variant_id}', rate={self.conversion_rate})>"

class ModelExplanation(BaseModel):
    """Model explanation and interpretability results"""
    __tablename__ = "model_explanations"
    
    model_id = Column(String(255), nullable=False, index=True)
    explanation_type = Column(String(50), nullable=False)  # global, local, feature_importance, etc.
    method = Column(String(50), nullable=False)  # shap, lime, permutation_importance, etc.
    feature_names = Column(JSONB, nullable=False)
    explanation_data = Column(JSONB, nullable=False)
    confidence_score = Column(Numeric(precision=3, scale=2), nullable=False)
    explanation_metadata = Column(JSONB, default={})
    
    # Indexes
    __table_args__ = (
        Index('ix_explanations_model_type', 'model_id', 'explanation_type'),
        Index('ix_explanations_method', 'method'),
    )
    
    def __repr__(self):
        return f"<ModelExplanation(model_id='{self.model_id}', method='{self.method}')>"

class BiasAnalysis(BaseModel):
    """Bias analysis results"""
    __tablename__ = "bias_analyses"
    
    model_id = Column(String(255), nullable=False, index=True)
    protected_attributes = Column(JSONB, nullable=False)
    bias_metrics = Column(JSONB, nullable=False)
    overall_bias_score = Column(Numeric(precision=5, scale=4), nullable=False)
    bias_detected = Column(Boolean, nullable=False, default=False)
    recommendations = Column(JSONB, default=[])
    analysis_metadata = Column(JSONB, default={})
    
    # Indexes
    __table_args__ = (
        Index('ix_bias_analyses_model', 'model_id'),
        Index('ix_bias_analyses_score', 'overall_bias_score'),
        Index('ix_bias_analyses_detected', 'bias_detected'),
    )
    
    def __repr__(self):
        return f"<BiasAnalysis(model_id='{self.model_id}', bias_score={self.overall_bias_score})>"

class FairnessReport(BaseModel):
    """Comprehensive fairness reports"""
    __tablename__ = "fairness_reports"
    
    model_id = Column(String(255), nullable=False, index=True)
    dataset_info = Column(JSONB, nullable=False)
    protected_groups = Column(JSONB, nullable=False)
    fairness_metrics = Column(JSONB, nullable=False)
    bias_analysis_id = Column(UUID(as_uuid=True), ForeignKey("bias_analyses.id"))
    mitigation_recommendations = Column(JSONB, default=[])
    compliance_status = Column(JSONB, default={})
    
    # Relationships
    bias_analysis = relationship("BiasAnalysis")
    
    # Indexes
    __table_args__ = (
        Index('ix_fairness_reports_model', 'model_id'),
    )
    
    def __repr__(self):
        return f"<FairnessReport(model_id='{self.model_id}')>"

class MitigationResult(BaseModel):
    """Bias mitigation results"""
    __tablename__ = "mitigation_results"
    
    original_model_id = Column(String(255), nullable=False, index=True)
    mitigated_model_id = Column(String(255), nullable=False, index=True)
    strategy = Column(String(50), nullable=False)  # resampling, reweighting, threshold_optimization, etc.
    before_metrics = Column(JSONB, nullable=False)
    after_metrics = Column(JSONB, nullable=False)
    improvement_score = Column(Numeric(precision=5, scale=4), nullable=False)
    trade_offs = Column(JSONB, default={})
    
    # Indexes
    __table_args__ = (
        Index('ix_mitigation_original_model', 'original_model_id'),
        Index('ix_mitigation_strategy', 'strategy'),
        Index('ix_mitigation_improvement', 'improvement_score'),
    )
    
    def __repr__(self):
        return f"<MitigationResult(strategy='{self.strategy}', improvement={self.improvement_score})>"

class EC2Instance(Base):
    __tablename__ = "ec2_instances"
    
    id = Column(String, primary_key=True)
    instance_type = Column(String)
    state = Column(String)
    region = Column(String)
    launch_time = Column(DateTime)
    
    # Relationships
    recommendations = relationship("OptimizationRecommendation", back_populates="ec2_instance")
    cost_history = relationship("CostHistory", back_populates="ec2_instance")

class EBSVolume(Base):
    __tablename__ = "ebs_volumes"
    
    id = Column(String, primary_key=True)
    size = Column(Integer)
    volume_type = Column(String)
    state = Column(String)
    region = Column(String)
    attached_to = Column(String, nullable=True)

class ScanStatus(PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(Enum(ScanStatus), default=ScanStatus.PENDING)
    resource_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

# Compatibility alias for code expecting `AnomalyDetection` model name
# Historically parts of the codebase imported `AnomalyDetection` from
# `app.models.models` (e.g. `resources_router`). Provide a simple
# alias so those imports continue to work and reference the `AnomalyEvent`
# SQLAlchemy model defined above.
try:
    AnomalyDetection = AnomalyEvent
except NameError:
    # If AnomalyEvent is not defined for some reason, skip the alias.
    AnomalyDetection = None
