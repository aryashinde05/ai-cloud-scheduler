"""
Compliance & Governance endpoints — built from real AWS resource data in the DB.
Checks tagging compliance, idle/oversized/unattached resource violations.
"""
import logging
from datetime import datetime, timezone
from typing import List

import boto3
from botocore.config import Config as BotoConfig
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.aws_account import AwsAccount
from app.models.resource import Resource
from app.services.optimizer import estimate_resource_monthly_cost

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/compliance", tags=["Compliance"])

BOTO_CFG = BotoConfig(retries={"max_attempts": 3, "mode": "standard"}, connect_timeout=8, read_timeout=15)

# Required tags every resource should have
REQUIRED_TAGS = ["Name", "Environment", "Owner"]


def _make_session(account: AwsAccount) -> boto3.Session:
    access_key, secret_key, region = account.get_decrypted_credentials()
    return boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )


def _fetch_resource_tags(session: boto3.Session, region: str) -> dict:
    """Fetch tags for all EC2 resources in a region. Returns {resource_id: {tag_key: tag_value}}."""
    tags_map = {}
    try:
        ec2 = session.client("ec2", region_name=region, config=BOTO_CFG)
        paginator = ec2.get_paginator("describe_tags")
        for page in paginator.paginate():
            for tag in page.get("Tags", []):
                rid = tag["ResourceId"]
                if rid not in tags_map:
                    tags_map[rid] = {}
                tags_map[rid][tag["Key"]] = tag["Value"]
    except Exception as e:
        logger.warning("Could not fetch tags for region %s: %s", region, e)
    return tags_map


def _check_tagging(resource: Resource, tags: dict) -> dict:
    """Check if a resource has all required tags. Returns compliance info."""
    resource_tags = tags.get(resource.resource_id, {})
    missing = [t for t in REQUIRED_TAGS if t not in resource_tags]
    compliant = len(missing) == 0
    return {
        "resource_id": resource.resource_id,
        "resource_type": resource.resource_type,
        "name": resource.name or resource.resource_id,
        "region": resource.region or "unknown",
        "compliant": compliant,
        "missing_tags": missing,
        "existing_tags": resource_tags,
    }


@router.get("")
def get_compliance(db: Session = Depends(get_db)):
    account = AwsAccount.get_default(db)
    if not account:
        raise HTTPException(status_code=400, detail="AWS account not configured.")

    resources = db.query(Resource).filter(Resource.aws_account_id == account.id).all()
    if not resources:
        return {
            "overview": {"overallScore": 0, "taggingCompliance": 0, "securityCompliance": 0,
                         "totalResources": 0, "compliantResources": 0},
            "taggingCompliance": [],
            "policyViolations": [],
            "complianceByService": [],
        }

    # Fetch real tags from AWS
    session = _make_session(account)
    regions = list({r.region for r in resources if r.region})
    all_tags: dict = {}
    for region in regions:
        all_tags.update(_fetch_resource_tags(session, region))

    # --- Tagging compliance ---
    tag_results = [_check_tagging(r, all_tags) for r in resources]
    compliant_count = sum(1 for t in tag_results if t["compliant"])
    tagging_pct = round((compliant_count / len(resources)) * 100, 1) if resources else 0

    # Group tagging by resource type (used as "team" proxy)
    type_groups: dict = {}
    for t in tag_results:
        rtype = t["resource_type"]
        if rtype not in type_groups:
            type_groups[rtype] = {"total": 0, "compliant": 0}
        type_groups[rtype]["total"] += 1
        if t["compliant"]:
            type_groups[rtype]["compliant"] += 1

    tagging_by_team = [
        {
            "team": rtype.replace("_", " ").title(),
            "total": v["total"],
            "compliant": v["compliant"],
            "compliance": round((v["compliant"] / v["total"]) * 100, 1) if v["total"] else 0,
        }
        for rtype, v in type_groups.items()
    ]

    # --- Policy violations from real resource flags ---
    violations = []
    for r in resources:
        cost = round(estimate_resource_monthly_cost(r), 2)

        if r.is_idle and r.resource_type == "ec2_instance":
            violations.append({
                "id": f"idle-{r.resource_id}",
                "resource": r.name or r.resource_id,
                "resourceType": "EC2 Instance",
                "policy": "No Idle Resources",
                "violation": f"CPU utilization {r.cpu_utilization:.1f}% — instance appears idle",
                "severity": "medium",
                "team": r.region or "unknown",
                "detected": datetime.now(timezone.utc).isoformat(),
                "status": "open",
                "monthly_cost": cost,
            })

        if r.is_oversized and r.resource_type == "ec2_instance":
            violations.append({
                "id": f"oversized-{r.resource_id}",
                "resource": r.name or r.resource_id,
                "resourceType": "EC2 Instance",
                "policy": "Right-Sizing Policy",
                "violation": f"Instance type {r.instance_type} is oversized (CPU {r.cpu_utilization:.1f}%)",
                "severity": "low",
                "team": r.region or "unknown",
                "detected": datetime.now(timezone.utc).isoformat(),
                "status": "open",
                "monthly_cost": cost,
            })

        if r.is_unattached and r.resource_type == "ebs_volume":
            violations.append({
                "id": f"unattached-{r.resource_id}",
                "resource": r.resource_id,
                "resourceType": "EBS Volume",
                "policy": "No Unattached Volumes",
                "violation": f"EBS volume ({r.volume_size} GB) is not attached to any instance",
                "severity": "high",
                "team": r.region or "unknown",
                "detected": datetime.now(timezone.utc).isoformat(),
                "status": "open",
                "monthly_cost": cost,
            })

        # Missing required tags = compliance violation
        tag_info = next((t for t in tag_results if t["resource_id"] == r.resource_id), None)
        if tag_info and not tag_info["compliant"]:
            violations.append({
                "id": f"tag-{r.resource_id}",
                "resource": r.name or r.resource_id,
                "resourceType": r.resource_type.replace("_", " ").title(),
                "policy": "Mandatory Tagging Policy",
                "violation": f"Missing required tags: {', '.join(tag_info['missing_tags'])}",
                "severity": "low",
                "team": r.region or "unknown",
                "detected": datetime.now(timezone.utc).isoformat(),
                "status": "open",
                "monthly_cost": cost,
            })

    # --- Security score: penalise for idle + unattached ---
    security_issues = sum(1 for r in resources if r.is_idle or r.is_unattached)
    security_pct = round(max(0, 100 - (security_issues / max(len(resources), 1)) * 100), 1)

    overall = round((tagging_pct + security_pct) / 2, 1)

    # --- Compliance by service ---
    service_map = {
        "ec2_instance": {"label": "EC2", "color": "#ff9800"},
        "ebs_volume": {"label": "EBS", "color": "#2196f3"},
        "rds_instance": {"label": "RDS", "color": "#9c27b0"},
    }
    compliance_by_service = []
    for rtype, meta in service_map.items():
        group = [t for t in tag_results if t["resource_type"] == rtype]
        if not group:
            continue
        pct = round((sum(1 for t in group if t["compliant"]) / len(group)) * 100, 1)
        compliance_by_service.append({"service": meta["label"], "compliant": pct, "color": meta["color"]})

    return {
        "overview": {
            "overallScore": overall,
            "taggingCompliance": tagging_pct,
            "securityCompliance": security_pct,
            "totalResources": len(resources),
            "compliantResources": compliant_count,
        },
        "taggingCompliance": tagging_by_team,
        "policyViolations": violations,
        "complianceByService": compliance_by_service,
        "tagDetails": tag_results,
    }
