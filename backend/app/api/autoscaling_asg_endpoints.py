"""
Auto Scaling Group CPU-based scaling: SimpleScaling policies + CloudWatch alarms.
"""

from __future__ import annotations

import os
import uuid
import logging
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.aws_account import AwsAccount
from app.models.ec2_schedule_models import AsgScalingRule

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/autoscaling", tags=["Auto Scaling (ASG)"])


def _default_region() -> str:
    return (
        os.getenv("AWS_REGION")
        or os.getenv("AWS_DEFAULT_REGION")
        or "ap-south-1"
    )


def _boto_session(db: Session) -> Tuple[Any, str]:
    account = AwsAccount.get_default(db)
    region = _default_region()
    if account:
        try:
            ak, sk, reg = account.get_decrypted_credentials()
            if reg:
                region = reg
            if ak and sk:
                return boto3.Session(aws_access_key_id=ak, aws_secret_access_key=sk, region_name=region), region
        except Exception:
            pass
    return boto3.Session(region_name=region), region


class CreateAsgRuleRequest(BaseModel):
    asg_name: str = Field(..., min_length=1, max_length=255)
    min_size: int = Field(..., ge=0)
    max_size: int = Field(..., ge=1)
    scale_up_cpu: int = Field(70, ge=1, le=99, description="Scale out when average CPU exceeds this %")
    scale_down_cpu: int = Field(20, ge=1, le=99, description="Scale in when average CPU below this %")
    region: Optional[str] = Field(None, description="Override region (default from env or connected account)")


class AsgRuleOut(BaseModel):
    public_id: str
    asg_name: str
    region: str
    min_size: int
    max_size: int
    scale_up_cpu: int
    scale_down_cpu: int
    scale_up_policy_arn: Optional[str] = None
    scale_down_policy_arn: Optional[str] = None
    alarm_high_name: Optional[str] = None
    alarm_low_name: Optional[str] = None

    class Config:
        from_attributes = True


@router.post("/create-rule", response_model=AsgRuleOut)
def create_asg_rule(payload: CreateAsgRuleRequest, db: Session = Depends(get_db)):
    if payload.min_size > payload.max_size:
        raise HTTPException(status_code=400, detail="min_size cannot exceed max_size")
    if payload.scale_down_cpu >= payload.scale_up_cpu:
        raise HTTPException(status_code=400, detail="scale_down_cpu must be less than scale_up_cpu")

    session, region = _boto_session(db)
    if payload.region:
        region = payload.region.strip()
        session = boto3.Session(region_name=region)

    autoscaling = session.client("autoscaling", region_name=region)
    cw = session.client("cloudwatch", region_name=region)

    public_id = str(uuid.uuid4())
    prefix = f"finops-{public_id[:8]}"

    try:
        autoscaling.update_auto_scaling_group(
            AutoScalingGroupName=payload.asg_name,
            MinSize=payload.min_size,
            MaxSize=payload.max_size,
        )
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        msg = e.response.get("Error", {}).get("Message", str(e))
        if code == "ValidationError":
            raise HTTPException(status_code=400, detail=msg)
        raise HTTPException(status_code=502, detail=f"AWS AutoScaling: {msg}")

    up_name = f"{prefix}-scale-up"
    down_name = f"{prefix}-scale-down"
    alarm_hi = f"{prefix}-cpu-high"
    alarm_lo = f"{prefix}-cpu-low"

    try:
        up = autoscaling.put_scaling_policy(
            AutoScalingGroupName=payload.asg_name,
            PolicyName=up_name,
            PolicyType="SimpleScaling",
            AdjustmentType="ChangeInCapacity",
            ScalingAdjustment=1,
            Cooldown=300,
        )
        down = autoscaling.put_scaling_policy(
            AutoScalingGroupName=payload.asg_name,
            PolicyName=down_name,
            PolicyType="SimpleScaling",
            AdjustmentType="ChangeInCapacity",
            ScalingAdjustment=-1,
            Cooldown=300,
        )
        up_arn = up["PolicyARN"]
        down_arn = down["PolicyARN"]

        cw.put_metric_alarm(
            AlarmName=alarm_hi,
            ComparisonOperator="GreaterThanThreshold",
            EvaluationPeriods=2,
            MetricName="CPUUtilization",
            Namespace="AWS/EC2",
            Period=300,
            Statistic="Average",
            Threshold=float(payload.scale_up_cpu),
            ActionsEnabled=True,
            AlarmActions=[up_arn],
            Dimensions=[{"Name": "AutoScalingGroupName", "Value": payload.asg_name}],
            TreatMissingData="notBreaching",
        )
        cw.put_metric_alarm(
            AlarmName=alarm_lo,
            ComparisonOperator="LessThanThreshold",
            EvaluationPeriods=3,
            MetricName="CPUUtilization",
            Namespace="AWS/EC2",
            Period=300,
            Statistic="Average",
            Threshold=float(payload.scale_down_cpu),
            ActionsEnabled=True,
            AlarmActions=[down_arn],
            Dimensions=[{"Name": "AutoScalingGroupName", "Value": payload.asg_name}],
            TreatMissingData="notBreaching",
        )
    except ClientError as e:
        msg = e.response.get("Error", {}).get("Message", str(e))
        raise HTTPException(status_code=502, detail=f"Failed to create policies/alarms: {msg}")

    row = AsgScalingRule(
        public_id=public_id,
        asg_name=payload.asg_name,
        region=region,
        min_size=payload.min_size,
        max_size=payload.max_size,
        scale_up_cpu=payload.scale_up_cpu,
        scale_down_cpu=payload.scale_down_cpu,
        scale_up_policy_arn=up_arn,
        scale_down_policy_arn=down_arn,
        scale_up_policy_name=up_name,
        scale_down_policy_name=down_name,
        alarm_high_arn=None,
        alarm_low_arn=None,
        alarm_high_name=alarm_hi,
        alarm_low_name=alarm_lo,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    print("Connected to AWS region:", region)
    return AsgRuleOut(
        public_id=row.public_id,
        asg_name=row.asg_name,
        region=row.region,
        min_size=row.min_size,
        max_size=row.max_size,
        scale_up_cpu=row.scale_up_cpu,
        scale_down_cpu=row.scale_down_cpu,
        scale_up_policy_arn=row.scale_up_policy_arn,
        scale_down_policy_arn=row.scale_down_policy_arn,
        alarm_high_name=row.alarm_high_name,
        alarm_low_name=row.alarm_low_name,
    )


@router.get("/rules", response_model=Dict[str, Any])
def list_asg_rules(db: Session = Depends(get_db)):
    rows = db.query(AsgScalingRule).order_by(AsgScalingRule.created_at.desc()).all()
    return {
        "rules": [
            {
                "public_id": r.public_id,
                "asg_name": r.asg_name,
                "region": r.region,
                "min_size": r.min_size,
                "max_size": r.max_size,
                "scale_up_cpu": r.scale_up_cpu,
                "scale_down_cpu": r.scale_down_cpu,
                "alarm_high_name": r.alarm_high_name,
                "alarm_low_name": r.alarm_low_name,
            }
            for r in rows
        ],
        "total": len(rows),
    }


@router.delete("/delete-rule/{public_id}")
def delete_asg_rule(public_id: str, db: Session = Depends(get_db)):
    row = db.query(AsgScalingRule).filter(AsgScalingRule.public_id == public_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Rule not found")

    session, region = _boto_session(db)
    if row.region:
        region = row.region
    autoscaling = session.client("autoscaling", region_name=region)
    cw = session.client("cloudwatch", region_name=region)

    try:
        if row.alarm_high_name:
            cw.delete_alarms(AlarmNames=[row.alarm_high_name])
        if row.alarm_low_name:
            cw.delete_alarms(AlarmNames=[row.alarm_low_name])
    except ClientError as e:
        logger.warning("Delete alarms: %s", e)

    for pname in (row.scale_up_policy_name, row.scale_down_policy_name):
        if not pname:
            continue
        try:
            autoscaling.delete_policy(
                AutoScalingGroupName=row.asg_name,
                PolicyName=pname,
            )
        except ClientError as e:
            logger.warning("Delete scaling policy %s: %s", pname, e)

    db.delete(row)
    db.commit()
    return {"status": "deleted", "public_id": public_id}


@router.post("/apply-rule/{public_id}")
def apply_asg_rule(public_id: str, db: Session = Depends(get_db)):
    """Re-apply min/max to ASG (policies/alarms already exist)."""
    row = db.query(AsgScalingRule).filter(AsgScalingRule.public_id == public_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Rule not found")

    session, region = _boto_session(db)
    region = row.region or region
    autoscaling = session.client("autoscaling", region_name=region)
    try:
        autoscaling.update_auto_scaling_group(
            AutoScalingGroupName=row.asg_name,
            MinSize=row.min_size,
            MaxSize=row.max_size,
        )
    except ClientError as e:
        msg = e.response.get("Error", {}).get("Message", str(e))
        raise HTTPException(status_code=502, detail=msg)

    return {"status": "applied", "asg_name": row.asg_name, "min_size": row.min_size, "max_size": row.max_size}
