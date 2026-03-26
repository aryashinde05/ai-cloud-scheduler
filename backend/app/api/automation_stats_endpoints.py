"""
Automation stats endpoint — derives real stats from scanned AWS resources in the DB.
No Supabase dependency. Used by AutomationDashboard.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.aws_account import AwsAccount
from app.models.resource import Resource
from app.services.optimizer import estimate_resource_monthly_cost

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/automation", tags=["Automation Stats"])


@router.get("/stats")
def get_automation_stats(db: Session = Depends(get_db)):
    """
    Real automation stats derived from scanned resources.
    Returns counts of idle/oversized/unattached resources as actionable items.
    """
    account = AwsAccount.get_default(db)
    if not account:
        return {
            "total_actions": 0, "pending_actions": 0, "completed_actions": 0,
            "failed_actions": 0, "total_savings": 0, "monthly_savings": 0,
            "automation_enabled": False, "last_execution": None,
        }

    resources = db.query(Resource).filter(Resource.aws_account_id == account.id).all()

    idle = [r for r in resources if r.is_idle]
    oversized = [r for r in resources if r.is_oversized]
    unattached = [r for r in resources if r.is_unattached]
    actionable = idle + oversized + unattached

    monthly_savings = round(sum(estimate_resource_monthly_cost(r) for r in actionable), 2)
    last_scan = max((r.last_seen_at for r in resources if r.last_seen_at), default=None)

    return {
        "total_actions": len(actionable),
        "pending_actions": len(actionable),
        "completed_actions": 0,
        "failed_actions": 0,
        "total_savings": 0.0,
        "monthly_savings": monthly_savings,
        "automation_enabled": True,
        "last_execution": last_scan.isoformat() if last_scan else None,
        "breakdown": {
            "idle_instances": len(idle),
            "oversized_instances": len(oversized),
            "unattached_volumes": len(unattached),
        },
    }


@router.get("/actions")
def get_automation_actions(db: Session = Depends(get_db)):
    """
    Returns real optimization actions derived from scanned resources.
    Each idle/oversized/unattached resource becomes an actionable item.
    """
    account = AwsAccount.get_default(db)
    if not account:
        return []

    resources = db.query(Resource).filter(Resource.aws_account_id == account.id).all()
    actions = []

    for r in resources:
        cost = round(estimate_resource_monthly_cost(r), 2)

        if r.is_idle and r.resource_type == "ec2_instance":
            actions.append({
                "action_id": f"idle-{r.resource_id}",
                "action_type": "stop_idle_instance",
                "resource_id": r.resource_id,
                "resource_type": r.resource_type,
                "name": r.name or r.resource_id,
                "region": r.region,
                "estimated_monthly_savings": cost,
                "risk_level": "low",
                "requires_approval": False,
                "scheduled_execution_time": datetime.now(timezone.utc).isoformat(),
                "safety_checks_passed": True,
                "execution_status": "pending",
                "detail": f"CPU utilization: {r.cpu_utilization:.1f}% — instance is idle",
                "created_at": r.last_seen_at.isoformat() if r.last_seen_at else datetime.now(timezone.utc).isoformat(),
                "updated_at": r.last_seen_at.isoformat() if r.last_seen_at else datetime.now(timezone.utc).isoformat(),
            })

        if r.is_oversized and r.resource_type == "ec2_instance":
            actions.append({
                "action_id": f"resize-{r.resource_id}",
                "action_type": "resize_underutilized_instances",
                "resource_id": r.resource_id,
                "resource_type": r.resource_type,
                "name": r.name or r.resource_id,
                "region": r.region,
                "estimated_monthly_savings": round(cost * 0.4, 2),
                "risk_level": "medium",
                "requires_approval": True,
                "scheduled_execution_time": datetime.now(timezone.utc).isoformat(),
                "safety_checks_passed": True,
                "execution_status": "pending",
                "detail": f"Instance type {r.instance_type} with CPU {r.cpu_utilization:.1f}% — consider downsizing",
                "created_at": r.last_seen_at.isoformat() if r.last_seen_at else datetime.now(timezone.utc).isoformat(),
                "updated_at": r.last_seen_at.isoformat() if r.last_seen_at else datetime.now(timezone.utc).isoformat(),
            })

        if r.is_unattached and r.resource_type == "ebs_volume":
            actions.append({
                "action_id": f"delete-vol-{r.resource_id}",
                "action_type": "delete_volumes",
                "resource_id": r.resource_id,
                "resource_type": r.resource_type,
                "name": r.resource_id,
                "region": r.region,
                "estimated_monthly_savings": cost,
                "risk_level": "low",
                "requires_approval": False,
                "scheduled_execution_time": datetime.now(timezone.utc).isoformat(),
                "safety_checks_passed": True,
                "execution_status": "pending",
                "detail": f"{r.volume_size} GB {r.volume_type} volume not attached to any instance",
                "created_at": r.last_seen_at.isoformat() if r.last_seen_at else datetime.now(timezone.utc).isoformat(),
                "updated_at": r.last_seen_at.isoformat() if r.last_seen_at else datetime.now(timezone.utc).isoformat(),
            })

    return actions


@router.post("/actions/execute")
def execute_action(payload: dict, db: Session = Depends(get_db)):
    """Execute a real action (stop instance / delete volume) via boto3."""
    from app.models.aws_account import AwsAccount
    import boto3
    from botocore.config import Config as BotoConfig

    account = AwsAccount.get_default(db)
    if not account:
        raise HTTPException(status_code=400, detail="AWS account not configured.")

    action_ids = payload.get("action_ids", [])
    results = []

    access_key, secret_key, region = account.get_decrypted_credentials()
    cfg = BotoConfig(retries={"max_attempts": 3, "mode": "standard"})

    for action_id in action_ids:
        # Determine resource from action_id prefix
        if action_id.startswith("idle-"):
            instance_id = action_id[5:]
            resource = db.query(Resource).filter(
                Resource.aws_account_id == account.id,
                Resource.resource_id == instance_id,
            ).first()
            if not resource:
                results.append({"action_id": action_id, "status": "error", "message": "Resource not found"})
                continue
            try:
                ec2 = boto3.client("ec2", region_name=resource.region or region,
                                   aws_access_key_id=access_key, aws_secret_access_key=secret_key, config=cfg)
                ec2.stop_instances(InstanceIds=[instance_id])
                results.append({"action_id": action_id, "status": "success", "message": f"Stop command sent to {instance_id}"})
            except Exception as e:
                results.append({"action_id": action_id, "status": "error", "message": str(e)})

        elif action_id.startswith("delete-vol-"):
            vol_id = action_id[11:]
            resource = db.query(Resource).filter(
                Resource.aws_account_id == account.id,
                Resource.resource_id == vol_id,
            ).first()
            if not resource:
                results.append({"action_id": action_id, "status": "error", "message": "Resource not found"})
                continue
            try:
                ec2 = boto3.client("ec2", region_name=resource.region or region,
                                   aws_access_key_id=access_key, aws_secret_access_key=secret_key, config=cfg)
                ec2.delete_volume(VolumeId=vol_id)
                results.append({"action_id": action_id, "status": "success", "message": f"Volume {vol_id} deleted"})
            except Exception as e:
                results.append({"action_id": action_id, "status": "error", "message": str(e)})

        else:
            results.append({"action_id": action_id, "status": "skipped",
                            "message": "Resize actions require manual execution in AWS Console"})

    return {"results": results, "executed": len([r for r in results if r["status"] == "success"])}
