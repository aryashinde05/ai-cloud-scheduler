"""
Pydantic models for Multi-Cloud Cost Comparison API

These models define the request/response schemas for the multi-cloud cost comparison endpoints.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union
from enum import Enum

from pydantic import BaseModel, Field, validator
from pydantic.types import UUID4


class CloudProvider(str, Enum):
    """Supported cloud providers"""
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"


class InstanceSize(str, Enum):
    """Instance size categories"""
    MICRO = "micro"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    XLARGE = "xlarge"
    CUSTOM = "custom"


class StorageType(str, Enum):
    """Storage types"""
    OBJECT = "object"
    BLOCK = "block"
    FILE = "file"
    DATABASE = "database"


class NetworkServiceType(str, Enum):
    """Network service types"""
    LOAD_BALANCER = "load_balancer"
    CDN = "cdn"
    API_GATEWAY = "api_gateway"
    VPN = "vpn"
    DIRECT_CONNECT = "direct_connect"


# Workload Specification Models

class ComputeSpec(BaseModel):
    """Compute requirements specification"""
    vcpus: int = Field(..., ge=1, le=1000, description="Number of virtual CPUs")
    memory_gb: float = Field(..., ge=0.5, le=10000, description="Memory in GB")
    instance_type: str = Field(default="general_purpose", description="Instance type category")
    operating_system: str = Field(default="linux", description="Operating system")
    architecture: str = Field(default="x86_64", description="CPU architecture")
    
    # Optional requirements
    gpu_requirements: Optional[Dict[str, Any]] = Field(default=None, description="GPU requirements")
    container_requirements: Optional[Dict[str, Any]] = Field(default=None, description="Container requirements")
    execution_model: Optional[str] = Field(default="persistent", description="Execution model")
    performance_requirements: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Performance requirements")
    security_requirements: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Security requirements")
    required_features: Optional[List[str]] = Field(default_factory=list, description="Required features")
    
    @validator('vcpus')
    def validate_vcpus(cls, v):
        if v <= 0:
            raise ValueError('vCPUs must be positive')
        return v
    
    @validator('memory_gb')
    def validate_memory(cls, v):
        if v <= 0:
            raise ValueError('Memory must be positive')
        return v


class StorageSpec(BaseModel):
    """Storage requirements specification"""
    storage_type: StorageType = Field(..., description="Type of storage")
    capacity_gb: int = Field(..., ge=1, description="Storage capacity in GB")
    access_pattern: str = Field(default="frequent", description="Access pattern")
    durability_requirements: Optional[str] = Field(default=None, description="Durability requirements")
    
    # Performance requirements
    iops_requirement: Optional[int] = Field(default=None, description="IOPS requirement")
    throughput_mbps: Optional[int] = Field(default=None, description="Throughput in MB/s")
    
    # Additional specifications
    backup_requirements: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Backup requirements")
    encryption_requirements: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Encryption requirements")
    performance_requirements: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Performance requirements")
    
    @validator('capacity_gb')
    def validate_capacity(cls, v):
        if v <= 0:
            raise ValueError('Storage capacity must be positive')
        return v


class NetworkComponent(BaseModel):
    """Network component specification"""
    service_type: NetworkServiceType = Field(..., description="Type of network service")
    requirements: Dict[str, Any] = Field(default_factory=dict, description="Service-specific requirements")
    bandwidth_requirements: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Bandwidth requirements")


class NetworkSpec(BaseModel):
    """Network requirements specification"""
    components: List[NetworkComponent] = Field(default_factory=list, description="Network components")
    bandwidth_requirements: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Overall bandwidth requirements")
    latency_requirements: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Latency requirements")
    security_requirements: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Network security requirements")


class DatabaseSpec(BaseModel):
    """Database requirements specification"""
    database_type: str = Field(..., description="Database type (mysql, postgresql, etc.)")
    instance_class: str = Field(..., description="Database instance class")
    storage_gb: int = Field(..., ge=1, description="Database storage in GB")
    backup_retention_days: int = Field(default=7, ge=0, le=365, description="Backup retention in days")
    multi_az: bool = Field(default=False, description="Multi-AZ deployment")
    read_replicas: int = Field(default=0, ge=0, le=10, description="Number of read replicas")
    
    # Performance requirements
    iops_requirement: Optional[int] = Field(default=None, description="IOPS requirement")
    connection_limit: Optional[int] = Field(default=None, description="Maximum connections")
    
    @validator('storage_gb')
    def validate_storage(cls, v):
        if v <= 0:
            raise ValueError('Database storage must be positive')
        return v


class WorkloadSpec(BaseModel):
    """Complete workload specification for multi-cloud comparison"""
    name: str = Field(..., min_length=1, max_length=200, description="Workload name")
    description: Optional[str] = Field(default=None, description="Workload description")
    
    # Core specifications
    compute: ComputeSpec = Field(..., description="Compute requirements")
    storage: List[StorageSpec] = Field(default_factory=list, description="Storage requirements")
    network: Optional[NetworkSpec] = Field(default=None, description="Network requirements")
    database: Optional[DatabaseSpec] = Field(default=None, description="Database requirements")
    
    # Additional specifications
    additional_services: List[Dict[str, Any]] = Field(default_factory=list, description="Additional service requirements")
    usage_patterns: Dict[str, Any] = Field(default_factory=dict, description="Usage patterns and scaling")
    compliance_requirements: List[str] = Field(default_factory=list, description="Compliance requirements")
    
    # Metadata
    tags: Dict[str, str] = Field(default_factory=dict, description="Workload tags")
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Workload name cannot be empty')
        return v.strip()


# Cost Comparison Response Models

class ServiceCost(BaseModel):
    """Cost breakdown for a specific service"""
    service_name: str = Field(..., description="Service name")
    service_category: str = Field(..., description="Service category")
    monthly_cost: Decimal = Field(..., description="Monthly cost")
    annual_cost: Decimal = Field(..., description="Annual cost")
    cost_breakdown: Dict[str, Decimal] = Field(default_factory=dict, description="Detailed cost breakdown")
    pricing_model: str = Field(..., description="Pricing model used")
    confidence_score: float = Field(..., ge=0, le=1, description="Confidence in cost estimate")


class ProviderCostSummary(BaseModel):
    """Cost summary for a cloud provider"""
    provider: CloudProvider = Field(..., description="Cloud provider")
    total_monthly_cost: Decimal = Field(..., description="Total monthly cost")
    total_annual_cost: Decimal = Field(..., description="Total annual cost")
    service_costs: List[ServiceCost] = Field(default_factory=list, description="Service-level costs")
    cost_breakdown: Dict[str, Decimal] = Field(default_factory=dict, description="Cost breakdown by category")
    
    # Additional cost factors
    data_transfer_cost: Decimal = Field(default=Decimal('0'), description="Data transfer costs")
    support_cost: Decimal = Field(default=Decimal('0'), description="Support costs")
    hidden_costs: Dict[str, Decimal] = Field(default_factory=dict, description="Hidden costs")


class CostComparison(BaseModel):
    """Multi-cloud cost comparison results"""
    workload_name: str = Field(..., description="Workload name")
    comparison_id: str = Field(..., description="Unique comparison ID")
    comparison_date: datetime = Field(default_factory=datetime.utcnow, description="Comparison timestamp")
    
    # Provider costs
    provider_costs: Dict[CloudProvider, ProviderCostSummary] = Field(..., description="Costs by provider")
    
    # Comparison metrics
    lowest_cost_provider: CloudProvider = Field(..., description="Provider with lowest cost")
    highest_cost_provider: CloudProvider = Field(..., description="Provider with highest cost")
    cost_difference_percentage: float = Field(..., description="Percentage difference between lowest and highest")
    
    # Metadata
    currency: str = Field(default="USD", description="Currency used")
    pricing_data_version: Optional[str] = Field(default=None, description="Version of pricing data")
    assumptions: List[str] = Field(default_factory=list, description="Assumptions made in comparison")


class TCOBreakdown(BaseModel):
    """TCO breakdown for a specific time period"""
    year: int = Field(..., description="Year number")
    infrastructure_cost: Decimal = Field(..., description="Infrastructure costs")
    operational_cost: Decimal = Field(..., description="Operational costs")
    support_cost: Decimal = Field(..., description="Support costs")
    training_cost: Decimal = Field(default=Decimal('0'), description="Training costs")
    migration_cost: Decimal = Field(default=Decimal('0'), description="Migration costs")
    total_cost: Decimal = Field(..., description="Total cost for the year")


class TCOAnalysis(BaseModel):
    """Total Cost of Ownership analysis"""
    workload_name: str = Field(..., description="Workload name")
    analysis_id: str = Field(..., description="Unique analysis ID")
    analysis_date: datetime = Field(default_factory=datetime.utcnow, description="Analysis timestamp")
    time_horizon_years: int = Field(..., ge=1, le=10, description="Analysis time horizon")
    
    # TCO by provider
    provider_tco: Dict[CloudProvider, List[TCOBreakdown]] = Field(..., description="TCO breakdown by provider and year")
    
    # Summary metrics
    total_tco_by_provider: Dict[CloudProvider, Decimal] = Field(..., description="Total TCO by provider")
    lowest_tco_provider: CloudProvider = Field(..., description="Provider with lowest TCO")
    tco_savings_percentage: float = Field(..., description="Savings percentage vs highest TCO")
    
    # Additional analysis
    hidden_cost_factors: Dict[str, Dict[CloudProvider, Decimal]] = Field(default_factory=dict, description="Hidden cost factors")
    risk_factors: List[str] = Field(default_factory=list, description="Risk factors considered")
    
    @validator('time_horizon_years')
    def validate_time_horizon(cls, v):
        if v < 1 or v > 10:
            raise ValueError('Time horizon must be between 1 and 10 years')
        return v


class MigrationCostBreakdown(BaseModel):
    """Migration cost breakdown"""
    data_transfer_cost: Decimal = Field(..., description="Data transfer costs")
    downtime_cost: Decimal = Field(..., description="Downtime impact cost")
    retraining_cost: Decimal = Field(..., description="Staff retraining costs")
    consulting_cost: Decimal = Field(..., description="Consulting and professional services")
    tool_licensing_cost: Decimal = Field(default=Decimal('0'), description="Migration tool licensing")
    testing_cost: Decimal = Field(..., description="Testing and validation costs")
    total_migration_cost: Decimal = Field(..., description="Total migration cost")


class RiskAssessment(BaseModel):
    """Migration risk assessment"""
    overall_risk_level: str = Field(..., description="Overall risk level (low/medium/high)")
    risk_factors: List[Dict[str, Any]] = Field(default_factory=list, description="Identified risk factors")
    mitigation_strategies: List[str] = Field(default_factory=list, description="Risk mitigation strategies")
    success_probability: float = Field(..., ge=0, le=1, description="Migration success probability")


class MigrationAnalysis(BaseModel):
    """Migration cost and timeline analysis"""
    analysis_id: str = Field(..., description="Unique analysis ID")
    workload_name: str = Field(..., description="Workload name")
    source_provider: CloudProvider = Field(..., description="Source cloud provider")
    target_provider: CloudProvider = Field(..., description="Target cloud provider")
    analysis_date: datetime = Field(default_factory=datetime.utcnow, description="Analysis timestamp")
    
    # Migration costs
    migration_costs: MigrationCostBreakdown = Field(..., description="Migration cost breakdown")
    
    # Timeline and ROI
    estimated_timeline_days: int = Field(..., ge=1, description="Estimated migration timeline in days")
    break_even_months: Optional[int] = Field(default=None, description="Break-even period in months")
    monthly_savings: Decimal = Field(..., description="Monthly savings after migration")
    
    # Risk assessment
    risk_assessment: RiskAssessment = Field(..., description="Migration risk assessment")
    
    # Recommendations
    recommended_approach: str = Field(..., description="Recommended migration approach")
    key_considerations: List[str] = Field(default_factory=list, description="Key considerations")
    
    @validator('estimated_timeline_days')
    def validate_timeline(cls, v):
        if v <= 0:
            raise ValueError('Migration timeline must be positive')
        return v


class CostRecommendation(BaseModel):
    """Cost optimization recommendation"""
    recommendation_id: str = Field(..., description="Unique recommendation ID")
    recommendation_type: str = Field(..., description="Type of recommendation")
    title: str = Field(..., description="Recommendation title")
    description: str = Field(..., description="Detailed description")
    
    # Impact
    potential_savings: Decimal = Field(..., description="Potential cost savings")
    implementation_effort: str = Field(..., description="Implementation effort level")
    risk_level: str = Field(..., description="Risk level")
    
    # Implementation
    implementation_steps: List[str] = Field(default_factory=list, description="Implementation steps")
    prerequisites: List[str] = Field(default_factory=list, description="Prerequisites")
    
    # Metadata
    confidence_score: float = Field(..., ge=0, le=1, description="Confidence in recommendation")
    applicable_providers: List[CloudProvider] = Field(default_factory=list, description="Applicable providers")


# Request Models

class CostComparisonRequest(BaseModel):
    """Request for multi-cloud cost comparison"""
    workload: WorkloadSpec = Field(..., description="Workload specification")
    providers: List[CloudProvider] = Field(default_factory=lambda: list(CloudProvider), description="Providers to compare")
    regions: Optional[Dict[CloudProvider, str]] = Field(default=None, description="Preferred regions by provider")
    include_support_costs: bool = Field(default=True, description="Include support costs")
    include_data_transfer: bool = Field(default=True, description="Include data transfer costs")


class TCOAnalysisRequest(BaseModel):
    """Request for TCO analysis"""
    workload: WorkloadSpec = Field(..., description="Workload specification")
    time_horizon_years: int = Field(default=3, ge=1, le=10, description="Analysis time horizon")
    providers: List[CloudProvider] = Field(default_factory=lambda: list(CloudProvider), description="Providers to analyze")
    include_hidden_costs: bool = Field(default=True, description="Include hidden costs")
    growth_assumptions: Optional[Dict[str, float]] = Field(default=None, description="Growth assumptions")


class MigrationAnalysisRequest(BaseModel):
    """Request for migration analysis"""
    workload: WorkloadSpec = Field(..., description="Workload specification")
    source_provider: CloudProvider = Field(..., description="Source provider")
    target_provider: CloudProvider = Field(..., description="Target provider")
    current_monthly_cost: Optional[Decimal] = Field(default=None, description="Current monthly cost")
    migration_timeline_preference: Optional[str] = Field(default=None, description="Preferred timeline")
    risk_tolerance: str = Field(default="medium", description="Risk tolerance level")


# Response Models

class CostComparisonResponse(BaseModel):
    """Response for cost comparison request"""
    success: bool = Field(..., description="Request success status")
    comparison: Optional[CostComparison] = Field(default=None, description="Cost comparison results")
    recommendations: List[CostRecommendation] = Field(default_factory=list, description="Cost recommendations")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")


class TCOAnalysisResponse(BaseModel):
    """Response for TCO analysis request"""
    success: bool = Field(..., description="Request success status")
    analysis: Optional[TCOAnalysis] = Field(default=None, description="TCO analysis results")
    recommendations: List[CostRecommendation] = Field(default_factory=list, description="TCO recommendations")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")


class MigrationAnalysisResponse(BaseModel):
    """Response for migration analysis request"""
    success: bool = Field(..., description="Request success status")
    analysis: Optional[MigrationAnalysis] = Field(default=None, description="Migration analysis results")
    recommendations: List[CostRecommendation] = Field(default_factory=list, description="Migration recommendations")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")

class SavingsOpportunity(BaseModel):
    opportunity_type: str = Field(...)
    description: str = Field(...)
    monthly_savings: Decimal = Field(...)
    annual_savings: Decimal = Field(...)
    confidence_score: float = Field(...)
    applicable_providers: List[str] = Field(...)

class RiskFactor(BaseModel):
    risk_type: str = Field(...)
    risk_level: str = Field(...)
    description: str = Field(...)
    mitigation_strategy: str = Field(...)
    impact_score: float = Field(...)

class MigrationPhase(BaseModel):
    phase_name: str = Field(...)
    duration_days: int = Field(...)
    cost: Decimal = Field(...)
    dependencies: List[str] = Field(...)
    deliverables: List[str] = Field(...)

class TCOComponent(BaseModel):
    component_name: str = Field(...)
    year_1_cost: Decimal = Field(...)
    year_2_cost: Decimal = Field(...)
    year_3_cost: Decimal = Field(...)
    total_cost: Decimal = Field(...)
    description: str = Field(...)
