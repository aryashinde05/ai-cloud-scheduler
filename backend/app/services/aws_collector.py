from __future__ import annotations

import json
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Any

import boto3
from botocore.config import Config as BotoConfig
from sqlalchemy.orm import Session

from app.models.aws_account import AwsAccount
from app.models.resource import Resource
from app.services import optimizer


def _build_clients(account: AwsAccount) -> Tuple:
    access_key, secret_key, region = account.get_decrypted_credentials()
    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )
    boto_config = BotoConfig(retries={"max_attempts": 5, "mode": "standard"})
    ec2 = session.client("ec2", config=boto_config)
    cloudwatch = session.client("cloudwatch", config=boto_config)
    return ec2, cloudwatch


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
        except Exception:
            continue

        datapoints = response.get("Datapoints", [])
        if not datapoints:
            continue

        # Average over all datapoints
        avg = sum(dp["Average"] for dp in datapoints) / len(datapoints)
        cpu_by_instance[instance_id] = float(avg)

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


def refresh_resources(db: Session, account: AwsAccount, cache_ttl_seconds: int = 60) -> None:
    """
    Fetch EC2 instances and EBS volumes for the given account and update the Resource table.
    Caching disabled for simplicity in this integration.
    """
    ec2, cloudwatch = _build_clients(account)

    # 1. EC2 Instances
    response = ec2.describe_instances()
    instance_ids = []
    instances_data = []

    for reservation in response.get("Reservations", []):
        for instance in reservation.get("Instances", []):
            instance_id = instance["InstanceId"]
            instance_ids.append(instance_id)
            instances_data.append(instance)

    # Fetch CPU metrics for all instances (naive approach: one by one or batched)
    cpu_map = _fetch_cpu_utilization(cloudwatch, instance_ids)

    for inst in instances_data:
        inst_id = inst["InstanceId"]
        inst_type = inst["InstanceType"]
        state = inst["State"]["Name"]
        launch_time = inst["LaunchTime"]
        
        # Name tag
        name = next((t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"), inst_id)

        _upsert_resource(
            db, account, 
            resource_id=inst_id,
            resource_type="ec2_instance",
            region=account.region,
            name=name,
            state=state,
            launch_time=launch_time,
            instance_type=inst_type,
            cpu_utilization=cpu_map.get(inst_id)
        )

    # 2. EBS Volumes
    vol_resp = ec2.describe_volumes()
    for vol in vol_resp.get("Volumes", []):
        vol_id = vol["VolumeId"]
        size = vol["Size"]
        state = vol["State"]
        create_time = vol["CreateTime"]
        vol_type = vol["VolumeType"]
        iops = vol.get("Iops")

        name = next((t["Value"] for t in vol.get("Tags", []) if t["Key"] == "Name"), vol_id)

        _upsert_resource(
            db, account,
            resource_id=vol_id,
            resource_type="ebs_volume",
            region=account.region,
            name=name,
            state=state,
            launch_time=create_time,
            volume_size=size,
            volume_type=vol_type,
            iops=iops
        )
    
    db.commit()
