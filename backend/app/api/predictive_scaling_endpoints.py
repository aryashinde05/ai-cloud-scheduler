"""
FastAPI endpoints for Predictive Scaling Engine

Provides REST API access to predictive scaling functionality:
- Resource monitoring initialization
- Demand forecasting
- Scaling recommendations
- Multi-resource optimization
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID

import pandas as pd
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel, Field
from supabase import Client

from app.database.database import get_supabase
from app.services.predictive_scaling_engine import (
    PredictiveScalingEngine, DemandForecast, ScalingRecommendation, 
    ScalingResult, ForecastHorizon, ScalingActionType
)
from app.services.safety_checker import SafetyChecker
from app.services.cloud_providers import CloudProviderService
from app.services.startup_migration.models import ResourceMetrics, ScalingEvent
from app.core.auth import get_current_user, User

logger = logging.getLogger(__name__)

# Pydantic models for API requests/responses
class ResourceInitializationRequest(BaseModel):
    """Request to initialize predictive scaling for a resource"""
    resource_id: str = Field(..., description="Unique identifier for the resource")
    resource_type: str = Field(..., description="Type of resource (e.g., 'ec2_instance', 'auto_scaling_group')")
    training_days: int = Field(default=90, ge=7, le=365, description="Days of historical data to use for training")

class ForecastRequest(BaseModel):
    """Request for demand forecasting"""
    resource_id: str = Field(..., description="Resource to forecast")
    horizon: str = Field(..., description="Forecast horizon: '1h', '24h', or '7d'")
    include_confidence_intervals: bool = Field(default=True, description="Include confidence intervals in response")

class ScalingRecommendationRequest(BaseModel):
    """Request for scaling recommendation"""
    resource_id: str = Field(..., description="Resource to analyze")
    current_capacity: int = Field(..., ge=1, description="Current resource capacity")
    forecast_horizon: str = Field(default="24h", description="Forecast horizon for analysis")

class MultiResourceOptimizationRequest(BaseModel):
    """Request for multi-resource optimization"""
    resource_ids: List[str] = Field(..., min_items=1, description="List of resources to optimize")
    available_providers: List[str] = Field(..., min_items=1, description="Available cloud providers")
    optimization_horizon: str = Field(default="24h", description="Optimization time horizon")

class ExecuteScalingRequest(BaseModel):
    """Request to execute scaling action"""
    resource_id: str = Field(..., description="Resource to scale")
    action_type: str = Field(..., description="Scaling action type")
    target_capacity: int = Field(..., ge=1, description="Target capacity")
    current_capacity: int = Field(..., ge=1, description="Current capacity")
    force_execution: bool = Field(default=False, description="Force execution even if safety checks fail")

# Response models
class DemandPoint(BaseModel):
    """Single demand prediction point"""
    timestamp: datetime
    predicted_value: float
    confidence_lower: float
    confidence_upper: float
    contributing_factors: Dict[str, float]

class ForecastResponse(BaseModel):
    """Demand forecast response"""
    resource_id: str
    forecast_horizon: str
    predictions: List[DemandPoint]
    confidence_intervals: List[List[float]]
    seasonal_factors: Dict[str, float]
    external_factors: List[str]
    accuracy_score: float
    model_used: str
    generated_at: datetime

class ScalingRecommendationResponse(BaseModel):
    """Scaling recommendation response"""
    resource_id: str
    action_type: str
    target_capacity: int
    current_capacity: int
    confidence: float
    reasoning: str
    expected_impact: Dict[str, float]
    execution_time: datetime
    safety_checks_passed: bool

class ScalingResultResponse(BaseModel):
    """Scaling execution result response"""
    resource_id: str
    action_executed: str
    success: bool
    previous_capacity: int
    new_capacity: int
    execution_time: datetime
    error_message: Optional[str]
    cost_impact: Optional[float]

class OptimizationResponse(BaseModel):
    """Multi-resource optimization response"""
    resource_allocations: Dict[str, Any]
    optimization_summary: Dict[str, Any]
    generated_at: str

# Initialize router
router = APIRouter(prefix="/api/v1/predictive-scaling", tags=["Predictive Scaling"])

# Global engine instance (would be dependency injected in production)
_scaling_engine: Optional[PredictiveScalingEngine] = None

def get_scaling_engine() -> PredictiveScalingEngine:
    """Get or create the predictive scaling engine"""
    global _scaling_engine
    if _scaling_engine is None:
        safety_checker = SafetyChecker()
        _scaling_engine = PredictiveScalingEngine(safety_checker)
    return _scaling_engine

@router.post("/resources/initialize", response_model=Dict[str, Any])
async def initialize_resource_monitoring(
    request: ResourceInitializationRequest,
    current_user: User = Depends(get_current_user),
    db: Client = Depends(get_supabase)
):
    """Initialize predictive scaling for a resource"""
    
    try:
        logger.info(f"Initializing predictive scaling for resource {request.resource_id}")
        
        # Get historical metrics data
        historical_data = await _get_historical_metrics(
            request.resource_id, request.training_days, db
        )
        
        if historical_data.empty:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient historical data for resource {request.resource_id}"
            )
        
        # Initialize monitoring
        engine = get_scaling_engine()
        success = await engine.initialize_resource_monitoring(
            request.resource_id, historical_data
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize predictive scaling"
            )
        
        return {
            "success": True,
            "resource_id": request.resource_id,
            "training_data_points": len(historical_data),
            "training_period_days": request.training_days,
            "initialized_at": datetime.now().isoformat(),
            "message": "Predictive scaling initialized successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initializing resource monitoring: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/forecast", response_model=ForecastResponse)
async def generate_demand_forecast(
    request: ForecastRequest,
    current_user: User = Depends(get_current_user),
    db: Client = Depends(get_supabase)
):
    """Generate demand forecast for a resource"""
    
    try:
        # Validate horizon
        try:
            horizon = ForecastHorizon(request.horizon)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid horizon '{request.horizon}'. Must be '1h', '24h', or '7d'"
            )
        
        # Get recent metrics data
        recent_data = await _get_recent_metrics(request.resource_id, 30, db)
        
        if recent_data.empty:
            raise HTTPException(
                status_code=400,
                detail=f"No recent data available for resource {request.resource_id}"
            )
        
        # Generate forecast
        engine = get_scaling_engine()
        forecast = await engine.forecast_demand(request.resource_id, horizon, recent_data)
        
        if not forecast:
            raise HTTPException(
                status_code=404,
                detail=f"Resource {request.resource_id} not initialized for prediction"
            )
        
        # Convert to response format
        predictions = [
            DemandPoint(
                timestamp=p.timestamp,
                predicted_value=p.predicted_value,
                confidence_lower=p.confidence_lower,
                confidence_upper=p.confidence_upper,
                contributing_factors=p.contributing_factors
            )
            for p in forecast.predictions
        ]
        
        return ForecastResponse(
            resource_id=forecast.resource_id,
            forecast_horizon=forecast.forecast_horizon.value,
            predictions=predictions,
            confidence_intervals=forecast.confidence_intervals,
            seasonal_factors=forecast.seasonal_factors,
            external_factors=forecast.external_factors,
            accuracy_score=forecast.accuracy_score,
            model_used=forecast.model_used,
            generated_at=datetime.now()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating forecast: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/recommendations", response_model=ScalingRecommendationResponse)
async def get_scaling_recommendation(
    request: ScalingRecommendationRequest,
    current_user: User = Depends(get_current_user),
    db: Client = Depends(get_supabase)
):
    """Get scaling recommendation based on demand forecast"""
    
    try:
        # Validate horizon
        try:
            horizon = ForecastHorizon(request.forecast_horizon)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid horizon '{request.forecast_horizon}'. Must be '1h', '24h', or '7d'"
            )
        
        # Get recent data and generate forecast
        recent_data = await _get_recent_metrics(request.resource_id, 30, db)
        
        if recent_data.empty:
            raise HTTPException(
                status_code=400,
                detail=f"No recent data available for resource {request.resource_id}"
            )
        
        engine = get_scaling_engine()
        forecast = await engine.forecast_demand(request.resource_id, horizon, recent_data)
        
        if not forecast:
            raise HTTPException(
                status_code=404,
                detail=f"Resource {request.resource_id} not initialized for prediction"
            )
        
        # Get scaling recommendation
        recommendation = await engine.recommend_scaling_action(forecast, request.current_capacity)
        
        return ScalingRecommendationResponse(
            resource_id=recommendation.resource_id,
            action_type=recommendation.action_type.value,
            target_capacity=recommendation.target_capacity,
            current_capacity=recommendation.current_capacity,
            confidence=recommendation.confidence,
            reasoning=recommendation.reasoning,
            expected_impact=recommendation.expected_impact,
            execution_time=recommendation.execution_time,
            safety_checks_passed=recommendation.safety_checks_passed
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting scaling recommendation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/execute", response_model=ScalingResultResponse)
async def execute_scaling_action(
    request: ExecuteScalingRequest,
    current_user: User = Depends(get_current_user),
    db: Client = Depends(get_supabase)
):
    """Execute a scaling action"""
    
    try:
        # Validate action type
        try:
            action_type = ScalingActionType(request.action_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action type '{request.action_type}'"
            )
        
        # Create scaling recommendation
        from app.services.predictive_scaling_engine import ScalingRecommendation
        recommendation = ScalingRecommendation(
            resource_id=request.resource_id,
            action_type=action_type,
            target_capacity=request.target_capacity,
            current_capacity=request.current_capacity,
            confidence=1.0,  # Manual execution
            reasoning="Manual scaling request",
            expected_impact={},
            execution_time=datetime.now(),
            safety_checks_passed=request.force_execution
        )
        
        # Execute scaling (would need actual cloud provider integration)
        engine = get_scaling_engine()
        # For now, simulate cloud provider
        from app.services.cloud_providers import AWSCostExplorerAdapter, AWSCredentials
        
        # This would be retrieved from configuration in a real system
        mock_credentials = AWSCredentials("mock", "mock")
        cloud_provider = AWSCostExplorerAdapter(mock_credentials)
        
        result = await engine.execute_scaling(recommendation, cloud_provider)
        
        # Record scaling event
        await _record_scaling_event(result, db)
        
        return ScalingResultResponse(
            resource_id=result.resource_id,
            action_executed=result.action_executed.value,
            success=result.success,
            previous_capacity=result.previous_capacity,
            new_capacity=result.new_capacity,
            execution_time=result.execution_time,
            error_message=result.error_message,
            cost_impact=result.cost_impact
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing scaling action: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/optimize", response_model=OptimizationResponse)
async def optimize_multi_resource_allocation(
    request: MultiResourceOptimizationRequest,
    current_user: User = Depends(get_current_user),
    db: Client = Depends(get_supabase)
):
    """Optimize allocation across multiple resources and providers"""
    
    try:
        # Validate horizon
        try:
            horizon = ForecastHorizon(request.optimization_horizon)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid horizon '{request.optimization_horizon}'. Must be '1h', '24h', or '7d'"
            )
        
        # Optimize allocation
        engine = get_scaling_engine()
        optimization_result = await engine.optimize_multi_resource_allocation(
            request.resource_ids,
            horizon,
            request.available_providers
        )
        
        if not optimization_result:
            raise HTTPException(
                status_code=400,
                detail="No optimization results generated. Check that resources are initialized."
            )
        
        return OptimizationResponse(
            resource_allocations=optimization_result.get('resource_allocations', {}),
            optimization_summary=optimization_result.get('optimization_summary', {}),
            generated_at=optimization_result.get('generated_at', datetime.now().isoformat())
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error optimizing multi-resource allocation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/resources/{resource_id}/status")
async def get_resource_status(
    resource_id: str,
    current_user: User = Depends(get_current_user),
    db: Client = Depends(get_supabase)
):
    """Get predictive scaling status for a resource"""
    
    try:
        engine = get_scaling_engine()
        
        # Check if resource is trained
        is_trained = resource_id in engine.trained_resources
        
        # Get recent metrics count
        recent_metrics = await _get_recent_metrics(resource_id, 7, db)
        
        # Get recent scaling events
        recent_events = db.query(ScalingEvent).filter(
            ScalingEvent.resource_id == resource_id,
            ScalingEvent.execution_time >= datetime.now() - timedelta(days=30)
        ).order_by(ScalingEvent.execution_time.desc()).limit(10).all()
        
        return {
            "resource_id": resource_id,
            "is_trained": is_trained,
            "recent_metrics_count": len(recent_metrics),
            "recent_scaling_events": len(recent_events),
            "last_scaling_event": recent_events[0].execution_time.isoformat() if recent_events else None,
            "status": "active" if is_trained else "not_initialized"
        }
        
    except Exception as e:
        logger.error(f"Error getting resource status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper functions
async def _get_historical_metrics(resource_id: str, days: int, db: Session) -> pd.DataFrame:
    """Get historical metrics data for a resource"""
    
    start_date = datetime.now() - timedelta(days=days)
    
    metrics = db.query(ResourceMetrics).filter(
        ResourceMetrics.resource_id == resource_id,
        ResourceMetrics.timestamp >= start_date
    ).order_by(ResourceMetrics.timestamp).all()
    
    if not metrics:
        return pd.DataFrame()
    
    # Convert to DataFrame
    data = []
    for metric in metrics:
        data.append({
            'timestamp': metric.timestamp,
            'cpu_utilization': float(metric.cpu_utilization or 0),
            'memory_utilization': float(metric.memory_utilization or 0),
            'network_in': float(metric.network_in or 0),
            'network_out': float(metric.network_out or 0),
            'disk_read': float(metric.disk_read or 0),
            'disk_write': float(metric.disk_write or 0),
            'request_count': metric.request_count or 0,
            'response_time': float(metric.response_time or 0)
        })
    
    return pd.DataFrame(data)

async def _get_recent_metrics(resource_id: str, days: int, db: Session) -> pd.DataFrame:
    """Get recent metrics data for a resource"""
    return await _get_historical_metrics(resource_id, days, db)

async def _record_scaling_event(result: ScalingResult, db: Session):
    """Record a scaling event in the database"""
    
    try:
        scaling_event = ScalingEvent(
            resource_id=result.resource_id,
            resource_type="unknown",  # Would be determined from resource metadata
            scaling_action=result.action_executed.value,
            previous_capacity=result.previous_capacity,
            target_capacity=result.new_capacity,
            actual_capacity=result.new_capacity,
            triggered_by="api_request",
            trigger_reason="Manual scaling request via API",
            execution_time=result.execution_time,
            completion_time=result.execution_time,
            success=result.success,
            error_message=result.error_message,
            cost_impact=result.cost_impact
        )
        
        db.add(scaling_event)
        db.commit()
        
        logger.info(f"Recorded scaling event for resource {result.resource_id}")
        
    except Exception as e:
        logger.error(f"Error recording scaling event: {str(e)}")
        db.rollback()

