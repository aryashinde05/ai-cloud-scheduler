import os
import uuid
from typing import Any, Dict, List, Optional

import boto3
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.database.session import get_db
from app.models.aws_account import AwsAccount
from app.models.ec2_schedule_models import Ec2Schedule, SchedulerActionLog
from app.services.startup_migration.models import User
from app.services.scheduler_service import SchedulerService
from app.services.schedule_job_manager import (
    is_scheduler_execution_enabled,
    reload_schedule_jobs,
    set_scheduler_execution_enabled,
)
from app.services.cost_explorer_helper import try_daily_costs_by_service
from app.services.scheduler_savings_util import (
    estimated_monthly_for_schedule,
    estimated_savings_for_schedule_stop,
)

router = APIRouter(
    prefix="/scheduler",
    tags=["scheduler"],
)

_SCHEDULER_SERVICE_CACHE: Dict[str, SchedulerService] = {}


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


class SchedulerActionExecuteRequest(BaseModel):
    action_type: str
    resource_id: str


class ProductionScheduleCreate(BaseModel):
    """DB-backed schedule for APScheduler (bulk + timezone + weekday pattern)."""

    instance_ids: List[str] = Field(default_factory=list)
    instance_id: Optional[str] = None
    start_time: str = "09:00"
    stop_time: str = "19:00"
    timezone: str = Field("UTC", description="IANA timezone e.g. Asia/Kolkata")
    days_pattern: str = Field("all", description="all | weekdays | weekends")
    enabled: bool = True
    estimated_hourly_usd: Optional[float] = Field(
        None,
        description="Optional $/hr for savings estimates (defaults from env SCHEDULER_DEFAULT_HOURLY_USD)",
    )


class SchedulerSettingsUpdate(BaseModel):
    execution_enabled: bool


def _default_region() -> str:
    return os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-south-1"


def get_scheduler_service(db: Session = None):
    session = None
    region = _default_region()
    cache_key = f"none|{region}"
    if db:
        account = AwsAccount.get_default(db)
        if account:
            try:
                access_key, secret_key, region = account.get_decrypted_credentials()
                cache_key = f"account:{account.id}|{region}"
                session = boto3.Session(
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    region_name=region,
                )
            except Exception:
                pass
    if session is None:
        session = boto3.Session(region_name=region)

    if cache_key in _SCHEDULER_SERVICE_CACHE:
        return _SCHEDULER_SERVICE_CACHE[cache_key]

    service = SchedulerService(boto3_session=session, region=region)
    _SCHEDULER_SERVICE_CACHE[cache_key] = service
    return service


def _days_from_pattern(pattern: str) -> List[str]:
    p = (pattern or "all").lower().strip()
    if p == "weekdays":
        return ["mon", "tue", "wed", "thu", "fri"]
    if p == "weekends":
        return ["sat", "sun"]
    return ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _ec2_row_to_schedule_dict(row: Ec2Schedule) -> Dict[str, Any]:
    ids = list(row.instance_ids or [])
    primary = ids[0] if ids else ""
    return {
        "id": row.public_id,
        "instance_id": primary,
        "instance_name": primary,
        "instance_ids": ids,
        "schedule_type": "production",
        "stop_time": row.stop_time,
        "start_time": row.start_time,
        "timezone": row.timezone,
        "days_pattern": row.days_pattern,
        "days": _days_from_pattern(row.days_pattern),
        "enabled": row.enabled,
        "estimated_monthly_savings": estimated_monthly_for_schedule(row),
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "last_action": None,
        "total_savings": 0.0,
        "executions": 0,
        "estimated_hourly_usd": row.estimated_hourly_usd,
    }


def _merged_schedules(db: Session, service: SchedulerService) -> List[Dict[str, Any]]:
    db_rows = db.query(Ec2Schedule).order_by(Ec2Schedule.id.desc()).all()
    out = [_ec2_row_to_schedule_dict(r) for r in db_rows]
    prod_ids = {s["instance_id"] for s in out}
    for s in service.get_schedules():
        if s.get("instance_id") not in prod_ids:
            out.append(s)
    return out


def _find_ec2_schedule_for_instance(db: Session, instance_id: str) -> Optional[Ec2Schedule]:
    for row in db.query(Ec2Schedule).filter(Ec2Schedule.enabled.is_(True)).all():
        if instance_id in (row.instance_ids or []):
            return row
    return None


def _log_db_action(
    db: Session,
    resource_id: str,
    action: str,
    status: str,
    message: str,
    estimated_savings_usd: Optional[float] = None,
) -> None:
    db.add(
        SchedulerActionLog(
            resource_id=resource_id,
            action=action,
            status=status,
            message=message[:2000] if message else None,
            estimated_savings_usd=estimated_savings_usd,
        )
    )
    db.commit()


@router.get("/resources")
async def get_schedulable_resources(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = get_scheduler_service(db)
    print("Connected to AWS region:", service.region)
    resources = service.get_schedulable_resources()
    payload: Dict[str, Any] = {"resources": resources}
    ec2_only = [r for r in resources if r.get("resource_type") == "ec2"]
    if len(ec2_only) == 0 and not resources:
        payload["message"] = "No running or stopped EC2 instances found in this region. Check AWS_REGION and credentials."
    return payload


@router.post("/analyze/{instance_id}")
async def analyze_instance_metrics(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
    db: Session = Depends(get_db),
):
    service = get_scheduler_service(db)
    return {"schedules": _merged_schedules(db, service)}


@router.get("/list")
async def list_schedules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Same as GET /schedules (production + legacy in-memory)."""
    service = get_scheduler_service(db)
    return {"schedules": _merged_schedules(db, service)}


@router.post("/create")
async def create_production_schedule(
    body: ProductionScheduleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a DB-backed schedule and register APScheduler cron jobs.
    Supports bulk instance_ids or single instance_id.
    """
    ids = list(body.instance_ids or [])
    if body.instance_id and body.instance_id.strip():
        ids.append(body.instance_id.strip())
    ids = [i.strip() for i in ids if i and str(i).strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="Provide instance_id or instance_ids")

    pattern = (body.days_pattern or "all").lower().strip()
    if pattern not in ("all", "weekdays", "weekends"):
        raise HTTPException(status_code=400, detail="days_pattern must be all, weekdays, or weekends")

    public_id = str(uuid.uuid4())
    row = Ec2Schedule(
        public_id=public_id,
        instance_ids=ids,
        start_time=body.start_time[:8],
        stop_time=body.stop_time[:8],
        timezone=body.timezone or "UTC",
        days_pattern=pattern,
        enabled=body.enabled,
        estimated_hourly_usd=body.estimated_hourly_usd,
    )
    db.add(row)
    db.commit()
    reload_schedule_jobs()
    return {"status": "created", "schedule": _ec2_row_to_schedule_dict(row)}


@router.delete("/remove/{schedule_id}")
async def remove_schedule(
    schedule_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(Ec2Schedule).filter(Ec2Schedule.public_id == schedule_id).first()
    if row:
        db.delete(row)
        db.commit()
        reload_schedule_jobs()
        return {"status": "deleted", "id": schedule_id}
    service = get_scheduler_service(db)
    if service.delete_schedule(schedule_id):
        return {"status": "deleted", "id": schedule_id}
    raise HTTPException(status_code=404, detail="Schedule not found")


@router.get("/settings")
async def get_scheduler_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"execution_enabled": is_scheduler_execution_enabled(db)}


@router.put("/settings")
async def put_scheduler_settings(
    body: SchedulerSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    set_scheduler_execution_enabled(body.execution_enabled)
    return {"execution_enabled": is_scheduler_execution_enabled(db)}


@router.get("/actions/history")
async def get_action_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = get_scheduler_service(db)
    mem = service.get_action_history()
    rows = (
        db.query(SchedulerActionLog)
        .order_by(SchedulerActionLog.created_at.desc())
        .limit(200)
        .all()
    )
    db_hist = [
        {
            "id": str(r.id),
            "resource_id": r.resource_id,
            "instance_id": r.resource_id,
            "action": r.action,
            "timestamp": r.created_at.isoformat() if r.created_at else "",
            "status": r.status,
            "message": r.message or "",
            "estimated_savings_usd": r.estimated_savings_usd,
        }
        for r in rows
    ]
    return {"history": db_hist + mem[:100]}


@router.get("/cost-insights")
async def scheduler_cost_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = get_scheduler_service(db)
    session = service.session
    region = service.region
    daily = try_daily_costs_by_service(session, region)
    return {
        "region": region,
        "daily_by_service": daily or [],
        "note": None if daily else "Cost Explorer data unavailable (enable ce:GetCostAndUsage or use pricing estimates on resources).",
    }


@router.get("/smart-recommendations")
async def smart_recommendations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Combine idle + cost signals for schedule suggestions."""
    service = get_scheduler_service(db)
    resources = service.get_schedulable_resources()
    recs: List[Dict[str, Any]] = []
    for r in resources:
        if r.get("resource_type") != "ec2":
            continue
        if r.get("do_not_schedule"):
            continue
        if r.get("cost_stop_suggested") or (r.get("avg_cpu_24h", 100) < 5 and r.get("state") == "running"):
            recs.append(
                {
                    "instance_id": r.get("instance_id"),
                    "name": r.get("name"),
                    "reason": "Idle at night / low CPU — schedule stop during off-hours",
                    "suggested_stop_time": "20:00",
                    "suggested_start_time": "08:00",
                    "days_pattern": "weekdays",
                    "estimated_hourly_cost": r.get("estimated_hourly_cost", r.get("hourly_cost")),
                }
            )
    return {"recommendations": recs}


@router.post("/schedules")
async def create_schedule(
    request: ScheduleCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
    db: Session = Depends(get_db),
):
    row = db.query(Ec2Schedule).filter(Ec2Schedule.public_id == schedule_id).first()
    if row:
        data = request.dict(exclude_unset=True)
        if "start_time" in data:
            row.start_time = data["start_time"][:8]
        if "stop_time" in data:
            row.stop_time = data["stop_time"][:8]
        if "enabled" in data:
            row.enabled = bool(data["enabled"])
        db.commit()
        reload_schedule_jobs()
        return _ec2_row_to_schedule_dict(row)

    service = get_scheduler_service(db)
    updates = request.dict(exclude_unset=True)
    schedule = service.update_schedule(schedule_id=schedule_id, data=updates)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await remove_schedule(schedule_id, current_user, db)


@router.get("/savings")
async def get_projected_savings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = get_scheduler_service(db)
    summary = service.get_savings_summary()
    db_rows = db.query(Ec2Schedule).all()
    db_active = sum(1 for r in db_rows if r.enabled)
    db_monthly = sum(estimated_monthly_for_schedule(r) for r in db_rows if r.enabled)

    realized_q = db.query(func.coalesce(func.sum(SchedulerActionLog.estimated_savings_usd), 0.0)).filter(
        SchedulerActionLog.status == "success",
    )
    db_realized = float(realized_q.scalar() or 0.0)

    success_db = db.query(func.count(SchedulerActionLog.id)).filter(SchedulerActionLog.status == "success").scalar() or 0
    failed_db = db.query(func.count(SchedulerActionLog.id)).filter(SchedulerActionLog.status == "failed").scalar() or 0
    db_actions = int(success_db) + int(failed_db)

    est_month = round(float(summary.get("estimated_monthly_savings", 0.0)) + float(db_monthly), 2)
    mem_realized = float(summary.get("total_realized_savings", 0.0))

    if db_actions > 0:
        success_rate = round((float(success_db) / float(db_actions)) * 100.0, 1)
        actions_executed = db_actions
    else:
        success_rate = float(summary.get("success_rate", 100.0))
        actions_executed = int(summary.get("actions_executed", 0))

    return {
        "active_schedules": int(summary.get("active_schedules", 0)) + db_active,
        "total_schedules": int(summary.get("total_schedules", 0)) + len(db_rows),
        "estimated_monthly_savings": est_month,
        "estimated_annual_savings": round(est_month * 12.0, 2),
        "total_realized_savings": round(db_realized + mem_realized, 2),
        "realized_savings_logged_usd": round(db_realized, 2),
        "actions_executed": actions_executed,
        "success_rate": success_rate,
    }


@router.post("/actions/execute")
async def execute_scheduler_action(
    request: SchedulerActionExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rid = (request.resource_id or "").strip()
    if rid.startswith("i-") and len(rid) < 10:
        raise HTTPException(status_code=400, detail="Invalid EC2 instance ID format.")

    service = get_scheduler_service(db)
    result = service.execute_action(instance_id=rid, action=request.action_type)
    savings: Optional[float] = None
    if result.get("status") == "success" and (request.action_type or "").strip().lower() == "stop":
        sch = _find_ec2_schedule_for_instance(db, rid)
        if sch:
            savings = estimated_savings_for_schedule_stop(sch)
    _log_db_action(
        db,
        rid,
        request.action_type,
        result.get("status", "unknown"),
        result.get("message", ""),
        estimated_savings_usd=savings,
    )
    return result
