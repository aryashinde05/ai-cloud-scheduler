from typing import Dict, Any, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.database.database import get_supabase
from app.core.auth import get_current_user
from app.services.startup_migration.models import User
from app.cloud.azure.azure_cost_analyzer import AzureCostAnalyzer, CostAnalysisReport

router = APIRouter(prefix="/api/v1/azure-cost", tags=["Azure Cost Analysis"])


# Request/Response Models

class AzureCredentialsRequest(BaseModel):
    """Request to configure Azure credentials using Service Principal"""

    tenant_id: str = Field(..., description="Azure Tenant ID")
    client_id: str = Field(..., description="Azure Client ID (App Registration)")
    client_secret: str = Field(..., description="Azure Client Secret")
    subscription_id: str = Field(..., description="Azure Subscription ID")

    class Config:
        schema_extra = {
            "example": {
                "tenant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                "client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                "client_secret": "xxxxxxxxxxxxxxxxxxxxxxxx",
                "subscription_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            }
        }


class CostAnalysisRequest(BaseModel):
    """Request for Azure cost analysis"""

    days_back: int = Field(default=30, ge=1, le=365, description="Number of days to analyze")
    include_recommendations: bool = Field(default=True, description="Include optimization recommendations")

    class Config:
        schema_extra = {
            "example": {
                "days_back": 30,
                "include_recommendations": True
            }
        }


class OptimizationOpportunityResponse(BaseModel):
    """Response model for optimization opportunity - matches AWS format"""

    service: str
    opportunity_type: str
    current_monthly_cost: float
    potential_monthly_savings: float
    confidence_level: str
    description: str
    action_required: str
    implementation_effort: str
    risk_level: str


class ServiceCostResponse(BaseModel):
    """Response model for service cost breakdown - matches AWS format"""

    service_name: str
    current_month_cost: float
    last_month_cost: float
    cost_trend: str
    percentage_of_total: float


class CostAnalysisResponse(BaseModel):
    """Response model for complete cost analysis - matches AWS format"""

    total_monthly_cost: float
    cost_trend: str
    top_cost_drivers: List[ServiceCostResponse]
    optimization_opportunities: List[OptimizationOpportunityResponse]
    potential_monthly_savings: float
    roi_analysis: Dict[str, Any]
    recommendations_summary: List[str]
    analysis_date: str


class ConnectionTestResponse(BaseModel):
    """Response model for Azure connection test"""

    status: str
    message: str
    permissions: List[str]


# Global analyzer instance cache
_analyzer_cache: Dict[str, AzureCostAnalyzer] = {}


def get_azure_analyzer(credentials: AzureCredentialsRequest) -> AzureCostAnalyzer:
    """Get or create Azure Cost Analyzer instance"""

    cache_key = f"{credentials.subscription_id}:{credentials.client_id}"

    if cache_key not in _analyzer_cache:
        _analyzer_cache[cache_key] = AzureCostAnalyzer(
            tenant_id=credentials.tenant_id,
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
            subscription_id=credentials.subscription_id
        )

    return _analyzer_cache[cache_key]


# API Endpoints

@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_azure_connection(
    credentials: AzureCredentialsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Test Azure connection and verify permissions for cost analysis.
    """

    try:
        analyzer = get_azure_analyzer(credentials)
        result = analyzer.test_connection()

        return ConnectionTestResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Azure connection test failed: {str(e)}"
        )


@router.post("/analyze", response_model=CostAnalysisResponse)
async def analyze_azure_costs(
    credentials: AzureCredentialsRequest,
    request: CostAnalysisRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Perform comprehensive Azure cost analysis and optimization recommendations.
    """

    try:
        analyzer = get_azure_analyzer(credentials)

        report = analyzer.analyze_costs(days_back=request.days_back)

        response = CostAnalysisResponse(
            total_monthly_cost=report.total_monthly_cost,
            cost_trend=report.cost_trend,
            top_cost_drivers=[
                ServiceCostResponse(
                    service_name=service.service_name,
                    current_month_cost=service.current_month_cost,
                    last_month_cost=service.last_month_cost,
                    cost_trend=service.cost_trend,
                    percentage_of_total=service.percentage_of_total
                )
                for service in report.top_cost_drivers
            ],
            optimization_opportunities=[
                OptimizationOpportunityResponse(
                    service=opp.service,
                    opportunity_type=opp.opportunity_type,
                    current_monthly_cost=opp.current_monthly_cost,
                    potential_monthly_savings=opp.potential_monthly_savings,
                    confidence_level=opp.confidence_level,
                    description=opp.description,
                    action_required=opp.action_required,
                    implementation_effort=opp.implementation_effort,
                    risk_level=opp.risk_level
                )
                for opp in report.optimization_opportunities
            ],
            potential_monthly_savings=report.potential_monthly_savings,
            roi_analysis=report.roi_analysis,
            recommendations_summary=report.recommendations_summary,
            analysis_date=datetime.now().isoformat()
        )

        return response

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Azure cost analysis failed: {str(e)}"
        )


@router.get("/service-breakdown", response_model=List[ServiceCostResponse])
async def get_azure_service_breakdown(
    credentials: AzureCredentialsRequest,
    days: int = 30,
    current_user: User = Depends(get_current_user)
):
    """Get detailed Azure cost breakdown by service"""

    try:
        analyzer = get_azure_analyzer(credentials)
        data = analyzer.get_service_breakdown(days)

        total = sum(d['cost'] for d in data)

        return [
            ServiceCostResponse(
                service_name=d['service'],
                current_month_cost=d['cost'],
                last_month_cost=d['cost'] * 0.9,
                cost_trend="stable",
                percentage_of_total=(d['cost'] / total * 100) if total > 0 else 0
            )
            for d in data
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cost-trends")
async def get_azure_cost_trends(
    credentials: AzureCredentialsRequest,
    days: int = 30,
    current_user: User = Depends(get_current_user)
):
    """Get daily Azure cost trends"""

    try:
        analyzer = get_azure_analyzer(credentials)
        return analyzer.get_cost_trends(days)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quick-wins", response_model=List[OptimizationOpportunityResponse])
async def get_azure_quick_wins(
    credentials: AzureCredentialsRequest,
    current_user: User = Depends(get_current_user)
):
    """Get Azure optimization quick wins"""

    try:
        analyzer = get_azure_analyzer(credentials)
        wins = analyzer.get_quick_wins()

        return [
            OptimizationOpportunityResponse(
                service=w.service,
                opportunity_type=w.opportunity_type,
                current_monthly_cost=w.current_monthly_cost,
                potential_monthly_savings=w.potential_monthly_savings,
                confidence_level=w.confidence_level,
                description=w.description,
                action_required=w.action_required,
                implementation_effort=w.implementation_effort,
                risk_level=w.risk_level
            )
            for w in wins
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/opportunities/{opportunity_type}", response_model=List[OptimizationOpportunityResponse])
async def get_azure_opportunities_by_type(
    opportunity_type: str,
    credentials: AzureCredentialsRequest,
    current_user: User = Depends(get_current_user)
):
    """Filter Azure optimization opportunities by type"""

    try:
        analyzer = get_azure_analyzer(credentials)
        all_recs = analyzer.get_optimization_recommendations()

        return [
            OptimizationOpportunityResponse(
                service=w.service,
                opportunity_type=w.opportunity_type,
                current_monthly_cost=w.current_monthly_cost,
                potential_monthly_savings=w.potential_monthly_savings,
                confidence_level=w.confidence_level,
                description=w.description,
                action_required=w.action_required,
                implementation_effort=w.implementation_effort,
                risk_level=w.risk_level
            )
            for w in all_recs
            if w.opportunity_type.lower() == opportunity_type.lower()
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))