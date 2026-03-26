from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError, EndpointResolutionError
from sqlalchemy.orm import Session

from app.models.aws_account import AwsAccount
from app.models.resource import Resource
from app.services import optimizer

logger = logging.getLogger(__name__)

# All regions to scan when doing a full multi-region sweep
ALL_REGIONS = [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "eu-west-1", "eu-west-2", "eu-west-3", "eu-central-1", "eu-north-1",
    "ap-southeast-1", "ap-southeast-2", "ap-northeast-1", "ap-northeast-2",
    "ap-south-1", "ap-east-1",
    "sa-east-1", "ca-central-1", "me-south-1", "af-south-1",
]

BOTO_CONFIG = BotoConfig(
    retries={"max_attempts": 3, "mode": "standard"},
    connect_timeout=5,
    read_timeout=10,
)


def _make_session(account: AwsAccount) -> boto3.Session:
    access_key, secret_key, _ = account.get_decrypted_credentials()
    return boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def _fetch_cpu_utilization(cloudwatch, instance_ids: List[str]) -> Dict[str, float]:
    now = datetime.utcnow()
    start_time = now - timedelta(hours=24)
    cpu_by_instance: Dict[str, float] = {}

    for instance_id in instance_ids:
        try:
            response = cloudwatch.get_metric_statistics(
                Namespace="AWS/EC2",
                MetricName="CPUUtilization",
                Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                StartTime=start_time,
                EndTime=now,
                Period=3600,
                Statistics=["Average"],
            )
            datapoints = response.get("Datapoints", [])
            if datapoints:
                avg = sum(dp["Average"] for dp in datapoints) / len(datapoints)
                cpu_by_instance[instance_id] = float(avg)
        except Exception:
            continue

    return cpu_by_instance


def _upsert_resource(
    db: Session,
    account: AwsAccount,
    resource_id: str,
    resource_type: str,
    **fields,
) -> Resource:
    resource = (
        db.query(Resource)
        .filter(
            Resource.aws_account_id == account.id,
            Resource.resource_id == resource_id,
            Resource.resource_type == resource_type,
        )
        .first()
    )
    if not resource:
        resource = Resource(
            aws_account_id=account.id,
            resource_id=resource_id,
            resource_type=resource_type,
        )
        db.add(resource)

    for key, value in fields.items():
        setattr(resource, key, value)

    optimizer.apply_optimization_flags(resource)
    resource.last_seen_at = datetime.utcnow()
    return resource


def _collect_region(
    db: Session,
    account: AwsAccount,
    session: boto3.Session,
    region: str,
) -> int:
    """Collect EC2 instances and EBS volumes for a single region. Returns count of resources found."""
    found = 0
    try:
        ec2 = session.client("ec2", region_name=region, config=BOTO_CONFIG)
        cw = session.client("cloudwatch", region_name=region, config=BOTO_CONFIG)

        # EC2 Instances (paginated)
        instance_ids = []
        instances_data = []
        paginator = ec2.get_paginator("describe_instances")
        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                for inst in reservation.get("Instances", []):
                    instance_ids.append(inst["InstanceId"])
                    instances_data.append(inst)

        cpu_map = _fetch_cpu_utilization(cw, instance_ids)

        for inst in instances_data:
            inst_id = inst["InstanceId"]
            name = next((t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"), inst_id)
            _upsert_resource(
                db, account,
                resource_id=inst_id,
                resource_type="ec2_instance",
                region=region,
                name=name,
                state=inst["State"]["Name"],
                launch_time=inst["LaunchTime"],
                instance_type=inst["InstanceType"],
                cpu_utilization=cpu_map.get(inst_id),
            )
            found += 1

        # EBS Volumes (paginated)
        vol_paginator = ec2.get_paginator("describe_volumes")
        for page in vol_paginator.paginate():
            for vol in page.get("Volumes", []):
                vol_id = vol["VolumeId"]
                name = next((t["Value"] for t in vol.get("Tags", []) if t["Key"] == "Name"), vol_id)
                _upsert_resource(
                    db, account,
                    resource_id=vol_id,
                    resource_type="ebs_volume",
                    region=region,
                    name=name,
                    state=vol["State"],
                    launch_time=vol["CreateTime"],
                    volume_size=vol["Size"],
                    volume_type=vol["VolumeType"],
                    iops=vol.get("Iops"),
                )
                found += 1

    except ClientError as e:
        code = e.response["Error"]["Code"]
        # AuthFailure / UnauthorizedOperation means creds are bad — re-raise
        if code in ("AuthFailure", "UnauthorizedOperation", "InvalidClientTokenId"):
            raise RuntimeError(f"AWS credentials rejected: {e}") from e
        # OptInRequired means the region isn't enabled for this account — skip silently
        logger.debug("Skipping region %s: %s", region, code)
    except Exception as e:
        logger.debug("Skipping region %s: %s", region, e)

    return found


def refresh_resources(
    db: Session,
    account: AwsAccount,
    regions: Optional[List[str]] = None,
) -> Dict[str, int]:
    """
    Scan one or more regions and upsert all EC2/EBS resources into the DB.

    If `regions` is None, scans ALL_REGIONS automatically.
    Returns a dict of {region: resource_count}.
    """
    session = _make_session(account)
    targets = regions if regions else ALL_REGIONS
    summary: Dict[str, int] = {}

    for region in targets:
        count = _collect_region(db, account, session, region)
        if count > 0:
            summary[region] = count
            logger.info("Region %s: found %d resources", region, count)

    db.commit()

    # Update the stored region to the first region that had resources,
    # so future single-region calls default to the right place.
    if summary:
        best_region = max(summary, key=lambda r: summary[r])
        if account.region != best_region:
            account.region = best_region
            db.commit()
            logger.info("Updated default region to %s", best_region)

    return summary
