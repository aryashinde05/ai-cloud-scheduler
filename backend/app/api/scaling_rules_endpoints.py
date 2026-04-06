"""
REST API Endpoints for Auto-Scaling Rules

Provides endpoints to create, manage, and monitor pre-authorized
scaling rules that automatically adjust AWS resources.
"""

from typing import Dict, List, Optional, Any

import boto3
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.services.scaling_rules_engine import ScalingRulesEngine
from app.database.session import get_db
from app.models.aws_account import AwsAccount

router = APIRouter(prefix="/scaling-rules", tags=["Auto-Scaling Rules"])


_SCALING_ENGINE_CACHE: Dict[str, ScalingRulesEngine] = {}

def get_engine(db: Session = None) -> ScalingRulesEngine:
    """Build ScalingRulesEngine using stored AWS credentials if available."""
    boto3_session = None
    region = "us-east-1"
    cache_key = f"none|{region}"
    if db:
        account = AwsAccount.get_default(db)
        if account:
            try:
                access_key, secret_key, acct_region = account.get_decrypted_credentials()
                cache_key = f"account:{account.id}|{acct_region}"
                boto3_session = boto3.Session(
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    region_name=acct_region,
                )
                region = acct_region
            except Exception:
                pass
    if boto3_session is None:
        boto3_session = boto3.Session(region_name=region)
    if cache_key in _SCALING_ENGINE_CACHE:
        return _SCALING_ENGINE_CACHE[cache_key]

    engine = ScalingRulesEngine(boto3_session=boto3_session, region=region)
    _SCALING_ENGINE_CACHE[cache_key] = engine
    return engine


# ── Pydantic Models ────────────────────────────────────────


class ScalingRuleRequest(BaseModel):
    """Request body for creating/updating a scaling rule."""
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=1000)
    service_type: str = Field(..., description="AWS service: ec2, ebs, rds, asg")
    resource_filter: Dict[str, Any] = Field(
        default_factory=dict,
        description="Resource selection filter. E.g. {resource_ids: ['vol-xxx']} or {tags: {Env: 'prod'}}"
    )
    metric_namespace: str = Field("AWS/EBS", description="CloudWatch namespace")
    metric_name: str = Field("VolumeQueueLength", description="CloudWatch metric name")
    metric_dimension_name: str = Field("VolumeId", description="CloudWatch dimension name")
    metric_statistic: str = Field("Average", description="CloudWatch statistic: Average, Maximum, Sum")
    threshold_operator: str = Field("gt", description="Comparison operator: gt, lt, gte, lte")
    threshold_value: float = Field(..., ge=0, description="Threshold value to trigger scaling")
    evaluation_periods: int = Field(3, ge=1, le=10, description="Consecutive periods that must breach")
    evaluation_interval_seconds: int = Field(300, ge=60, le=3600, description="Interval between checks in seconds")
    scaling_direction: str = Field("scale_up", description="scale_up or scale_down")
    scaling_action: Dict[str, Any] = Field(
        ...,
        description="Action config. EBS: {action: 'increase_storage', amount_gb: 4}, "
                    "EC2: {action: 'resize_instance', target_instance_type: 'm5.xlarge'}, "
                    "RDS: {action: 'resize_db_instance', target_db_instance_class: 'db.m5.large'}"
    )
    max_scaling_limit: Dict[str, Any] = Field(
        default_factory=dict,
        description="Safety limits. EBS: {max_size_gb: 100}, EC2: {max_instance_type: 'm5.4xlarge'}"
    )
    cooldown_seconds: int = Field(1800, ge=300, le=86400, description="Cooldown between triggers in seconds")
    is_enabled: bool = Field(True, description="Whether the rule is active")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Increase production EBS storage",
                "description": "Add 4GB when disk queue length is high",
                "service_type": "ebs",
                "resource_filter": {"resource_ids": ["vol-0abc123"]},
                "metric_namespace": "AWS/EBS",
                "metric_name": "VolumeQueueLength",
                "metric_dimension_name": "VolumeId",
                "metric_statistic": "Average",
                "threshold_operator": "gt",
                "threshold_value": 5.0,
                "evaluation_periods": 3,
                "evaluation_interval_seconds": 300,
                "scaling_direction": "scale_up",
                "scaling_action": {"action": "increase_storage", "amount_gb": 4},
                "max_scaling_limit": {"max_size_gb": 100},
                "cooldown_seconds": 1800,
                "is_enabled": True
            }
        }


class ScalingRuleUpdateRequest(BaseModel):
    """Request body for partial update of a scaling rule."""
    name: Optional[str] = None
    description: Optional[str] = None
    service_type: Optional[str] = None
    resource_filter: Optional[Dict[str, Any]] = None
    metric_namespace: Optional[str] = None
    metric_name: Optional[str] = None
    metric_dimension_name: Optional[str] = None
    metric_statistic: Optional[str] = None
    threshold_operator: Optional[str] = None
    threshold_value: Optional[float] = None
    evaluation_periods: Optional[int] = None
    evaluation_interval_seconds: Optional[int] = None
    scaling_direction: Optional[str] = None
    scaling_action: Optional[Dict[str, Any]] = None
    max_scaling_limit: Optional[Dict[str, Any]] = None
    cooldown_seconds: Optional[int] = None
    is_enabled: Optional[bool] = None


# ── Endpoints ──────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_scaling_rule(request: ScalingRuleRequest, db: Session = Depends(get_db)):
    """Create a new auto-scaling rule."""
    engine = get_engine(db)
    rule = engine.create_rule(request.dict())
    return {"status": "created", "rule": rule}


@router.get("")
async def list_scaling_rules(db: Session = Depends(get_db)):
    """List all scaling rules."""
    engine = get_engine(db)
    rules = engine.get_rules()
    return {"rules": rules, "total": len(rules)}


@router.get("/stats")
async def get_scaling_stats(db: Session = Depends(get_db)):
    """Get auto-scaling summary statistics."""
    engine = get_engine(db)
    return engine.get_stats()


@router.get("/executions/all")
async def get_all_executions(db: Session = Depends(get_db)):
    """Get all execution history across all rules."""
    engine = get_engine(db)
    executions = engine.get_executions()
    return {"executions": executions, "total": len(executions)}


@router.post("/evaluate")
async def evaluate_all_rules(db: Session = Depends(get_db)):
    """
    Manually trigger evaluation of all enabled scaling rules.
    Rules that breach their thresholds will execute their scaling actions.
    """
    engine = get_engine(db)
    results = engine.evaluate_all_rules()
    triggered = [r for r in results if r.get("triggered")]
    return {
        "status": "evaluation_complete",
        "total_rules_evaluated": len(results),
        "rules_triggered": len(triggered),
        "results": results,
    }


@router.get("/{rule_id}")
async def get_scaling_rule(rule_id: str, db: Session = Depends(get_db)):
    """Get a specific scaling rule by ID."""
    engine = get_engine(db)
    rule = engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return {"rule": rule}


@router.put("/{rule_id}")
async def update_scaling_rule(rule_id: str, request: ScalingRuleUpdateRequest, db: Session = Depends(get_db)):
    """Update an existing scaling rule."""
    engine = get_engine(db)
    data = {k: v for k, v in request.dict().items() if v is not None}
    rule = engine.update_rule(rule_id, data)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return {"status": "updated", "rule": rule}


@router.delete("/{rule_id}")
async def delete_scaling_rule(rule_id: str, db: Session = Depends(get_db)):
    """Delete a scaling rule."""
    engine = get_engine(db)
    deleted = engine.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return {"status": "deleted", "rule_id": rule_id}


@router.post("/{rule_id}/toggle")
async def toggle_scaling_rule(rule_id: str, db: Session = Depends(get_db)):
    """Toggle a scaling rule on/off."""
    engine = get_engine(db)
    rule = engine.toggle_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return {"status": "toggled", "rule": rule}


@router.get("/{rule_id}/executions")
async def get_rule_executions(rule_id: str, db: Session = Depends(get_db)):
    """Get execution history for a scaling rule."""
    engine = get_engine(db)
    rule = engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    executions = engine.get_executions(rule_id)
    return {"rule_id": rule_id, "executions": executions, "total": len(executions)}


@router.post("/{rule_id}/test")
async def test_scaling_rule(rule_id: str, db: Session = Depends(get_db)):
    """Dry-run test a scaling rule against current CloudWatch metrics."""
    engine = get_engine(db)
    rule = engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    result = engine.test_rule(rule_id)
    return {"rule_id": rule_id, "test_result": result}
