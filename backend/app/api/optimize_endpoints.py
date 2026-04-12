"""
Optimization execution endpoints.

Implements real AWS actions (stop idle EC2 instances, delete unattached EBS volumes)
with safety gates to avoid accidental changes.
"""

from __future__ import annotations

import os
from typing import Literal, Optional, List, Dict, Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, PartialCredentialsError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.aws_account import AwsAccount
from app.models.resource import Resource
from app.models.models import SystemConfiguration


router = APIRouter(tags=["Optimization Execution"])


class OptimizeExecuteRequest(BaseModel):
    resource_id: str = Field(..., min_length=1, description="EC2 instance ID (i-...) or EBS volume ID (vol-...)")
    resource_type: Literal["ec2_instance", "ebs_volume"] = Field(..., description="Resource type to execute on")
    confirm_delete: bool = Field(default=False, description="Required for volume deletion actions")


class OptimizeExecuteResponse(BaseModel):
    status: Literal["success"]
    actions: List[str]
    resource_id: str


def _env_truthy(name: str) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    return v in {"1", "true", "yes", "y", "on"}

def _get_auto_mode_enabled(db: Session) -> bool:
    """
    Auto mode effective value.
    Precedence:
    1) DB override in system_configurations.key = 'auto_mode_enabled'
    2) Environment variable AUTO_MODE_ENABLED
    """
    try:
        row = db.query(SystemConfiguration).filter(SystemConfiguration.key == "auto_mode_enabled").first()
        if row and isinstance(row.value, dict) and "enabled" in row.value:
            return bool(row.value.get("enabled"))
        if row and isinstance(row.value, bool):
            return bool(row.value)
    except Exception:
        # Fail closed to env-based behavior if config read fails
        pass
    return _env_truthy("AUTO_MODE_ENABLED")


def _get_region(resource: Optional[Resource]) -> str:
    return (
        (resource.region if resource and getattr(resource, "region", None) else None)
        or os.getenv("AWS_REGION")
        or os.getenv("AWS_DEFAULT_REGION")
        or "us-east-1"
    )


def _require_auto_mode(db: Session) -> None:
    auto_mode_enabled = _get_auto_mode_enabled(db)
    print("Auto mode:", auto_mode_enabled)
    if not auto_mode_enabled:
        raise HTTPException(
            status_code=403,
            detail='Auto mode is disabled. Set environment variable "AUTO_MODE_ENABLED=true" to allow execution.',
        )

def _get_instance_tags(ec2_client, instance_id: str) -> Dict[str, str]:
    resp = ec2_client.describe_instances(InstanceIds=[instance_id])
    reservations = resp.get("Reservations", [])
    instances: List[Dict[str, Any]] = []
    for r in reservations:
        instances.extend(r.get("Instances", []))
    if not instances:
        raise HTTPException(status_code=404, detail="EC2 instance not found in AWS.")
    tags = instances[0].get("Tags") or []
    return {t.get("Key"): t.get("Value") for t in tags if t.get("Key")}


class AutoModeStateResponse(BaseModel):
    enabled: bool
    source: Literal["db", "env"]


class AutoModeUpdateRequest(BaseModel):
    enabled: bool = Field(..., description="Whether to enable auto mode execution")


@router.get("/optimize/auto-mode", response_model=AutoModeStateResponse)
def get_auto_mode(db: Session = Depends(get_db)):
    """
    Get current auto mode state.
    """
    enabled_env = _env_truthy("AUTO_MODE_ENABLED")
    enabled_effective = _get_auto_mode_enabled(db)
    source: Literal["db", "env"] = "env"
    try:
        row = db.query(SystemConfiguration).filter(SystemConfiguration.key == "auto_mode_enabled").first()
        if row is not None:
            source = "db"
    except Exception:
        source = "env"
    print("Auto mode:", enabled_effective)
    # If DB row exists but is unreadable, we still report effective value and db source.
    if source == "env" and enabled_effective != enabled_env:
        source = "db"
    return AutoModeStateResponse(enabled=enabled_effective, source=source)


@router.put("/optimize/auto-mode", response_model=AutoModeStateResponse)
def set_auto_mode(payload: AutoModeUpdateRequest, db: Session = Depends(get_db)):
    """
    Persist auto mode toggle in DB.
    """
    row = db.query(SystemConfiguration).filter(SystemConfiguration.key == "auto_mode_enabled").first()
    if row is None:
        row = SystemConfiguration(
            key="auto_mode_enabled",
            value={"enabled": bool(payload.enabled)},
            description="Auto mode execution toggle (true enables real AWS actions)",
            is_encrypted=False,
        )
        db.add(row)
    else:
        row.value = {"enabled": bool(payload.enabled)}
    db.commit()
    enabled_effective = _get_auto_mode_enabled(db)
    print("Auto mode:", enabled_effective)
    return AutoModeStateResponse(enabled=enabled_effective, source="db")


@router.post("/optimize/execute", response_model=OptimizeExecuteResponse)
def optimize_execute(payload: OptimizeExecuteRequest, db: Session = Depends(get_db)):
    """
    Execute real optimization actions in AWS.

    Safety:
    - Only runs if AUTO_MODE_ENABLED=true
    - Volume deletion requires confirm_delete=true
    - Only stops EC2 instances already marked idle in our inventory
    - Only deletes EBS volumes already marked unattached in our inventory
    """
    _require_auto_mode(db)

    # Ensure there is an AWS account connected (used to gate optimization UI).
    # Credentials for boto3 are loaded from environment variables (or standard AWS chain).
    account = AwsAccount.get_default(db)
    if not account:
        raise HTTPException(status_code=400, detail="AWS account not configured. Connect first.")

    # Fetch resource from our inventory to enforce "idle" / "unattached" gates.
    resource = (
        db.query(Resource)
        .filter(Resource.resource_id == payload.resource_id, Resource.resource_type == payload.resource_type)
        .first()
    )
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found in inventory. Refresh resources first.")

    region = _get_region(resource)

    try:
        print("Connected to AWS region:", region)
        ec2 = boto3.client("ec2", region_name=region)

        if payload.resource_type == "ec2_instance":
            if not bool(getattr(resource, "is_idle", False)):
                raise HTTPException(status_code=400, detail="Instance is not marked idle; refusing to stop it.")

            tags = _get_instance_tags(ec2, payload.resource_id)
            if (tags.get("DoNotStop") or "").strip().lower() == "true":
                print(f"[optimize] Skipping stop due to DoNotStop=true tag (instance={payload.resource_id})")
                return OptimizeExecuteResponse(
                    status="success",
                    actions=["skipped EC2 (DoNotStop=true)"],
                    resource_id=payload.resource_id,
                )

            print(f"[optimize] Stopping idle EC2 instance {payload.resource_id} in {region}")
            ec2.stop_instances(InstanceIds=[payload.resource_id])
            return OptimizeExecuteResponse(
                status="success",
                actions=["stopped EC2"],
                resource_id=payload.resource_id,
            )

        if payload.resource_type == "ebs_volume":
            if not bool(getattr(resource, "is_unattached", False)):
                raise HTTPException(status_code=400, detail="Volume is not marked unattached; refusing to delete it.")
            if not payload.confirm_delete:
                raise HTTPException(status_code=400, detail="confirm_delete=true is required to delete volumes.")

            print(f"[optimize] Deleting unattached EBS volume {payload.resource_id} in {region}")
            ec2.delete_volume(VolumeId=payload.resource_id)
            return OptimizeExecuteResponse(
                status="success",
                actions=["deleted volume"],
                resource_id=payload.resource_id,
            )

        raise HTTPException(status_code=400, detail="Unsupported resource_type")

    except (NoCredentialsError, PartialCredentialsError):
        raise HTTPException(
            status_code=401,
            detail="AWS credentials not found or incomplete. Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY (and AWS_SESSION_TOKEN if needed).",
        )
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "ClientError")
        msg = e.response.get("Error", {}).get("Message", str(e))
        print(f"[optimize] AWS ClientError {code}: {msg} (resource={payload.resource_id})")
        raise HTTPException(status_code=502, detail=f"AWS error ({code}): {msg}")
    except BotoCoreError as e:
        print(f"[optimize] AWS BotoCoreError: {str(e)} (resource={payload.resource_id})")
        raise HTTPException(status_code=502, detail=f"AWS SDK error: {str(e)}")

