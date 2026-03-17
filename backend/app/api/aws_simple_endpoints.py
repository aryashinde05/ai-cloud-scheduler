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
    instance_type: str | None = None
    state: str | None = None
    cpu_utilization: float | None = None
    volume_size: int | None = None
    is_idle: bool
    is_oversized: bool
    is_unattached: bool
    monthly_cost: float | None = None  # computed for display

    class Config:
        orm_mode = True


router = APIRouter(prefix="/api/v1/aws", tags=["AWS Connection"])


@router.get("/status")
def aws_status(db: Session = Depends(get_db)):
    """Return whether AWS account is configured. Used by frontend to gate access."""
    account = AwsAccount.get_default(db)
    return {"connected": account is not None, "region": account.region if account else None}


@router.post("/connect")
def connect_aws_account(payload: AwsConnectRequest, db: Session = Depends(get_db)):
    """
    Store AWS account credentials (encrypted) for subsequent Boto3 calls.
    """
    region = (payload.region or "").strip()
    # Guard against typos like "ap-sutheast-2" (missing 'o')
    valid_regions = set(boto3.session.Session().get_available_regions("ec2"))
    if region not in valid_regions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid AWS region '{region}'. Example: ap-southeast-2, us-east-1.",
        )
    account = AwsAccount.create_or_update_default(
        db=db,
        access_key=(payload.access_key or "").strip(),
        secret_key=(payload.secret_key or "").strip(),
        region=region,
    )
    return {"message": "AWS account connected successfully", "account_id": account.id}


@router.get("/resources", response_model=List[ResourceOut])
def get_resources(db: Session = Depends(get_db)):
    account = AwsAccount.get_default(db)
    if not account:
        raise HTTPException(status_code=400, detail="AWS account not configured. Connect first.")

    try:
        aws_collector.refresh_resources(db=db, account=account)
        resources = (
            db.query(Resource)
            .filter(Resource.aws_account_id == account.id)
            .order_by(Resource.resource_type, Resource.resource_id)
            .all()
        )
        return [
            ResourceOut(
                **{k: getattr(r, k) for k in ["id", "aws_account_id", "resource_id", "resource_type", "instance_type", "state", "cpu_utilization", "volume_size", "is_idle", "is_oversized", "is_unattached"]},
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
        # Assuming resources are already refreshed via /resources or background job
        resources = (
            db.query(Resource)
            .filter(Resource.aws_account_id == account.id, Resource.resource_type == "ec2_instance")
            .all()
        )
        return [
            ResourceOut(
                **{k: getattr(r, k) for k in ["id", "aws_account_id", "resource_id", "resource_type", "instance_type", "state", "cpu_utilization", "volume_size", "is_idle", "is_oversized", "is_unattached"]},
                monthly_cost=round(optimizer.estimate_resource_monthly_cost(r), 2),
            )
            for r in resources
        ]
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"Backend error: {e}")
