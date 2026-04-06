from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import boto3

from app.database.session import get_db
from app.models.aws_account import AwsAccount
from app.models.resource import Resource
from app.services import aws_collector, optimizer


class AwsConnectRequest(BaseModel):
    access_key: str
    secret_key: str
    region: str


class ResourceOut(BaseModel):
    id: int
    aws_account_id: int
    resource_id: str
    resource_type: str
    region: str | None = None
    name: str | None = None
    instance_type: str | None = None
    state: str | None = None
    cpu_utilization: float | None = None
    volume_size: int | None = None
    is_idle: bool
    is_oversized: bool
    is_unattached: bool
    monthly_cost: float | None = None

    class Config:
        # Pydantic v2: replace orm_mode with from_attributes
        from_attributes = True


router = APIRouter(prefix="/api/v1/aws", tags=["AWS Connection"])


@router.get("/status")
def aws_status(db: Session = Depends(get_db)):
    """Return whether AWS account is configured. Used by frontend to gate access."""
    account = AwsAccount.get_default(db)
    if not account:
        return {
            "connected": False,
            "region": None,
            "account_id": None,
        }

    # Treat the account as connected only when decrypted credentials are non-empty.
    try:
        access_key, secret_key, _region = account.get_decrypted_credentials()
        has_creds = bool(access_key and secret_key)
    except Exception:
        has_creds = False

    return {
        "connected": has_creds,
        "region": account.region if account else None,
        "account_id": str(account.aws_account_id) if account and hasattr(account, 'aws_account_id') else str(account.id) if account else None,
    }


@router.post("/connect")
def connect_aws_account(payload: AwsConnectRequest, db: Session = Depends(get_db)):
    """
    Store AWS account credentials (encrypted) for subsequent Boto3 calls.
    """
    region = (payload.region or "").strip()
    access_key = (payload.access_key or "").strip()
    secret_key = (payload.secret_key or "").strip()

    # Fail fast: avoid saving empty credentials that later cause long AWS timeouts.
    if not access_key or not secret_key:
        raise HTTPException(
            status_code=400,
            detail="AWS credentials are required (access_key and secret_key).",
        )

    # Guard against typos like "ap-sutheast-2" (missing 'o')
    valid_regions = set(boto3.session.Session().get_available_regions("ec2"))
    if region not in valid_regions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid AWS region '{region}'. Example: ap-southeast-2, us-east-1.",
        )
    account = AwsAccount.create_or_update_default(
        db=db,
        access_key=access_key,
        secret_key=secret_key,
        region=region,
    )
    return {"message": "AWS account connected successfully", "account_id": account.id}


@router.get("/resources", response_model=List[ResourceOut])
def get_resources(region: str = None, db: Session = Depends(get_db)):
    """
    Refresh and return resources.

    Demo-safe default:
    - if `?region` is omitted, scan only the account's configured default region.
    - pass `?region=all` to scan ALL regions.
    - pass `?region=us-east-1` to scan a single region.
    """
    account = AwsAccount.get_default(db)
    if not account:
        raise HTTPException(status_code=400, detail="AWS account not configured. Connect first.")

    try:
        # When the frontend uses selectedRegion="all", it omits the query param.
        # In that case, avoid scanning ALL regions (can exceed frontend timeouts).
        if not region:
            regions = [account.region]
        elif region == "all":
            regions = None
        else:
            regions = [region]

        aws_collector.refresh_resources(db=db, account=account, regions=regions)
        query = db.query(Resource).filter(Resource.aws_account_id == account.id)
        if region and region != "all":
            query = query.filter(Resource.region == region)
        resources = query.order_by(Resource.resource_type, Resource.resource_id).all()
        return [
            ResourceOut(
                **{k: getattr(r, k) for k in ["id", "aws_account_id", "resource_id", "resource_type", "region", "name", "instance_type", "state", "cpu_utilization", "volume_size", "is_idle", "is_oversized", "is_unattached"]},
                monthly_cost=round(optimizer.estimate_resource_monthly_cost(r), 2),
            )
            for r in resources
        ]
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to refresh AWS resources: {e}")


@router.get("/instances", response_model=List[ResourceOut])
def get_instances(db: Session = Depends(get_db)):
    account = AwsAccount.get_default(db)
    if not account:
        raise HTTPException(status_code=400, detail="AWS account not configured. Connect first.")

    try:
        resources = (
            db.query(Resource)
            .filter(Resource.aws_account_id == account.id, Resource.resource_type == "ec2_instance")
            .all()
        )
        return [
            ResourceOut(
                **{k: getattr(r, k) for k in ["id", "aws_account_id", "resource_id", "resource_type", "region", "name", "instance_type", "state", "cpu_utilization", "volume_size", "is_idle", "is_oversized", "is_unattached"]},
                monthly_cost=round(optimizer.estimate_resource_monthly_cost(r), 2),
            )
            for r in resources
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backend error: {e}")


@router.get("/rds", response_model=List[ResourceOut])
def get_rds_instances(region: str = None, db: Session = Depends(get_db)):
    """Fetch real RDS instances (demo-safe default: only account default region)."""
    account = AwsAccount.get_default(db)
    if not account:
        raise HTTPException(status_code=400, detail="AWS account not configured.")

    import boto3
    from botocore.config import Config as BotoConfig
    from datetime import datetime, timedelta

    ALL_REGIONS = [
        "us-east-1", "us-east-2", "us-west-1", "us-west-2",
        "eu-west-1", "eu-west-2", "eu-central-1",
        "ap-southeast-1", "ap-southeast-2", "ap-northeast-1",
        "ap-south-1", "sa-east-1", "ca-central-1",
    ]
    cfg = BotoConfig(retries={"max_attempts": 2, "mode": "standard"}, connect_timeout=5, read_timeout=10)
    access_key, secret_key, stored_region = account.get_decrypted_credentials()
    session = boto3.Session(aws_access_key_id=access_key, aws_secret_access_key=secret_key)

    results = []
    target_regions = ALL_REGIONS if region == "all" else [region] if region else [account.region]
    for region in target_regions:
        try:
            rds_client = session.client("rds", region_name=region, config=cfg)
            cw = session.client("cloudwatch", region_name=region, config=cfg)
            paginator = rds_client.get_paginator("describe_db_instances")
            for page in paginator.paginate():
                for db_inst in page.get("DBInstances", []):
                    db_id = db_inst["DBInstanceIdentifier"]
                    # Get CPU from CloudWatch
                    cpu = None
                    try:
                        now = datetime.utcnow()
                        resp = cw.get_metric_statistics(
                            Namespace="AWS/RDS", MetricName="CPUUtilization",
                            Dimensions=[{"Name": "DBInstanceIdentifier", "Value": db_id}],
                            StartTime=now - timedelta(hours=24), EndTime=now,
                            Period=3600, Statistics=["Average"],
                        )
                        dps = resp.get("Datapoints", [])
                        if dps:
                            cpu = round(sum(d["Average"] for d in dps) / len(dps), 1)
                    except Exception:
                        pass

                    results.append({
                        "id": 0, "aws_account_id": account.id,
                        "resource_id": db_id,
                        "resource_type": "rds_instance",
                        "region": region,
                        "name": db_id,
                        "instance_type": db_inst.get("DBInstanceClass"),
                        "state": db_inst.get("DBInstanceStatus"),
                        "cpu_utilization": cpu,
                        "volume_size": db_inst.get("AllocatedStorage"),
                        "is_idle": cpu is not None and cpu < 2.0,
                        "is_oversized": cpu is not None and cpu < 10.0,
                        "is_unattached": False,
                        "monthly_cost": None,
                        "engine": db_inst.get("Engine"),
                        "connections": None,
                    })
        except Exception:
            continue

    return results
    """Remove the stored AWS account credentials."""
    account = AwsAccount.get_default(db)
    if not account:
        raise HTTPException(status_code=404, detail="No AWS account connected.")
    db.delete(account)
    db.commit()
    return {"message": "AWS account disconnected successfully"}


@router.get("/dashboard")
def get_dashboard_summary(db: Session = Depends(get_db)):
    """Lightweight dashboard summary for the onboarding success screen."""
    account = AwsAccount.get_default(db)
    if not account:
        return {"finops_summary": None}

    resources = db.query(Resource).filter(Resource.aws_account_id == account.id).all()
    idle_count = sum(1 for r in resources if r.is_idle)
    oversized_count = sum(1 for r in resources if r.is_oversized)
    unattached_count = sum(1 for r in resources if r.is_unattached)

    total_cost = sum(optimizer.estimate_resource_monthly_cost(r) for r in resources)
    # Savings potential is roughly the cost of idle/oversized/unattached resources
    savings_potential = sum(optimizer.estimate_resource_monthly_cost(r) for r in resources if r.is_idle or r.is_oversized or r.is_unattached)

    return {
        "finops_summary": {
            "totalMonthlyCost": round(total_cost, 2),
            "monthlySavings": round(savings_potential, 2),
            "optimizationOpportunities": idle_count + oversized_count + unattached_count,
            "resourceCount": len(resources),
            "forecastedCost": round(total_cost * 1.05, 2), # Simplified 5% buffer for forecast
        }
    }
