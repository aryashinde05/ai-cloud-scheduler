"""
Reports & Analytics endpoints — built from real DB resource data + AWS Cost Explorer.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import boto3
from botocore.config import Config as BotoConfig
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.aws_account import AwsAccount
from app.models.resource import Resource
from app.services.optimizer import estimate_resource_monthly_cost

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])

BOTO_CFG = BotoConfig(retries={"max_attempts": 3, "mode": "standard"}, connect_timeout=8, read_timeout=15)


def _make_session(account: AwsAccount) -> boto3.Session:
    access_key, secret_key, region = account.get_decrypted_credentials()
    return boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )


def _get_cost_explorer_data(session: boto3.Session, days: int = 30) -> dict:
    """Fetch cost data from AWS Cost Explorer."""
    try:
        ce = session.client("ce", region_name="us-east-1", config=BOTO_CFG)
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=days)

        resp = ce.get_cost_and_usage(
            TimePeriod={"Start": str(start), "End": str(end)},
            Granularity="DAILY",
            Metrics=["BlendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        daily: dict = {}
        service_totals: dict = {}

        for result in resp.get("ResultsByTime", []):
            date = result["TimePeriod"]["Start"]
            day_total = 0.0
            for group in result.get("Groups", []):
                svc = group["Keys"][0]
                cost = float(group["Metrics"]["BlendedCost"]["Amount"])
                day_total += cost
                service_totals[svc] = service_totals.get(svc, 0) + cost
            daily[date] = round(day_total, 4)

        return {"daily": daily, "by_service": service_totals}
    except Exception as e:
        logger.warning("Cost Explorer unavailable: %s", e)
        return {"daily": {}, "by_service": {}}


@router.get("/summary")
def get_reports_summary(db: Session = Depends(get_db)):
    """High-level summary for the Reports page header cards."""
    account = AwsAccount.get_default(db)
    if not account:
        raise HTTPException(status_code=400, detail="AWS account not configured.")

    resources = db.query(Resource).filter(Resource.aws_account_id == account.id).all()
    session = _make_session(account)
    ce_data = _get_cost_explorer_data(session, days=30)

    total_cost = sum(ce_data["daily"].values())
    idle_count = sum(1 for r in resources if r.is_idle)
    oversized_count = sum(1 for r in resources if r.is_oversized)
    unattached_count = sum(1 for r in resources if r.is_unattached)
    potential_savings = sum(
        estimate_resource_monthly_cost(r)
        for r in resources
        if r.is_idle or r.is_oversized or r.is_unattached
    )

    return {
        "total_monthly_cost": round(total_cost, 2),
        "resource_count": len(resources),
        "optimization_opportunities": idle_count + oversized_count + unattached_count,
        "potential_monthly_savings": round(potential_savings, 2),
        "data_freshness": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/cost-trend")
def get_cost_trend(days: int = Query(30, ge=7, le=90), db: Session = Depends(get_db)):
    """Daily cost trend from Cost Explorer."""
    account = AwsAccount.get_default(db)
    if not account:
        raise HTTPException(status_code=400, detail="AWS account not configured.")

    session = _make_session(account)
    ce_data = _get_cost_explorer_data(session, days=days)

    trend = [
        {"date": date, "cost": round(cost, 2)}
        for date, cost in sorted(ce_data["daily"].items())
    ]
    return {"trend": trend, "total": round(sum(ce_data["daily"].values()), 2), "days": days}


@router.get("/service-breakdown")
def get_service_breakdown(days: int = Query(30, ge=7, le=90), db: Session = Depends(get_db)):
    """Cost breakdown by AWS service."""
    account = AwsAccount.get_default(db)
    if not account:
        raise HTTPException(status_code=400, detail="AWS account not configured.")

    session = _make_session(account)
    ce_data = _get_cost_explorer_data(session, days=days)

    total = sum(ce_data["by_service"].values())
    breakdown = sorted(
        [
            {
                "service": svc,
                "cost": round(cost, 2),
                "percentage": round((cost / total) * 100, 1) if total else 0,
            }
            for svc, cost in ce_data["by_service"].items()
            if cost > 0.01
        ],
        key=lambda x: -x["cost"],
    )
    return {"breakdown": breakdown, "total": round(total, 2)}


@router.get("/optimization-opportunities")
def get_optimization_opportunities(db: Session = Depends(get_db)):
    """List all real optimization opportunities from scanned resources."""
    account = AwsAccount.get_default(db)
    if not account:
        raise HTTPException(status_code=400, detail="AWS account not configured.")

    resources = db.query(Resource).filter(Resource.aws_account_id == account.id).all()
    opportunities = []

    for r in resources:
        cost = round(estimate_resource_monthly_cost(r), 2)

        if r.is_idle and r.resource_type == "ec2_instance":
            opportunities.append({
                "resource_id": r.resource_id,
                "name": r.name or r.resource_id,
                "resource_type": "EC2 Instance",
                "region": r.region,
                "issue": "Idle instance",
                "detail": f"CPU utilization: {r.cpu_utilization:.1f}%",
                "action": "Stop or terminate this instance",
                "monthly_savings": cost,
                "risk": "low",
            })

        if r.is_oversized and r.resource_type == "ec2_instance":
            opportunities.append({
                "resource_id": r.resource_id,
                "name": r.name or r.resource_id,
                "resource_type": "EC2 Instance",
                "region": r.region,
                "issue": "Oversized instance",
                "detail": f"Type: {r.instance_type}, CPU: {r.cpu_utilization:.1f}%",
                "action": "Downsize to a smaller instance type",
                "monthly_savings": round(cost * 0.4, 2),
                "risk": "medium",
            })

        if r.is_unattached and r.resource_type == "ebs_volume":
            opportunities.append({
                "resource_id": r.resource_id,
                "name": r.resource_id,
                "resource_type": "EBS Volume",
                "region": r.region,
                "issue": "Unattached volume",
                "detail": f"{r.volume_size} GB {r.volume_type} volume not attached",
                "action": "Delete or snapshot and delete this volume",
                "monthly_savings": cost,
                "risk": "low",
            })

    total_savings = round(sum(o["monthly_savings"] for o in opportunities), 2)
    return {
        "opportunities": opportunities,
        "count": len(opportunities),
        "total_monthly_savings": total_savings,
        "total_annual_savings": round(total_savings * 12, 2),
    }


@router.get("/resource-inventory")
def get_resource_inventory(db: Session = Depends(get_db)):
    """Full resource inventory from DB."""
    account = AwsAccount.get_default(db)
    if not account:
        raise HTTPException(status_code=400, detail="AWS account not configured.")

    resources = db.query(Resource).filter(Resource.aws_account_id == account.id).all()

    by_type: dict = {}
    by_region: dict = {}
    by_state: dict = {}

    for r in resources:
        by_type[r.resource_type] = by_type.get(r.resource_type, 0) + 1
        region = r.region or "unknown"
        by_region[region] = by_region.get(region, 0) + 1
        state = r.state or "unknown"
        by_state[state] = by_state.get(state, 0) + 1

    return {
        "total": len(resources),
        "by_type": [{"type": k, "count": v} for k, v in by_type.items()],
        "by_region": [{"region": k, "count": v} for k, v in sorted(by_region.items(), key=lambda x: -x[1])],
        "by_state": [{"state": k, "count": v} for k, v in by_state.items()],
        "last_scan": max((r.last_seen_at for r in resources if r.last_seen_at), default=None),
    }
