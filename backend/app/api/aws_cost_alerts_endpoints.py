"""
AWS Cost Alerts & Monitoring API Endpoints

Provides REST API endpoints for cost monitoring, alerting, and proactive notifications.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field, EmailStr
from supabase import Client

from app.database.database import get_supabase
from app.core.auth import get_current_user
from app.services.startup_migration.models import User
from app.aws.aws_cost_monitor import AWSCostMonitor, BudgetThreshold, CostAlert

router = APIRouter(prefix="/api/v1/aws-cost-alerts", tags=["AWS Cost Alerts"])

# Request/Response Models

class AWSCredentialsRequest(BaseModel):
    """AWS credentials for monitoring"""
    aws_access_key_id: str = Field(..., description="AWS Access Key ID")
    aws_secret_access_key: str = Field(..., description="AWS Secret Access Key")
    region: str = Field(default="us-east-1", description="AWS Region")

class BudgetThresholdRequest(BaseModel):
    """Request to create budget threshold"""
    name: str = Field(..., description="Budget name")
    monthly_budget: float = Field(..., gt=0, description="Monthly budget amount")
    warning_threshold: float = Field(default=80.0, ge=0, le=100, description="Warning threshold percentage")
    critical_threshold: float = Field(default=95.0, ge=0, le=100, description="Critical threshold percentage")
    services: List[str] = Field(default=[], description="Specific services to monitor (empty = all)")
    enabled: bool = Field(default=True, description="Enable this threshold")
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Monthly AWS Budget",
                "monthly_budget": 1000.0,
                "warning_threshold": 80.0,
                "critical_threshold": 95.0,
                "services": [],
                "enabled": True
            }
        }

class NotificationConfigRequest(BaseModel):
    """Notification configuration"""
    email_enabled: bool = Field(default=False, description="Enable email notifications")
    email_config: Optional[Dict[str, Any]] = Field(default=None, description="Email configuration")
    slack_enabled: bool = Field(default=False, description="Enable Slack notifications")
    slack_config: Optional[Dict[str, Any]] = Field(default=None, description="Slack configuration")
    
    class Config:
        schema_extra = {
            "example": {
                "email_enabled": True,
                "email_config": {
                    "to_email": "admin@company.com",
                    "from_email": "alerts@finops.com",
                    "smtp_server": "smtp.gmail.com",
                    "smtp_port": 587,
                    "use_tls": True,
                    "username": "alerts@finops.com",
                    "password": "app_password"
                },
                "slack_enabled": True,
                "slack_config": {
                    "webhook_url": "https://hooks.slack.com/services/..."
                }
            }
        }

class MonitoringConfigRequest(BaseModel):
    """Complete monitoring configuration"""
    credentials: AWSCredentialsRequest
    budget_thresholds: List[BudgetThresholdRequest] = Field(default=[], description="Budget thresholds")
    notification_config: NotificationConfigRequest
    anomaly_detection_enabled: bool = Field(default=True, description="Enable anomaly detection")
    spike_detection_threshold: float = Field(default=50.0, ge=0, description="Cost spike threshold percentage")

class CostAlertResponse(BaseModel):
    """Response model for cost alert"""
    alert_id: str
    alert_type: str
    severity: str
    title: str
    description: str
    current_cost: float
    threshold_cost: Optional[float]
    percentage_change: Optional[float]
    service_affected: Optional[str]
    recommended_actions: List[str]
    created_at: str
    resolved: bool

class DailySummaryResponse(BaseModel):
    """Response model for daily cost summary"""
    date: str
    total_cost: float
    cost_change: float
    cost_change_percentage: float
    top_services: List[Dict[str, Any]]
    alerts_count: int
    optimization_opportunities: int

class MonitoringResultsResponse(BaseModel):
    """Response model for monitoring results"""
    monitoring_date: str
    new_alerts_count: int
    total_active_alerts: int
    budget_alerts: int
    anomaly_alerts: int
    spike_alerts: int
    daily_summary: DailySummaryResponse
    new_alerts: List[CostAlertResponse]

class AlertSummaryResponse(BaseModel):
    """Response model for alert summary"""
    total_active: int
    by_severity: Dict[str, int]
    by_type: Dict[str, int]
    most_recent: Optional[CostAlertResponse]

# Global monitor instances (in production, use dependency injection)
_monitor_cache: Dict[str, AWSCostMonitor] = {}

def get_cost_monitor(credentials: AWSCredentialsRequest) -> AWSCostMonitor:
    """Get or create AWS Cost Monitor instance"""
    cache_key = f"{credentials.aws_access_key_id}:{credentials.region}"
    
    if cache_key not in _monitor_cache:
        _monitor_cache[cache_key] = AWSCostMonitor(
            aws_access_key_id=credentials.aws_access_key_id,
            aws_secret_access_key=credentials.aws_secret_access_key,
            region=credentials.region
        )
    
    return _monitor_cache[cache_key]

# API Endpoints

@router.post("/setup-monitoring")
async def setup_cost_monitoring(
    config: MonitoringConfigRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Client = Depends(get_supabase)
):
    """
    Set up comprehensive cost monitoring with budget thresholds and notifications.
    
    This endpoint configures budget thresholds, notification settings, and starts
    monitoring your AWS costs for anomalies and threshold breaches.
    """
    try:
        monitor = get_cost_monitor(config.credentials)
        
        # Add budget thresholds
        for threshold_config in config.budget_thresholds:
            threshold = BudgetThreshold(
                name=threshold_config.name,
                monthly_budget=threshold_config.monthly_budget,
                warning_threshold=threshold_config.warning_threshold,
                critical_threshold=threshold_config.critical_threshold,
                services=threshold_config.services,
                enabled=threshold_config.enabled
            )
            monitor.add_budget_threshold(threshold)
        
        # Store notification config (in production, save to database)
        notification_config = config.notification_config.dict()
        
        # Run initial monitoring cycle in background
        background_tasks.add_task(
            _run_monitoring_and_notify,
            monitor=monitor,
            notification_config=notification_config,
            user_id=current_user.id
        )
        
        return {
            "status": "success",
            "message": "Cost monitoring setup completed",
            "budget_thresholds_count": len(config.budget_thresholds),
            "notifications_enabled": config.notification_config.email_enabled or config.notification_config.slack_enabled,
            "monitoring_features": {
                "budget_monitoring": len(config.budget_thresholds) > 0,
                "anomaly_detection": config.anomaly_detection_enabled,
                "spike_detection": True,
                "daily_summaries": True
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to setup cost monitoring: {str(e)}"
        )

@router.post("/run-monitoring", response_model=MonitoringResultsResponse)
async def run_cost_monitoring(
    credentials: AWSCredentialsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Run immediate cost monitoring cycle and return results.
    
    This endpoint performs real-time cost analysis, checks budget thresholds,
    detects anomalies and cost spikes, and returns all findings.
    """
    try:
        monitor = get_cost_monitor(credentials)
        results = monitor.run_monitoring_cycle()
        
        # Convert to response format
        response = MonitoringResultsResponse(
            monitoring_date=results['monitoring_date'],
            new_alerts_count=results['new_alerts_count'],
            total_active_alerts=results['total_active_alerts'],
            budget_alerts=results['budget_alerts'],
            anomaly_alerts=results['anomaly_alerts'],
            spike_alerts=results['spike_alerts'],
            daily_summary=DailySummaryResponse(
                date=results['daily_summary'].date,
                total_cost=results['daily_summary'].total_cost,
                cost_change=results['daily_summary'].cost_change,
                cost_change_percentage=results['daily_summary'].cost_change_percentage,
                top_services=results['daily_summary'].top_services,
                alerts_count=results['daily_summary'].alerts_count,
                optimization_opportunities=results['daily_summary'].optimization_opportunities
            ),
            new_alerts=[
                CostAlertResponse(
                    alert_id=alert.alert_id,
                    alert_type=alert.alert_type,
                    severity=alert.severity,
                    title=alert.title,
                    description=alert.description,
                    current_cost=alert.current_cost,
                    threshold_cost=alert.threshold_cost,
                    percentage_change=alert.percentage_change,
                    service_affected=alert.service_affected,
                    recommended_actions=alert.recommended_actions,
                    created_at=alert.created_at.isoformat(),
                    resolved=alert.resolved
                )
                for alert in results['new_alerts']
            ]
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cost monitoring failed: {str(e)}"
        )

@router.get("/alerts", response_model=List[CostAlertResponse])
async def get_active_alerts(
    credentials: AWSCredentialsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Get all active (unresolved) cost alerts.
    
    Returns a list of all current cost alerts including budget threshold breaches,
    anomalies, and cost spikes that haven't been resolved yet.
    """
    try:
        monitor = get_cost_monitor(credentials)
        active_alerts = monitor.get_active_alerts()
        
        return [
            CostAlertResponse(
                alert_id=alert.alert_id,
                alert_type=alert.alert_type,
                severity=alert.severity,
                title=alert.title,
                description=alert.description,
                current_cost=alert.current_cost,
                threshold_cost=alert.threshold_cost,
                percentage_change=alert.percentage_change,
                service_affected=alert.service_affected,
                recommended_actions=alert.recommended_actions,
                created_at=alert.created_at.isoformat(),
                resolved=alert.resolved
            )
            for alert in active_alerts
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get alerts: {str(e)}"
        )

@router.get("/alerts/summary", response_model=AlertSummaryResponse)
async def get_alert_summary(
    credentials: AWSCredentialsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Get summary statistics of current alerts.
    
    Returns aggregated information about active alerts including counts by
    severity and type, plus the most recent alert.
    """
    try:
        monitor = get_cost_monitor(credentials)
        summary = monitor.get_alert_summary()
        
        most_recent = None
        if summary['most_recent']:
            alert = summary['most_recent']
            most_recent = CostAlertResponse(
                alert_id=alert.alert_id,
                alert_type=alert.alert_type,
                severity=alert.severity,
                title=alert.title,
                description=alert.description,
                current_cost=alert.current_cost,
                threshold_cost=alert.threshold_cost,
                percentage_change=alert.percentage_change,
                service_affected=alert.service_affected,
                recommended_actions=alert.recommended_actions,
                created_at=alert.created_at.isoformat(),
                resolved=alert.resolved
            )
        
        return AlertSummaryResponse(
            total_active=summary['total_active'],
            by_severity=summary['by_severity'],
            by_type=summary['by_type'],
            most_recent=most_recent
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get alert summary: {str(e)}"
        )

@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    credentials: AWSCredentialsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Mark a specific alert as resolved.
    
    This removes the alert from the active alerts list and stops further
    notifications for this specific issue.
    """
    try:
        monitor = get_cost_monitor(credentials)
        success = monitor.resolve_alert(alert_id)
        
        if success:
            return {
                "status": "success",
                "message": f"Alert {alert_id} resolved successfully",
                "resolved_at": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert {alert_id} not found"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve alert: {str(e)}"
        )

@router.get("/daily-summary")
async def get_daily_cost_summary(
    credentials: AWSCredentialsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Get today's cost summary with trends and key metrics.
    
    Returns comprehensive daily cost information including total spend,
    day-over-day changes, top services, and alert counts.
    """
    try:
        monitor = get_cost_monitor(credentials)
        summary = monitor.generate_daily_summary()
        
        return DailySummaryResponse(
            date=summary.date,
            total_cost=summary.total_cost,
            cost_change=summary.cost_change,
            cost_change_percentage=summary.cost_change_percentage,
            top_services=summary.top_services,
            alerts_count=summary.alerts_count,
            optimization_opportunities=summary.optimization_opportunities
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get daily summary: {str(e)}"
        )

@router.post("/test-notifications")
async def test_notifications(
    notification_config: NotificationConfigRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Test notification configuration by sending a sample alert.
    
    This endpoint validates your email and Slack notification settings
    by sending a test alert message.
    """
    try:
        # Create a test alert
        test_alert = CostAlert(
            alert_id="test_alert_" + datetime.now().strftime('%Y%m%d_%H%M%S'),
            alert_type='test',
            severity='medium',
            title="🧪 Test Alert - Notification Configuration",
            description="This is a test alert to verify your notification settings are working correctly.",
            current_cost=123.45,
            threshold_cost=100.00,
            percentage_change=23.45,
            service_affected="Test Service",
            recommended_actions=[
                "This is a test alert - no action required",
                "If you received this, your notifications are working!"
            ],
            created_at=datetime.now()
        )
        
        # Create a temporary monitor for testing
        class TestMonitor:
            def send_alert_notification(self, alert, config):
                # Import here to avoid circular imports
                from app.aws.aws_cost_monitor import AWSCostMonitor
                temp_monitor = AWSCostMonitor.__new__(AWSCostMonitor)
                return temp_monitor._send_email_alert(alert, config.get('email', {})) if config.get('email_enabled') else True
        
        test_monitor = TestMonitor()
        
        results = {}
        
        # Test email if enabled
        if notification_config.email_enabled and notification_config.email_config:
            email_success = test_monitor.send_alert_notification(
                test_alert, 
                {'email_enabled': True, 'email': notification_config.email_config}
            )
            results['email'] = {
                'enabled': True,
                'success': email_success,
                'message': 'Test email sent successfully' if email_success else 'Failed to send test email'
            }
        else:
            results['email'] = {'enabled': False}
        
        # Test Slack if enabled
        if notification_config.slack_enabled and notification_config.slack_config:
            # Import here to avoid circular imports
            import requests
            
            try:
                test_message = {
                    "text": "🧪 FinOps Platform - Test Notification",
                    "attachments": [
                        {
                            "color": "good",
                            "title": "Notification Test Successful",
                            "text": "Your Slack notifications are configured correctly!",
                            "footer": "FinOps Platform Cost Monitor"
                        }
                    ]
                }
                
                response = requests.post(
                    notification_config.slack_config['webhook_url'],
                    json=test_message,
                    timeout=10
                )
                
                slack_success = response.status_code == 200
                results['slack'] = {
                    'enabled': True,
                    'success': slack_success,
                    'message': 'Test Slack message sent successfully' if slack_success else f'Failed to send Slack message: {response.status_code}'
                }
                
            except Exception as e:
                results['slack'] = {
                    'enabled': True,
                    'success': False,
                    'message': f'Slack test failed: {str(e)}'
                }
        else:
            results['slack'] = {'enabled': False}
        
        return {
            'status': 'completed',
            'test_results': results,
            'overall_success': any(r.get('success', False) for r in results.values() if r.get('enabled')),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test notifications: {str(e)}"
        )

# Background task functions

async def _run_monitoring_and_notify(monitor: AWSCostMonitor, notification_config: Dict[str, Any], user_id: int):
    """Background task to run monitoring and send notifications"""
    try:
        # Run monitoring cycle
        results = monitor.run_monitoring_cycle()
        
        # Send notifications for new alerts
        for alert in results.get('new_alerts', []):
            if alert.severity in ['high', 'critical']:  # Only notify for important alerts
                monitor.send_alert_notification(alert, notification_config)
        
        # Log results
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Background monitoring completed for user {user_id}: "
                   f"{results['new_alerts_count']} new alerts")
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Background monitoring failed for user {user_id}: {str(e)}")

# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check for AWS Cost Alerts service"""
    return {
        "status": "healthy",
        "service": "AWS Cost Alerts & Monitoring",
        "timestamp": datetime.now().isoformat(),
        "features": [
            "budget_threshold_monitoring",
            "cost_anomaly_detection",
            "cost_spike_detection",
            "email_notifications",
            "slack_notifications",
            "daily_summaries",
            "real_time_alerts"
        ]
    }
