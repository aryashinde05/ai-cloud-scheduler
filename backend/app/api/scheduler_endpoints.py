from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional
from uuid import UUID
import boto3

from app.core.auth import get_current_user
from app.services.startup_migration.models import User
from app.services.scheduler_service import SchedulerService
from app.database.session import get_db
from app.models.aws_account import AwsAccount
from sqlalchemy.orm import Session
from pydantic import BaseModel

router = APIRouter(
    prefix="/scheduler",
    tags=["scheduler"]
)

class ScheduleCreateRequest(BaseModel):
    instance_id: str
    instance_name: Optional[str] = None
    schedule_type: str = "manual"
    start_time: str = "08:00"
    stop_time: str = "20:00"
    days_of_week: Optional[List[str]] = None
    enabled: bool = True
    estimated_monthly_savings: float = 0.0

class ScheduleUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    schedule_type: Optional[str] = None
    start_time: Optional[str] = None
    stop_time: Optional[str] = None
    days: Optional[List[str]] = None
    estimated_monthly_savings: Optional[float] = None

def get_scheduler_service(db: Session = None):
    """Build SchedulerService using stored AWS credentials if available."""
    session = None
    if db:
        account = AwsAccount.get_default(db)
        if account:
            try:
                access_key, secret_key, region = account.get_decrypted_credentials()
                session = boto3.Session(
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    region_name=region,
                )
            except Exception:
                pass
    if session is None:
        session = boto3.Session(region_name="us-east-1")
    return SchedulerService(boto3_session=session)

@router.get("/resources")
async def get_schedulable_resources(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get resources that can be scheduled (EC2, RDS)"""
    service = get_scheduler_service(db)
    return service.get_schedulable_resources()

@router.post("/analyze/{instance_id}")
async def analyze_instance_metrics(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Analyze an instance's metrics to generate an optimal schedule"""
    service = get_scheduler_service(db)
    try:
        recommendation = service.analyze_resource(instance_id)
        if recommendation and "error" in recommendation.get("analysis", {}):
             raise HTTPException(status_code=500, detail=recommendation["analysis"]["error"])
        return recommendation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.get("/schedules")
async def get_schedules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all configured schedules"""
    service = get_scheduler_service(db)
    return service.get_schedules()

@router.post("/schedules")
async def create_schedule(
    request: ScheduleCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new resource schedule"""
    service = get_scheduler_service(db)
    try:
        schedule_data = request.dict(exclude_unset=True)
        if "days_of_week" in schedule_data:
             schedule_data["days"] = schedule_data.pop("days_of_week")
        schedule = service.create_schedule(schedule_data)
        return schedule
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create schedule: {str(e)}")

@router.put("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    request: ScheduleUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an existing schedule (e.g. pause/resume)"""
    service = get_scheduler_service(db)
    try:
        updates = request.dict(exclude_unset=True)
        schedule = service.update_schedule(schedule_id=schedule_id, data=updates)
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        return schedule
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update schedule: {str(e)}")

@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a schedule"""
    service = get_scheduler_service(db)
    success = service.delete_schedule(schedule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Schedule not found or could not be deleted")
    return {"status": "deleted"}

@router.get("/savings")
async def get_projected_savings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Compute projected monthly savings from all active schedules"""
    service = get_scheduler_service(db)
    summary = service.get_savings_summary()
    return {
        "active_schedules": summary.get("active_schedules", 0),
        "total_schedules": summary.get("total_schedules", 0),
        "estimated_monthly_savings": summary.get("estimated_monthly_savings", 0.0),
        "estimated_annual_savings": summary.get("estimated_annual_savings", 0.0),
        "total_realized_savings": summary.get("total_realized_savings", 0.0),
        "actions_executed": summary.get("actions_executed", 0),
        "success_rate": summary.get("success_rate", 100),
    }
