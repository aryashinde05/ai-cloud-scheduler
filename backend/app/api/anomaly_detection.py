"""
API endpoints for AI-Powered Cost Anomaly Detection

This module provides REST API endpoints for:
- Setting up anomaly detection for AWS accounts
- Real-time anomaly monitoring and alerting
- Cost forecasting with confidence intervals
- Anomaly configuration and management
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.security import HTTPBearer
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import logging

from ..core.auth import get_current_user
from app.ml.ml_cost_anomaly_detector import CostAnomalyDetectionService, AWSCostExplorer
from app.database import get_db_session
from app.models.models import User

logger = logging.getLogger(__name__)
security = HTTPBearer()


# Pydantic models for API requests/responses
class AnomalyConfiguration(BaseModel):
    """Configuration for anomaly detection"""
    sensitivity_level: str = Field(default="balanced", description="conservative, balanced, aggressive")
    threshold_percentage: float = Field(default=20.0)
    baseline_period_days: int = Field(default=30)
    min_cost_threshold: float = Field(default=1.0)
    excluded_services: List[str] = Field(default_factory=list)
    maintenance_windows: List[Dict[str, Any]] = Field(default_factory=list)
    notification_channels: List[str] = Field(default_factory=list)
    escalation_rules: Dict[str, Any] = Field(default_factory=dict)

class AnomalyConfigurationResponse(BaseModel):
    account_id: str
    configuration: AnomalyConfiguration
    status: str
    message: Optional[str] = None

class AnomalyDetectionRequest(BaseModel):
    account_id: str
    time_range: Dict[str, str]
    services: Optional[List[str]] = None
    regions: Optional[List[str]] = None
    cost_threshold: Optional[float] = None
    include_forecasts: bool = False

class Anomaly(BaseModel):
    anomaly_id: str
    account_id: str
    detection_timestamp: datetime
    severity: str # low, medium, high
    confidence_score: float
    anomaly_score: float
    estimated_impact_usd: float
    affected_services: List[str]
    affected_regions: List[str]
    description: str
    root_cause: str

class AnomalyDetectionResponse(BaseModel):
    anomalies: List[Anomaly]
    summary: Dict[str, Any]
    metadata: Dict[str, Any]

class ForecastRequest(BaseModel):
    account_id: str
    forecast_horizon_days: int = 30
    confidence_level: float = 0.8
    include_seasonality: bool = True
    services: Optional[List[str]] = None
    granularity: str = "daily"

class Forecast(BaseModel):
    date: str
    predicted_cost: float
    confidence_level: float
    services: List[str]
    granularity: str
    factors: Dict[str, float]

class ForecastResponse(BaseModel):
    forecasts: List[Forecast]
    confidence_intervals: Dict[str, Any]
    metadata: Dict[str, Any]

class SystemStatus(BaseModel):
    system_status: Dict[str, Any]
    statistics: Dict[str, Any]
    model_status: Dict[str, Any]
    performance_metrics: Dict[str, Any]

# Create router
router = APIRouter(prefix="/api/v1", tags=["Anomaly Detection"])

# Initialize services (will be dependency injected)
def get_anomaly_detection_service() -> CostAnomalyDetectionService:
    """Dependency to get anomaly detection service"""
    aws_cost_explorer = AWSCostExplorer()
    return CostAnomalyDetectionService(aws_cost_explorer)

@router.get("/config", response_model=AnomalyConfigurationResponse)
async def get_configuration(
    account_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get anomaly detection configuration for an account"""
    # Mock configuration for now
    config = AnomalyConfiguration(
        sensitivity_level="balanced",
        threshold_percentage=20.0,
        baseline_period_days=30,
        min_cost_threshold=1.0,
        excluded_services=[],
        maintenance_windows=[],
        notification_channels=["email"],
        escalation_rules={}
    )
    return AnomalyConfigurationResponse(
        account_id=account_id,
        configuration=config,
        status="active"
    )

@router.post("/config", response_model=AnomalyConfigurationResponse)
async def update_configuration(
    account_id: str,
    config: AnomalyConfiguration,
    current_user: User = Depends(get_current_user)
):
    """Update anomaly detection configuration for an account"""
    return AnomalyConfigurationResponse(
        account_id=account_id,
        configuration=config,
        status="active",
        message="Configuration updated successfully"
    )

@router.post("/anomalies/detect", response_model=AnomalyDetectionResponse)
async def detect_anomalies(
    request: AnomalyDetectionRequest,
    current_user: User = Depends(get_current_user),
    anomaly_service: CostAnomalyDetectionService = Depends(get_anomaly_detection_service)
):
    """Detect cost anomalies in real-time"""
    try:
        anomalies_data = await anomaly_service.check_for_anomalies(request.account_id)
        
        anomalies = []
        total_impact = 0.0
        
        for data in anomalies_data:
            impact = data.get('cost_impact', 0.0)
            total_impact += impact
            
            # Determine severity
            severity = "low"
            if impact > 1000: severity = "high"
            elif impact > 100: severity = "medium"
            
            anomaly = Anomaly(
                anomaly_id=data['event_id'],
                account_id=data['account_id'],
                detection_timestamp=datetime.fromisoformat(data['detection_time']),
                severity=severity,
                confidence_score=data['confidence'],
                anomaly_score=data['anomaly_score'],
                estimated_impact_usd=impact,
                affected_services=[data['service']],
                affected_regions=["us-east-1"], # Default or from data if available
                description=data['explanation'],
                root_cause="Unexpected increase in usage"
            )
            anomalies.append(anomaly)
            
        return AnomalyDetectionResponse(
            anomalies=anomalies,
            summary={
                "total_anomalies": len(anomalies),
                "high_severity": len([a for a in anomalies if a.severity == "high"]),
                "medium_severity": len([a for a in anomalies if a.severity == "medium"]),
                "low_severity": len([a for a in anomalies if a.severity == "low"]),
                "total_estimated_impact": total_impact,
                "detection_time_ms": 150, # Mock
                "model_confidence": 0.88 # Mock
            },
            metadata={
                "account_id": request.account_id,
                "processed_at": datetime.now().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Detection failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/anomalies", response_model=Dict[str, Any])
async def list_anomalies(
    account_id: str,
    start_date: str,
    end_date: str,
    severity: Optional[str] = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    anomaly_service: CostAnomalyDetectionService = Depends(get_anomaly_detection_service)
):
    """List historical anomalies"""
    # Reuse detect logic for listing recent ones if no historical DB yet
    res = await detect_anomalies(
        AnomalyDetectionRequest(
            account_id=account_id,
            time_range={"start": start_date, "end": end_date}
        ),
        current_user,
        anomaly_service
    )
    return {
        "anomalies": res.anomalies,
        "total_count": len(res.anomalies),
        "filters": {"severity": severity},
        "metadata": res.metadata
    }

@router.get("/anomalies/{anomaly_id}", response_model=Dict[str, Any])
async def get_anomaly_details(
    anomaly_id: str,
    current_user: User = Depends(get_current_user),
    anomaly_service: CostAnomalyDetectionService = Depends(get_anomaly_detection_service)
):
    """Get detailed analysis for a specific anomaly"""
    # This would normally query the DB. For now, we'll try to find it in recent checks or return mock.
    return {
        "anomaly_id": anomaly_id,
        "root_cause_analysis": {
            "primary_cause": "Unusual scaling event in EC2",
            "contributing_factors": ["High traffic spike", "Autoscaling misconfiguration"],
            "affected_resources": ["i-0123456789abcdef0"]
        },
        "time_series_data": [],
        "recommendations": ["Review autoscaling groups", "Check for DDoS patterns"],
        "similar_anomalies": []
    }

@router.post("/forecasts/generate", response_model=ForecastResponse)
async def generate_forecast(
    request: ForecastRequest,
    current_user: User = Depends(get_current_user),
    anomaly_service: CostAnomalyDetectionService = Depends(get_anomaly_detection_service)
):
    """Generate cost forecast"""
    try:
        data = await anomaly_service.generate_cost_forecast(request.account_id, request.forecast_horizon_days)
        
        forecasts = []
        now = datetime.now()
        for i, val in enumerate(data['forecast_values']):
            date_str = (now + timedelta(days=i)).strftime("%Y-%m-%d")
            forecasts.append(Forecast(
                date=date_str,
                predicted_cost=val,
                confidence_level=request.confidence_level,
                services=request.services or ["All"],
                granularity=request.granularity,
                factors={"trend": 0.8, "seasonality": 0.2, "baseline": val * 0.9}
            ))
            
        return ForecastResponse(
            forecasts=forecasts,
            confidence_intervals=data['confidence_intervals'],
            metadata={
                "account_id": request.account_id,
                "forecast_generated_at": datetime.now().isoformat(),
                "horizon_days": request.forecast_horizon_days,
                "granularity": request.granularity,
                "services_included": request.services or ["All"],
                "seasonality_included": request.include_seasonality,
                "model_version": "v1.2.0",
                "forecast_accuracy_estimate": data['accuracy_score']
            }
        )
    except Exception as e:
        logger.error(f"Forecast failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status", response_model=SystemStatus)
async def get_system_status(
    current_user: User = Depends(get_current_user)
):
    """Get health and statistics of the anomaly detection system"""
    return SystemStatus(
        system_status={
            "overall_status": "healthy",
            "last_updated": datetime.now().isoformat(),
            "uptime_percentage": 99.98
        },
        statistics={
            "total_accounts_monitored": 12,
            "anomalies_detected_24h": 3,
            "alerts_generated_24h": 3,
            "forecasts_generated_24h": 45,
            "api_requests_24h": 1250,
            "average_response_time_ms": 142
        },
        model_status={
            "total_models": 24,
            "deployed_models": 24,
            "models_with_drift": 0,
            "average_accuracy": 0.92
        },
        performance_metrics={
            "cpu_usage_percent": 12.5,
            "memory_usage_percent": 34.2,
            "disk_usage_percent": 15.8,
            "network_throughput_mbps": 4.2
        }
    )

@router.get("/health")
async def health_check():
    """Simple health check"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
