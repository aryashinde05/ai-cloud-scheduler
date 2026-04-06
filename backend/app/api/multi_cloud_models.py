"""
Pydantic models for the Multi-Cloud API.

The router `app.api.multi_cloud` imports these models, but the module was
missing, preventing the backend from starting.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    message: str
    details: Optional[Dict[str, Any]] = None


class ComputeSpecRequest(BaseModel):
    cpu_cores: int = Field(..., ge=1)
    memory_gb: float = Field(..., ge=0.5)
    operating_system: Optional[str] = "linux"
    architecture: Optional[str] = "x86_64"


class StorageSpecRequest(BaseModel):
    storage_type: str = Field("block", description="block|object")
    primary_storage_gb: int = Field(..., ge=1)
    iops_requirement: Optional[int] = None
    throughput_mbps: Optional[float] = None


class NetworkSpecRequest(BaseModel):
    data_transfer_gb_monthly: float = Field(0, ge=0)
    cdn_required: bool = False


class DatabaseSpecRequest(BaseModel):
    database_type: str = "postgres"
    storage_gb: int = Field(20, ge=1)
    backup_retention_days: int = Field(7, ge=0)


class UsagePatternsRequest(BaseModel):
    hours_per_day: int = Field(24, ge=1, le=24)
    days_per_month: int = Field(30, ge=1, le=31)
    utilization_percent: float = Field(50, ge=0, le=100)


class WorkloadSpecRequest(BaseModel):
    name: str
    description: Optional[str] = None
    compute_spec: ComputeSpecRequest
    storage_spec: StorageSpecRequest
    network_spec: NetworkSpecRequest
    database_spec: Optional[DatabaseSpecRequest] = None
    additional_services: List[str] = []
    usage_patterns: UsagePatternsRequest = UsagePatternsRequest()
    compliance_requirements: List[str] = []
    regions: List[str] = ["us-east-1"]


class MigrationTimelinePreference(str, Enum):
    FAST = "fast"
    BALANCED = "balanced"
    CONSERVATIVE = "conservative"


class ProviderType(str, Enum):
    aws = "aws"
    gcp = "gcp"
    azure = "azure"


class MigrationRequest(BaseModel):
    workload_id: UUID
    source_provider: ProviderType
    target_provider: ProviderType
    migration_timeline_preference: Optional[MigrationTimelinePreference] = None


class TCORequest(BaseModel):
    workload_id: UUID
    time_horizon_years: int = Field(3, ge=1, le=10)
    include_hidden_costs: bool = True


class ServicePricing(BaseModel):
    provider: str
    service_name: str
    service_category: str
    region: str
    pricing_unit: str
    price_per_unit: Decimal
    currency: str = "USD"
    effective_date: datetime
    pricing_details: Dict[str, Any] = {}


class CloudProvider(BaseModel):
    name: str
    provider_type: str
    supported_regions: List[str] = []
    supported_services: List[str] = []
    pricing_model: Optional[str] = None


class CloudService(BaseModel):
    name: str
    category: str
    description: Optional[str] = None
    pricing_units: List[str] = []
    regions: List[str] = []


class CostComparisonResponse(BaseModel):
    id: UUID
    workload_id: UUID
    comparison_date: datetime
    aws_monthly_cost: Decimal
    gcp_monthly_cost: Decimal
    azure_monthly_cost: Decimal
    aws_annual_cost: Decimal
    gcp_annual_cost: Decimal
    azure_annual_cost: Decimal
    cost_breakdown: Dict[str, Any] = {}
    recommendations: List[str] = []
    pricing_data_version: str = "live"
    lowest_cost_provider: str
    cost_difference_percentage: Dict[str, Any] = {}


class TCOAnalysisResponse(BaseModel):
    id: UUID
    workload_id: UUID
    analysis_date: datetime
    time_horizon_years: int
    aws_tco: Dict[str, Any]
    gcp_tco: Dict[str, Any]
    azure_tco: Dict[str, Any]
    hidden_costs: Dict[str, Any] = {}
    operational_costs: Dict[str, Any] = {}
    cost_projections: Dict[str, Any] = {}
    total_tco_comparison: Dict[str, Any] = {}
    recommended_provider: str


class MigrationAnalysisResponse(BaseModel):
    id: UUID
    workload_id: UUID
    source_provider: str
    target_provider: str
    analysis_date: datetime
    migration_cost: Decimal
    migration_timeline_days: int
    break_even_months: float
    cost_breakdown: Dict[str, Any] = {}
    risk_assessment: Dict[str, Any] = {}
    recommendations: List[str] = []
    monthly_savings: Decimal = Decimal("0")
    annual_savings: Decimal = Decimal("0")
    roi_percentage: float = 0.0


class ServiceEquivalencyResponse(BaseModel):
    source_provider: str
    source_service: str
    equivalents: List[Dict[str, Any]] = []


class WorkloadValidationResponse(BaseModel):
    is_valid: bool
    errors: List[Dict[str, Any]] = []
    warnings: List[str] = []
    estimated_monthly_cost_range: Optional[Dict[str, Any]] = None


class WorkloadListResponse(BaseModel):
    workloads: List[Dict[str, Any]]
    total_count: int
    page: int
    page_size: int


class ComparisonListResponse(BaseModel):
    comparisons: List[CostComparisonResponse]
    total_count: int
    page: int
    page_size: int

