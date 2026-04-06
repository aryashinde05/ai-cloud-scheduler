"""
Multi-Cloud Cost Comparison API Endpoints

FastAPI router implementation for multi-cloud cost comparison functionality.
Provides endpoints for workload cost comparison, TCO analysis, migration analysis,
and pricing data retrieval.
"""

from typing import Dict, List, Optional, Any
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from fastapi.responses import JSONResponse
import structlog

# Use the SQLAlchemy-backed auth used by the frontend (/auth/login).
# This avoids UUID-based user models and works out-of-the-box with SQLite demo DB.
from app.api.auth_endpoints import get_current_user as get_current_user_sql, UserDB
from app.api.multi_cloud_models import (
    # Request models
    WorkloadSpecRequest, MigrationRequest, TCORequest,
    
    # Response models
    CostComparisonResponse, TCOAnalysisResponse, MigrationAnalysisResponse,
    ServicePricing, CloudProvider, CloudService, ServiceEquivalencyResponse,
    WorkloadValidationResponse, WorkloadListResponse, ComparisonListResponse,
    ErrorResponse
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/multi-cloud", tags=["Multi-Cloud Cost Comparison"])


@router.post(
    "/compare",
    response_model=CostComparisonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Compare workload costs across cloud providers",
    description="Analyze and compare costs for a workload specification across AWS, GCP, and Azure"
)
async def compare_workload_costs(
    workload: WorkloadSpecRequest,
    current_user: UserDB = Depends(get_current_user_sql),
) -> CostComparisonResponse:
    """
    Compare workload costs across multiple cloud providers.
    
    This endpoint processes a workload specification and returns detailed cost
    comparisons across AWS, GCP, and Azure, including monthly and annual costs,
    cost breakdowns by service category, and optimization recommendations.
    """
    try:
        logger.info(
            "Starting workload cost comparison",
            user_id=current_user.id,
            workload_name=workload.name
        )
        
        # Demo-friendly implementation:
        # - Runs without Supabase
        # - Computes costs using `MultiCloudCostEngine`
        # - Does not require persistence (UUIDs are generated per request)
        from uuid import uuid4
        from app.services.multi_cloud_cost_engine import MultiCloudCostEngine
        from app.models.multi_cloud_models import (
            WorkloadSpec, ComputeSpec, StorageSpec, NetworkSpec, DatabaseSpec,
            StorageType, NetworkComponent, NetworkServiceType, CloudProvider
        )
        engine = MultiCloudCostEngine()
        workload_id = uuid4()
        comparison_id = uuid4()
        
        # Build domain models
        compute = ComputeSpec(
            vcpus=workload.compute_spec.cpu_cores,
            memory_gb=float(workload.compute_spec.memory_gb),
            operating_system=workload.compute_spec.operating_system,
            architecture=workload.compute_spec.architecture
        )
        storage_models = []
        if workload.storage_spec:
            storage_type = StorageType.OBJECT if workload.storage_spec.storage_type == 'object' else StorageType.BLOCK
            storage_models.append(StorageSpec(
                storage_type=storage_type,
                capacity_gb=workload.storage_spec.primary_storage_gb,
                iops_requirement=workload.storage_spec.iops_requirement,
                throughput_mbps=workload.storage_spec.throughput_mbps
            ))
        network = None
        if workload.network_spec:
            components = []
            if workload.network_spec.data_transfer_gb_monthly > 0:
                components.append(NetworkComponent(
                    service_type=NetworkServiceType.CDN if workload.network_spec.cdn_required else NetworkServiceType.API_GATEWAY
                ))
            network = NetworkSpec(components=components)
        
        db_spec = None
        if workload.database_spec:
            db_spec = DatabaseSpec(
                database_type=workload.database_spec.database_type,
                instance_class="standard",
                storage_gb=workload.database_spec.storage_gb,
                backup_retention_days=workload.database_spec.backup_retention_days
            )
            
        domain_workload = WorkloadSpec(
            name=workload.name,
            description=workload.description,
            compute=compute,
            storage=storage_models,
            network=network,
            database=db_spec,
            additional_services=[{"name": s} for s in workload.additional_services],
            usage_patterns=workload.usage_patterns.dict()
        )
        
        result = await engine.compare_workload_costs(domain_workload)
        comparison = result["comparison"]
        cost_diffs = result["cost_differences"]
        
        logger.info(
            "Workload cost comparison completed",
            user_id=current_user.id,
            comparison_id=str(comparison_id),
            lowest_cost_provider=comparison.lowest_cost_provider.value
        )
        
        aws_monthly = comparison.provider_costs.get(CloudProvider.AWS).total_monthly_cost if CloudProvider.AWS in comparison.provider_costs else Decimal('0')
        gcp_monthly = comparison.provider_costs.get(CloudProvider.GCP).total_monthly_cost if CloudProvider.GCP in comparison.provider_costs else Decimal('0')
        azure_monthly = comparison.provider_costs.get(CloudProvider.AZURE).total_monthly_cost if CloudProvider.AZURE in comparison.provider_costs else Decimal('0')

        cost_breakdown = {
            p.value: {
                "compute": sum(c.monthly_cost for c in comparison.provider_costs[p].service_costs if c.service_category == "compute"),
                "storage": sum(c.monthly_cost for c in comparison.provider_costs[p].service_costs if c.service_category == "storage"),
                "network": sum(c.monthly_cost for c in comparison.provider_costs[p].service_costs if c.service_category == "network"),
                "database": sum(c.monthly_cost for c in comparison.provider_costs[p].service_costs if c.service_category == "database"),
                "total": comparison.provider_costs[p].total_monthly_cost
            } for p in comparison.provider_costs
        }

        return CostComparisonResponse(
            id=comparison_id,
            workload_id=workload_id,
            comparison_date=comparison.comparison_date,
            aws_monthly_cost=aws_monthly,
            gcp_monthly_cost=gcp_monthly,
            azure_monthly_cost=azure_monthly,
            aws_annual_cost=aws_monthly * 12,
            gcp_annual_cost=gcp_monthly * 12,
            azure_annual_cost=azure_monthly * 12,
            cost_breakdown=cost_breakdown,
            recommendations=[r.description for r in result.get("recommendations", [])],
            pricing_data_version="live",
            lowest_cost_provider=comparison.lowest_cost_provider.value,
            cost_difference_percentage={p.value: cost_diffs.get(p, 0.0) for p in comparison.provider_costs},
        )
                
    except Exception as e:
        logger.error(
            "Failed to compare workload costs",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compare workload costs: {str(e)}"
        )


@router.post(
    "/tco",
    response_model=TCOAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Calculate Total Cost of Ownership (TCO)",
    description="Perform comprehensive TCO analysis including hidden costs and multi-year projections"
)
async def calculate_tco(
    tco_request: TCORequest,
    current_user: UserDB = Depends(get_current_user_sql),
) -> TCOAnalysisResponse:
    """
    Calculate Total Cost of Ownership for a workload across multiple cloud providers.
    
    Includes base infrastructure costs, hidden costs (support, compliance, operational overhead),
    and multi-year cost projections with discount rate calculations.
    """
    try:
        logger.info(
            "Starting TCO analysis",
            user_id=current_user.id,
            workload_id=tco_request.workload_id,
            time_horizon=tco_request.time_horizon_years
        )
        
        # Demo-friendly: because persistence may be disabled, this endpoint expects
        # the frontend to call `/multi-cloud/compare` first and keep the workload
        # spec client-side. If a workload_id is unknown, return a clear 400.
        # (A persistent store can be added later without changing the API shape.)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TCO demo mode: call /multi-cloud/compare and compute TCO client-side (persistence disabled)."
        )
        from app.services.multi_cloud_cost_engine import MultiCloudCostEngine
        from app.models.multi_cloud_models import (
            WorkloadSpec, ComputeSpec, StorageSpec, NetworkSpec, DatabaseSpec, CloudProvider
        )
        
        compute = ComputeSpec(
            vcpus=workload.compute_spec.get('cpu_cores', 2) if workload.compute_spec else 2,
            memory_gb=float(workload.compute_spec.get('memory_gb', 4.0)) if workload.compute_spec else 4.0
        )
        domain_workload = WorkloadSpec(
            name=workload.name,
            compute=compute,
            usage_patterns=workload.usage_patterns or {}
        )
        
        engine = MultiCloudCostEngine()
        tco_analysis = await engine.calculate_tco(
            domain_workload, 
            years=tco_request.time_horizon_years,
            include_hidden_costs=tco_request.include_hidden_costs
        )
        
        # Map the domain tco result into standard payload
        def get_tco_dict(p: CloudProvider):
            comps = tco_analysis.provider_tco.get(p, [])
            return {
                "base_infrastructure": sum(c.total_cost for c in comps if "Base" in c.component_name),
                "support_costs": sum(c.total_cost for c in comps if "Hidden" in c.component_name),
                "operational_overhead": sum(c.total_cost for c in comps if "Operational" in c.component_name),
                "total": tco_analysis.total_tco_by_provider.get(p, Decimal("0"))
            }

        tco_data = {
            "workload_id": tco_request.workload_id,
            "analysis_date": datetime.utcnow(),
            "time_horizon_years": tco_request.time_horizon_years,
            "aws_tco": get_tco_dict(CloudProvider.AWS),
            "gcp_tco": get_tco_dict(CloudProvider.GCP),
            "azure_tco": get_tco_dict(CloudProvider.AZURE),
            "hidden_costs": {},
            "operational_costs": {},
            "cost_projections": {},
            "total_tco_comparison": {
                p.value: tco_analysis.total_tco_by_provider.get(p, Decimal("0")) for p in [CloudProvider.AWS, CloudProvider.GCP, CloudProvider.AZURE]
            },
            "recommended_provider": tco_analysis.lowest_tco_provider.value if getattr(tco_analysis, 'lowest_tco_provider', None) else "aws"
        }
        
        # Save TCO analysis
        saved_analysis = await repository.save_tco_analysis(tco_data)
        
        logger.info(
            "TCO analysis completed",
            user_id=current_user.id,
            analysis_id=saved_analysis.id,
            recommended_provider=tco_data["recommended_provider"]
        )
        
        return TCOAnalysisResponse(
            id=saved_analysis.id,
            workload_id=saved_analysis.workload_id,
            analysis_date=saved_analysis.analysis_date,
            time_horizon_years=saved_analysis.time_horizon_years,
            aws_tco=saved_analysis.aws_tco,
            gcp_tco=saved_analysis.gcp_tco,
            azure_tco=saved_analysis.azure_tco,
            hidden_costs=saved_analysis.hidden_costs,
            operational_costs=saved_analysis.operational_costs,
            cost_projections=saved_analysis.cost_projections,
            total_tco_comparison=saved_analysis.total_tco_comparison,
            recommended_provider=saved_analysis.recommended_provider
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to calculate TCO",
            user_id=current_user.id,
            workload_id=tco_request.workload_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate TCO: {str(e)}"
        )


@router.post(
    "/migration",
    response_model=MigrationAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Analyze migration costs and ROI",
    description="Analyze migration costs, timeline, and ROI for moving workloads between cloud providers"
)
async def analyze_migration_costs(
    migration_request: MigrationRequest,
    current_user: UserDB = Depends(get_current_user_sql),
) -> MigrationAnalysisResponse:
    """
    Analyze migration costs and return on investment for moving workloads between providers.
    
    Includes migration timeline estimation, cost breakdown, risk assessment,
    and break-even analysis.
    """
    try:
        logger.info(
            "Starting migration analysis",
            user_id=current_user.id,
            workload_id=migration_request.workload_id,
            source_provider=migration_request.source_provider,
            target_provider=migration_request.target_provider
        )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Migration demo mode: run /multi-cloud/compare and present migration estimates from the compare output (persistence disabled)."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to analyze migration costs",
            user_id=current_user.id,
            workload_id=migration_request.workload_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze migration costs: {str(e)}"
        )


@router.get(
    "/pricing/{provider}/{service}",
    response_model=ServicePricing,
    summary="Get service pricing information",
    description="Retrieve current pricing information for a specific service from a cloud provider"
)
async def get_service_pricing(
    provider: str = Path(..., description="Cloud provider (aws, gcp, azure)"),
    service: str = Path(..., description="Service name"),
    region: Optional[str] = Query(None, description="Region filter"),
    current_user: UserDB = Depends(get_current_user_sql),
) -> ServicePricing:
    """
    Get current pricing information for a specific cloud service.
    
    Returns the most recent pricing data for the specified provider and service,
    optionally filtered by region.
    """
    try:
        logger.info(
            "Retrieving service pricing",
            user_id=current_user.id,
            provider=provider,
            service=service,
            region=region
        )
        
        # Validate provider
        valid_providers = ["aws", "gcp", "azure"]
        if provider.lower() not in valid_providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider. Must be one of: {', '.join(valid_providers)}"
            )
        
        # TODO: Implement actual pricing retrieval logic
        # This is a placeholder implementation
        
        # Mock pricing data
        pricing_data = {
            "provider": provider.lower(),
            "service_name": service,
            "service_category": "compute",  # This would be determined dynamically
            "region": region or "us-east-1",
            "pricing_unit": "hour",
            "price_per_unit": Decimal("0.096"),
            "currency": "USD",
            "effective_date": datetime.utcnow(),
            "pricing_details": {
                "instance_type": "m5.large",
                "vcpus": 2,
                "memory_gb": 8,
                "storage_type": "EBS",
                "network_performance": "Up to 10 Gbps"
            }
        }
        
        logger.info(
            "Service pricing retrieved",
            user_id=current_user.id,
            provider=provider,
            service=service,
            price=pricing_data["price_per_unit"]
        )
        
        return ServicePricing(**pricing_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to retrieve service pricing",
            user_id=current_user.id,
            provider=provider,
            service=service,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve service pricing: {str(e)}"
        )


@router.get(
    "/providers",
    response_model=List[CloudProvider],
    summary="Get supported cloud providers",
    description="Retrieve list of supported cloud providers and their capabilities"
)
async def get_supported_providers(
    current_user: UserDB = Depends(get_current_user_sql)
) -> List[CloudProvider]:
    """
    Get list of supported cloud providers with their capabilities and regions.
    """
    try:
        logger.info("Retrieving supported providers", user_id=current_user.id)
        
        # Static provider information
        providers = [
            CloudProvider(
                name="Amazon Web Services",
                provider_type="aws",
                supported_regions=[
                    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
                    "eu-west-1", "eu-west-2", "eu-central-1",
                    "ap-southeast-1", "ap-southeast-2", "ap-northeast-1"
                ],
                supported_services=[
                    "EC2", "RDS", "S3", "Lambda", "ELB", "CloudFront",
                    "EBS", "VPC", "Route53", "CloudWatch"
                ],
                pricing_model='{"marketShare": 33, "reliability": 99.99, "avgCost": "Medium"}'
            ),
            CloudProvider(
                name="Google Cloud Platform",
                provider_type="gcp",
                supported_regions=[
                    "us-central1", "us-east1", "us-west1", "us-west2",
                    "europe-west1", "europe-west2", "europe-west3",
                    "asia-southeast1", "asia-northeast1", "asia-east1"
                ],
                supported_services=[
                    "Compute Engine", "Cloud SQL", "Cloud Storage", "Cloud Functions",
                    "Cloud Load Balancing", "Cloud CDN", "Persistent Disk",
                    "VPC", "Cloud DNS", "Cloud Monitoring"
                ],
                pricing_model='{"marketShare": 10, "reliability": 99.95, "avgCost": "Low"}'
            ),
            CloudProvider(
                name="Microsoft Azure",
                provider_type="azure",
                supported_regions=[
                    "East US", "East US 2", "West US", "West US 2",
                    "West Europe", "North Europe", "UK South",
                    "Southeast Asia", "East Asia", "Japan East"
                ],
                supported_services=[
                    "Virtual Machines", "Azure SQL Database", "Blob Storage",
                    "Azure Functions", "Load Balancer", "Azure CDN",
                    "Managed Disks", "Virtual Network", "Azure DNS", "Azure Monitor"
                ],
                pricing_model='{"marketShare": 21, "reliability": 99.99, "avgCost": "Medium-High"}'
            )
        ]
        
        logger.info(
            "Supported providers retrieved",
            user_id=current_user.id,
            provider_count=len(providers)
        )
        
        return providers
        
    except Exception as e:
        logger.error(
            "Failed to retrieve supported providers",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve supported providers: {str(e)}"
        )


@router.get(
    "/services/{provider}",
    response_model=List[CloudService],
    summary="Get provider services",
    description="Retrieve list of services available from a specific cloud provider"
)
async def get_provider_services(
    provider: str = Path(..., description="Cloud provider (aws, gcp, azure)"),
    category: Optional[str] = Query(None, description="Service category filter"),
    current_user: UserDB = Depends(get_current_user_sql)
) -> List[CloudService]:
    """
    Get list of services available from a specific cloud provider.
    
    Optionally filter by service category (compute, storage, database, etc.).
    """
    try:
        logger.info(
            "Retrieving provider services",
            user_id=current_user.id,
            provider=provider,
            category=category
        )
        
        # Validate provider
        valid_providers = ["aws", "gcp", "azure"]
        if provider.lower() not in valid_providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider. Must be one of: {', '.join(valid_providers)}"
            )
        
        # Mock service data by provider
        services_by_provider = {
            "aws": [
                CloudService(
                    name="EC2",
                    category="compute",
                    description="Elastic Compute Cloud - Virtual servers in the cloud",
                    pricing_units=["hour", "second"],
                    regions=["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
                ),
                CloudService(
                    name="RDS",
                    category="database",
                    description="Relational Database Service - Managed database service",
                    pricing_units=["hour", "month"],
                    regions=["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
                ),
                CloudService(
                    name="S3",
                    category="storage",
                    description="Simple Storage Service - Object storage service",
                    pricing_units=["GB-month", "request"],
                    regions=["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
                )
            ],
            "gcp": [
                CloudService(
                    name="Compute Engine",
                    category="compute",
                    description="Virtual machines running in Google's data centers",
                    pricing_units=["hour", "second"],
                    regions=["us-central1", "us-east1", "europe-west1", "asia-southeast1"]
                ),
                CloudService(
                    name="Cloud SQL",
                    category="database",
                    description="Fully managed relational database service",
                    pricing_units=["hour", "month"],
                    regions=["us-central1", "us-east1", "europe-west1", "asia-southeast1"]
                ),
                CloudService(
                    name="Cloud Storage",
                    category="storage",
                    description="Object storage with global edge-caching",
                    pricing_units=["GB-month", "operation"],
                    regions=["us-central1", "us-east1", "europe-west1", "asia-southeast1"]
                )
            ],
            "azure": [
                CloudService(
                    name="Virtual Machines",
                    category="compute",
                    description="On-demand, scalable computing resources",
                    pricing_units=["hour", "month"],
                    regions=["East US", "West US 2", "West Europe", "Southeast Asia"]
                ),
                CloudService(
                    name="Azure SQL Database",
                    category="database",
                    description="Managed SQL database service",
                    pricing_units=["hour", "DTU", "vCore"],
                    regions=["East US", "West US 2", "West Europe", "Southeast Asia"]
                ),
                CloudService(
                    name="Blob Storage",
                    category="storage",
                    description="Massively scalable object storage",
                    pricing_units=["GB-month", "transaction"],
                    regions=["East US", "West US 2", "West Europe", "Southeast Asia"]
                )
            ]
        }
        
        services = services_by_provider.get(provider.lower(), [])
        
        # Filter by category if specified
        if category:
            services = [s for s in services if s.category.lower() == category.lower()]
        
        logger.info(
            "Provider services retrieved",
            user_id=current_user.id,
            provider=provider,
            service_count=len(services)
        )
        
        return services
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to retrieve provider services",
            user_id=current_user.id,
            provider=provider,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve provider services: {str(e)}"
        )


@router.get(
    "/workloads",
    response_model=WorkloadListResponse,
    summary="Get user workload specifications",
    description="Retrieve workload specifications created by the current user"
)
async def get_workload_specifications(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: UserDB = Depends(get_current_user_sql),
) -> WorkloadListResponse:
    """
    Get paginated list of workload specifications for the current user.
    """
    try:
        logger.info(
            "Retrieving user workload specifications",
            user_id=current_user.id,
            page=page,
            page_size=page_size
        )
        
        # Demo mode: no persistence; return empty list (frontend can store its own history).
        return WorkloadListResponse(workloads=[], total_count=0, page=page, page_size=page_size)
        
    except Exception as e:
        logger.error(
            "Failed to retrieve workload specifications",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve workload specifications: {str(e)}"
        )


@router.get(
    "/comparisons/{workload_id}",
    response_model=ComparisonListResponse,
    summary="Get cost comparisons for workload",
    description="Retrieve cost comparison history for a specific workload"
)
async def get_workload_comparisons(
    workload_id: UUID = Path(..., description="Workload specification ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=50, description="Items per page"),
    current_user: UserDB = Depends(get_current_user_sql),
) -> ComparisonListResponse:
    """
    Get paginated list of cost comparisons for a specific workload.
    """
    try:
        logger.info(
            "Retrieving workload cost comparisons",
            user_id=current_user.id,
            workload_id=workload_id,
            page=page,
            page_size=page_size
        )
        
        return ComparisonListResponse(comparisons=[], total_count=0, page=page, page_size=page_size)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to retrieve workload cost comparisons",
            user_id=current_user.id,
            workload_id=workload_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve workload cost comparisons: {str(e)}"
        )


@router.post(
    "/validate",
    response_model=WorkloadValidationResponse,
    summary="Validate workload specification",
    description="Validate a workload specification and provide cost estimates"
)
async def validate_workload_specification(
    workload: WorkloadSpecRequest,
    current_user: UserDB = Depends(get_current_user_sql)
) -> WorkloadValidationResponse:
    """
    Validate a workload specification and provide preliminary cost estimates.
    
    This endpoint validates the workload configuration without saving it
    and provides estimated cost ranges for planning purposes.
    """
    try:
        logger.info(
            "Validating workload specification",
            user_id=current_user.id,
            workload_name=workload.name
        )
        
        errors = []
        warnings = []
        
        # Basic validation
        if workload.compute_spec.cpu_cores < 1:
            errors.append({"message": "CPU cores must be at least 1", "field": "compute_spec.cpu_cores"})
        
        if workload.compute_spec.memory_gb < 1:
            errors.append({"message": "Memory must be at least 1 GB", "field": "compute_spec.memory_gb"})
        
        if workload.storage_spec.primary_storage_gb < 1:
            errors.append({"message": "Primary storage must be at least 1 GB", "field": "storage_spec.primary_storage_gb"})
        
        # Warnings for optimization
        if workload.compute_spec.cpu_cores > 64:
            warnings.append("High CPU core count may be expensive - consider distributed architecture")
        
        if workload.storage_spec.primary_storage_gb > 10000:
            warnings.append("Large storage requirements - consider tiered storage strategy")
        
        if len(workload.regions) > 3:
            warnings.append("Multi-region deployment increases complexity and costs")
        
        # Calculate estimated cost range
        estimated_monthly_cost_range = None
        if not errors:
            base_compute = workload.compute_spec.cpu_cores * 50 + workload.compute_spec.memory_gb * 5
            base_storage = workload.storage_spec.primary_storage_gb * 0.1
            base_network = workload.network_spec.data_transfer_gb_monthly * 0.05
            
            base_cost = Decimal(str(base_compute + base_storage + base_network))
            
            estimated_monthly_cost_range = {
                "min_cost": base_cost * Decimal("0.8"),  # 20% lower
                "max_cost": base_cost * Decimal("1.3"),  # 30% higher
                "currency": "USD"
            }
        
        is_valid = len(errors) == 0
        
        logger.info(
            "Workload specification validation completed",
            user_id=current_user.id,
            workload_name=workload.name,
            is_valid=is_valid,
            error_count=len(errors),
            warning_count=len(warnings)
        )
        
        return WorkloadValidationResponse(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            estimated_monthly_cost_range=estimated_monthly_cost_range
        )
        
    except Exception as e:
        logger.error(
            "Failed to validate workload specification",
            user_id=current_user.id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate workload specification: {str(e)}"
        )


# Admin endpoints for pricing update management

@router.get(
    "/admin/pricing-updates/status",
    response_model=Dict[str, Any],
    summary="Get pricing update status",
    description="Get the status of automated pricing updates for all providers"
)
async def get_pricing_update_status(
    current_user: UserDB = Depends(get_current_user_sql),
):
    """
    Get pricing update status for admin dashboard.
    
    Returns information about the last pricing updates, success rates,
    and any issues with pricing data synchronization.
    """
    try:
        # Check if user has admin privileges (simplified check)
        if not getattr(current_user, 'is_admin', False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        logger.info("Getting pricing update status", user_id=current_user.id)
        
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Pricing update status requires a persistent pricing store (disabled in demo mode)."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get pricing update status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pricing update status: {str(e)}"
        )


@router.post(
    "/admin/pricing-updates/trigger",
    response_model=Dict[str, Any],
    summary="Trigger pricing update",
    description="Manually trigger pricing updates for specified providers"
)
async def trigger_pricing_update(
    providers: Optional[List[str]] = Query(None, description="Providers to update (aws, gcp, azure)"),
    current_user: UserDB = Depends(get_current_user_sql)
):
    """
    Manually trigger pricing updates for specified providers.
    
    Useful for testing or when immediate pricing updates are needed.
    """
    try:
        # Check if user has admin privileges
        if not getattr(current_user, 'is_admin', False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Import Celery tasks
        from tasks.pricing_update_tasks import (
            update_aws_pricing, update_gcp_pricing, update_azure_pricing,
            update_all_provider_pricing
        )
        
        logger.info("Triggering pricing update", user_id=current_user.id, providers=providers)
        
        # Default to all providers if none specified
        if not providers:
            providers = ['aws', 'gcp', 'azure']
        
        # Validate providers
        valid_providers = {'aws', 'gcp', 'azure'}
        invalid_providers = set(providers) - valid_providers
        if invalid_providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid providers: {list(invalid_providers)}"
            )
        
        task_results = {}
        
        # Trigger updates for each provider
        for provider in providers:
            try:
                if provider == 'aws':
                    task = update_aws_pricing.delay()
                elif provider == 'gcp':
                    task = update_gcp_pricing.delay()
                elif provider == 'azure':
                    task = update_azure_pricing.delay()
                
                task_results[provider] = {
                    'task_id': task.id,
                    'status': 'queued',
                    'provider': provider
                }
                
            except Exception as e:
                logger.error(f"Failed to trigger {provider} pricing update", error=str(e))
                task_results[provider] = {
                    'status': 'error',
                    'error': str(e),
                    'provider': provider
                }
        
        return {
            'message': f"Pricing updates triggered for {len(providers)} providers",
            'providers': providers,
            'tasks': task_results,
            'triggered_at': datetime.utcnow().isoformat(),
            'triggered_by': current_user.id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to trigger pricing update", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger pricing update: {str(e)}"
        )


@router.get(
    "/admin/pricing-updates/history",
    response_model=Dict[str, Any],
    summary="Get pricing update history",
    description="Get history of pricing updates and their results"
)
async def get_pricing_update_history(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    days: int = Query(7, description="Number of days to look back"),
    current_user: UserDB = Depends(get_current_user_sql),
):
    """
    Get pricing update history for monitoring and troubleshooting.
    """
    try:
        # Check if user has admin privileges
        if not getattr(current_user, 'is_admin', False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        logger.info("Getting pricing update history", user_id=current_user.id, provider=provider, days=days)
        
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Pricing update history requires a persistent pricing store (disabled in demo mode)."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get pricing update history", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pricing update history: {str(e)}"
        )

# Performance Monitoring Endpoints

@router.get(
    "/performance/dashboard",
    response_model=Dict[str, Any],
    summary="Get performance dashboard data",
    description="Retrieve comprehensive performance metrics for the multi-cloud cost engine"
)
async def get_performance_dashboard(
    hours: int = Query(1, ge=1, le=168, description="Hours of data to analyze (1-168)"),
    current_user: UserDB = Depends(get_current_user_sql)
) -> Dict[str, Any]:
    """
    Get performance dashboard data including metrics, alerts, and system health.
    
    Returns comprehensive performance data for monitoring and analysis.
    """
    try:
        # Import performance metrics (lazy import to avoid circular dependencies)
        from monitoring.performance_metrics import PerformanceMetrics
        from app.utils.cache_manager import CacheManager
        
        # Initialize performance metrics (in production, this would be a singleton)
        metrics = PerformanceMetrics()
        
        # Get dashboard data
        dashboard_data = metrics.get_performance_dashboard_data()
        
        # Add cache statistics if available
        try:
            cache_manager = CacheManager()
            await cache_manager.initialize()
            cache_stats = cache_manager.get_cache_statistics()
            
            dashboard_data['cache_statistics'] = {
                'hit_rate': cache_stats.hit_rate,
                'total_requests': cache_stats.total_requests,
                'cache_hits': cache_stats.cache_hits,
                'cache_misses': cache_stats.cache_misses,
                'memory_usage_mb': cache_stats.memory_usage_mb,
                'redis_usage_mb': cache_stats.redis_usage_mb
            }
        except Exception as e:
            logger.warning("Failed to get cache statistics", error=str(e))
            dashboard_data['cache_statistics'] = None
        
        logger.info(
            "Performance dashboard data retrieved",
            user_id=current_user.id,
            hours=hours
        )
        
        return dashboard_data
        
    except Exception as e:
        logger.error("Failed to get performance dashboard", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve performance dashboard: {str(e)}"
        )


@router.get(
    "/performance/metrics/{metric_name}",
    response_model=Dict[str, Any],
    summary="Get specific metric data",
    description="Retrieve detailed data for a specific performance metric"
)
async def get_metric_data(
    metric_name: str = Path(..., description="Name of the metric to retrieve"),
    hours: int = Query(1, ge=1, le=168, description="Hours of data to analyze"),
    current_user: UserDB = Depends(get_current_user_sql)
) -> Dict[str, Any]:
    """
    Get detailed data for a specific performance metric.
    
    Available metrics:
    - api_response_time
    - cache_hit_rate
    - comparison_processing_time
    - parallel_efficiency
    - database_query_time
    - memory_usage
    - error_rate
    - throughput
    """
    try:
        from monitoring.performance_metrics import PerformanceMetrics
        
        metrics = PerformanceMetrics()
        
        # Get metric summary
        summary = metrics.get_metric_summary(metric_name, hours)
        
        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Metric '{metric_name}' not found or has no data"
            )
        
        # Get raw metric points for charting
        from datetime import timedelta
        since = datetime.utcnow() - timedelta(hours=hours)
        
        if metric_name in metrics.metrics:
            points = metrics.metrics[metric_name].get_points(since=since)
            chart_data = [
                {
                    'timestamp': point.timestamp.isoformat(),
                    'value': point.value,
                    'labels': point.labels
                }
                for point in points[-100:]  # Limit to last 100 points for performance
            ]
        else:
            chart_data = []
        
        result = {
            'metric_name': metric_name,
            'summary': summary.to_dict(),
            'chart_data': chart_data,
            'data_points': len(chart_data)
        }
        
        logger.info(
            "Metric data retrieved",
            user_id=current_user.id,
            metric_name=metric_name,
            hours=hours,
            data_points=len(chart_data)
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get metric data", metric_name=metric_name, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve metric data: {str(e)}"
        )


@router.get(
    "/performance/cache/stats",
    response_model=Dict[str, Any],
    summary="Get cache performance statistics",
    description="Retrieve detailed cache performance statistics and hit rates"
)
async def get_cache_statistics(
    current_user: UserDB = Depends(get_current_user_sql)
) -> Dict[str, Any]:
    """
    Get comprehensive cache performance statistics.
    
    Returns cache hit rates, memory usage, and performance metrics.
    """
    try:
        from app.utils.cache_manager import CacheManager
        
        cache_manager = CacheManager()
        await cache_manager.initialize()
        
        # Get cache statistics
        stats = cache_manager.get_cache_statistics()
        
        # Get memory cache stats
        memory_stats = cache_manager.memory_cache.get_stats()
        
        # Get Redis stats if available
        redis_stats = {}
        if cache_manager.redis_cache and cache_manager.redis_cache.connected:
            redis_stats = await cache_manager.redis_cache.get_stats()
        
        result = {
            'overall_stats': {
                'total_requests': stats.total_requests,
                'cache_hits': stats.cache_hits,
                'cache_misses': stats.cache_misses,
                'hit_rate': stats.hit_rate,
                'avg_response_time_ms': stats.avg_response_time_ms,
                'evictions': stats.evictions,
                'invalidations': stats.invalidations,
                'last_updated': stats.last_updated.isoformat() if stats.last_updated else None
            },
            'memory_cache': {
                'entry_count': memory_stats['entry_count'],
                'size_mb': memory_stats['size_mb'],
                'max_entries': memory_stats['max_entries'],
                'max_size_mb': memory_stats['max_size_mb'],
                'utilization_percent': (memory_stats['size_mb'] / memory_stats['max_size_mb']) * 100
            },
            'redis_cache': redis_stats if redis_stats else {'connected': False}
        }
        
        logger.info(
            "Cache statistics retrieved",
            user_id=current_user.id,
            hit_rate=stats.hit_rate,
            total_requests=stats.total_requests
        )
        
        return result
        
    except Exception as e:
        logger.error("Failed to get cache statistics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve cache statistics: {str(e)}"
        )


@router.post(
    "/performance/cache/warm",
    response_model=Dict[str, Any],
    summary="Warm cache with common workloads",
    description="Pre-populate cache with frequently accessed workload comparisons"
)
async def warm_cache(
    workload_ids: List[UUID] = Query(..., description="List of workload IDs to warm cache with"),
    current_user: UserDB = Depends(get_current_user_sql),
) -> Dict[str, Any]:
    """
    Warm cache by pre-computing cost comparisons for specified workloads.
    
    This endpoint helps improve performance by pre-loading frequently accessed data.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Cache warming requires persistent workload storage (disabled in demo mode)."
    )


@router.delete(
    "/performance/cache/clear",
    response_model=Dict[str, Any],
    summary="Clear cache data",
    description="Clear all cached data to force fresh calculations"
)
async def clear_cache(
    cache_type: Optional[str] = Query(None, description="Cache type to clear (memory, redis, or all)"),
    current_user: UserDB = Depends(get_current_user_sql)
) -> Dict[str, Any]:
    """
    Clear cache data to force fresh calculations.
    
    Use with caution as this will impact performance until cache is rebuilt.
    """
    try:
        from app.utils.cache_manager import CacheManager
        
        cache_manager = CacheManager()
        await cache_manager.initialize()
        
        if cache_type == "memory" or cache_type is None:
            await cache_manager.memory_cache.clear()
        
        if cache_type == "redis" or cache_type is None:
            if cache_manager.redis_cache and cache_manager.redis_cache.connected:
                await cache_manager.redis_cache.clear()
        
        result = {
            'cleared_cache_type': cache_type or "all",
            'success': True,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(
            "Cache cleared",
            user_id=current_user.id,
            cache_type=cache_type or "all"
        )
        
        return result
        
    except Exception as e:
        logger.error("Failed to clear cache", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(e)}"
        )


@router.get(
    "/performance/system/health",
    response_model=Dict[str, Any],
    summary="Get system health status",
    description="Retrieve overall system health and performance status"
)
async def get_system_health(
    current_user: UserDB = Depends(get_current_user_sql)
) -> Dict[str, Any]:
    """
    Get comprehensive system health status including performance metrics,
    cache status, and overall system health score.
    """
    try:
        from monitoring.performance_metrics import PerformanceMetrics
        from app.utils.cache_manager import CacheManager
        
        # Get performance metrics
        metrics = PerformanceMetrics()
        dashboard_data = metrics.get_performance_dashboard_data()
        
        # Get cache health
        cache_manager = CacheManager()
        await cache_manager.initialize()
        cache_stats = cache_manager.get_cache_statistics()
        
        # Calculate overall health
        health_score = dashboard_data.get('system_health', {}).get('score', 100)
        health_status = dashboard_data.get('system_health', {}).get('status', 'unknown')
        
        # Check individual components
        components = {
            'api_performance': {
                'status': 'healthy' if health_score > 80 else 'degraded',
                'metrics': dashboard_data.get('metrics_summary', {}).get('api_response_time', {})
            },
            'cache_performance': {
                'status': 'healthy' if cache_stats.hit_rate > 0.7 else 'degraded',
                'hit_rate': cache_stats.hit_rate,
                'total_requests': cache_stats.total_requests
            },
            'database_performance': {
                'status': 'healthy',  # Would check actual DB metrics in production
                'metrics': dashboard_data.get('metrics_summary', {}).get('database_query_time', {})
            }
        }
        
        result = {
            'overall_health': {
                'score': health_score,
                'status': health_status,
                'timestamp': datetime.utcnow().isoformat()
            },
            'components': components,
            'uptime_hours': dashboard_data.get('uptime_hours', 0),
            'recent_alerts': dashboard_data.get('recent_alerts', [])
        }
        
        logger.info(
            "System health retrieved",
            user_id=current_user.id,
            health_score=health_score,
            health_status=health_status
        )
        
        return result
        
    except Exception as e:
        logger.error("Failed to get system health", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve system health: {str(e)}"
        )
