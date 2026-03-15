"""
AWS Cost Analysis API Endpoints

Provides REST API endpoints for real AWS cost analysis and optimization recommendations.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from supabase import Client

from app.database.database import get_supabase
from app.core.auth import get_current_user
from app.services.startup_migration.models import User
from app.aws.aws_cost_analyzer import AWSCostAnalyzer, CostAnalysisReport

router = APIRouter(prefix="/api/v1/aws-cost", tags=["AWS Cost Analysis"])

# Request/Response Models

class AWSCredentialsRequest(BaseModel):
    """Request to configure AWS credentials"""
    aws_access_key_id: str = Field(..., description="AWS Access Key ID")
    aws_secret_access_key: str = Field(..., description="AWS Secret Access Key")
    region: str = Field(default="us-east-1", description="AWS Region")
    
    class Config:
        schema_extra = {
            "example": {
                "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
                "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                "region": "us-east-1"
            }
        }

class CostAnalysisRequest(BaseModel):
    """Request for cost analysis"""
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
    """Response model for optimization opportunity"""
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
    """Response model for service cost breakdown"""
    service_name: str
    current_month_cost: float
    last_month_cost: float
    cost_trend: str
    percentage_of_total: float

class CostAnalysisResponse(BaseModel):
    """Response model for complete cost analysis"""
    total_monthly_cost: float
    cost_trend: str
    top_cost_drivers: List[ServiceCostResponse]
    optimization_opportunities: List[OptimizationOpportunityResponse]
    potential_monthly_savings: float
    roi_analysis: Dict[str, Any]
    recommendations_summary: List[str]
    analysis_date: str

class ConnectionTestResponse(BaseModel):
    """Response model for AWS connection test"""
    status: str
    message: str
    permissions: List[str]

# Global analyzer instance (in production, use dependency injection)
_analyzer_cache: Dict[str, AWSCostAnalyzer] = {}

def get_aws_analyzer(credentials: AWSCredentialsRequest) -> AWSCostAnalyzer:
    """Get or create AWS Cost Analyzer instance"""
    cache_key = f"{credentials.aws_access_key_id}:{credentials.region}"
    
    if cache_key not in _analyzer_cache:
        _analyzer_cache[cache_key] = AWSCostAnalyzer(
            aws_access_key_id=credentials.aws_access_key_id,
            aws_secret_access_key=credentials.aws_secret_access_key,
            region=credentials.region
        )
    
    return _analyzer_cache[cache_key]

# API Endpoints

@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_aws_connection(
    credentials: AWSCredentialsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Test AWS connection and verify permissions for cost analysis.
    
    This endpoint validates AWS credentials and checks if the user has
    the necessary permissions to access Cost Explorer and other required services.
    """
    try:
        analyzer = get_aws_analyzer(credentials)
        result = analyzer.test_connection()
        
        return ConnectionTestResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"AWS connection test failed: {str(e)}"
        )

@router.post("/analyze", response_model=CostAnalysisResponse)
async def analyze_aws_costs(
    credentials: AWSCredentialsRequest,
    request: CostAnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Client = Depends(get_supabase)
):
    """
    Perform comprehensive AWS cost analysis and optimization recommendations.
    
    This endpoint analyzes your AWS spending patterns and identifies specific
    opportunities to reduce costs through rightsizing, removing unused resources,
    purchasing Reserved Instances, and optimizing storage.
    """
    try:
        analyzer = get_aws_analyzer(credentials)
        
        # Perform cost analysis
        report = analyzer.analyze_costs(days_back=request.days_back)
        
        # Convert to response format
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
        
        # Store analysis results in background (for historical tracking)
        background_tasks.add_task(
            _store_analysis_results,
            user_id=current_user.id,
            analysis_data=response.dict(),
            db=db
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cost analysis failed: {str(e)}"
        )

@router.get("/opportunities/{opportunity_type}")
async def get_opportunities_by_type(
    opportunity_type: str,
    credentials: AWSCredentialsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed optimization opportunities by type.
    
    Supported types: rightsizing, unused_resources, reserved_instances, storage_optimization
    """
    try:
        analyzer = get_aws_analyzer(credentials)
        report = analyzer.analyze_costs()
        
        # Filter opportunities by type
        filtered_opportunities = [
            opp for opp in report.optimization_opportunities
            if opp.opportunity_type == opportunity_type
        ]
        
        return {
            'opportunity_type': opportunity_type,
            'count': len(filtered_opportunities),
            'total_potential_savings': sum(opp.potential_monthly_savings for opp in filtered_opportunities),
            'opportunities': [
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
                for opp in filtered_opportunities
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get opportunities: {str(e)}"
        )

@router.get("/cost-trends")
async def get_cost_trends(
    credentials: AWSCredentialsRequest,
    days: int = 30,
    current_user: User = Depends(get_current_user)
):
    """
    Get cost trends over time for visualization.
    """
    try:
        analyzer = get_aws_analyzer(credentials)
        
        # Get daily cost data
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        cost_data = analyzer._get_cost_data(days)
        
        # Format for frontend charting
        daily_costs = []
        for result in cost_data['ResultsByTime']:
            date = result['TimePeriod']['Start']
            total_cost = float(result['Total']['BlendedCost']['Amount'])
            
            daily_costs.append({
                'date': date,
                'cost': total_cost
            })
        
        return {
            'period': f'{start_date} to {end_date}',
            'daily_costs': daily_costs,
            'total_cost': sum(day['cost'] for day in daily_costs),
            'average_daily_cost': sum(day['cost'] for day in daily_costs) / len(daily_costs) if daily_costs else 0
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cost trends: {str(e)}"
        )

@router.get("/service-breakdown")
async def get_service_cost_breakdown(
    credentials: AWSCredentialsRequest,
    days: int = 30,
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed cost breakdown by AWS service.
    """
    try:
        analyzer = get_aws_analyzer(credentials)
        service_costs = analyzer._get_service_breakdown(days)
        
        total_cost = sum(service['cost'] for service in service_costs)
        
        # Format response
        breakdown = []
        for service in service_costs:
            percentage = (service['cost'] / total_cost) * 100 if total_cost > 0 else 0
            breakdown.append({
                'service': service['service'],
                'cost': service['cost'],
                'percentage': percentage
            })
        
        return {
            'total_cost': total_cost,
            'service_breakdown': breakdown,
            'analysis_period_days': days
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get service breakdown: {str(e)}"
        )

@router.post("/quick-wins")
async def get_quick_wins(
    credentials: AWSCredentialsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Get quick win optimization opportunities that can be implemented immediately.
    
    Returns high-confidence, low-risk opportunities with immediate impact.
    """
    try:
        analyzer = get_aws_analyzer(credentials)
        report = analyzer.analyze_costs()
        
        # Filter for quick wins: high confidence, low risk, low effort
        quick_wins = [
            opp for opp in report.optimization_opportunities
            if (opp.confidence_level == 'high' and 
                opp.risk_level == 'low' and 
                opp.implementation_effort == 'low')
        ]
        
        # Sort by potential savings (highest first)
        quick_wins.sort(key=lambda x: x.potential_monthly_savings, reverse=True)
        
        total_quick_win_savings = sum(opp.potential_monthly_savings for opp in quick_wins)
        
        return {
            'quick_wins_count': len(quick_wins),
            'total_potential_savings': total_quick_win_savings,
            'annual_savings_potential': total_quick_win_savings * 12,
            'opportunities': [
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
                for opp in quick_wins[:10]  # Top 10 quick wins
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get quick wins: {str(e)}"
        )

# Background task functions

async def _store_analysis_results(user_id: int, analysis_data: Dict[str, Any], db: Client):
    """Store analysis results for historical tracking"""
    try:
        # In a real implementation, you would store this in a database table
        # For now, we'll just log it
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Storing cost analysis for user {user_id}: "
                   f"${analysis_data['potential_monthly_savings']:.2f} potential savings")
        
        # TODO: Implement database storage for analysis history
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to store analysis results: {str(e)}")

# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check for AWS Cost Analysis service"""
    return {
        "status": "healthy",
        "service": "AWS Cost Analysis",
        "timestamp": datetime.now().isoformat(),
        "features": [
            "cost_analysis",
            "optimization_recommendations", 
            "quick_wins",
            "cost_trends",
            "service_breakdown"
        ]
    }

