from __future__ import annotations

from typing import Iterable, Union

from sqlalchemy.orm import Session
from app.models.resource import Resource


INSTANCE_MONTHLY_COST = {
    # Simplified on-demand monthly estimates (approx, 730h/month)
    "t3.micro": 8.0,
    "t3.small": 15.0,
    "t3.medium": 30.0,
    "t3.large": 60.0,
    "t3.xlarge": 120.0,
    "t3.2xlarge": 240.0,
    "m5.large": 80.0,
    "m5.xlarge": 160.0,
    "m5.2xlarge": 320.0,
}

DEFAULT_INSTANCE_MONTHLY_COST = 50.0
EBS_MONTHLY_COST_PER_GB = 0.1  # simplified


def estimate_instance_monthly_cost(instance_type: str | None) -> float:
    if not instance_type:
        return DEFAULT_INSTANCE_MONTHLY_COST
    return INSTANCE_MONTHLY_COST.get(instance_type, DEFAULT_INSTANCE_MONTHLY_COST)


def estimate_volume_monthly_cost(size_gb: int | None) -> float:
    if not size_gb:
        return 0.0
    return size_gb * EBS_MONTHLY_COST_PER_GB


def estimate_resource_monthly_cost(resource: Resource) -> float:
    if resource.resource_type == "ec2_instance":
        return estimate_instance_monthly_cost(resource.instance_type)
    if resource.resource_type == "ebs_volume":
        return estimate_volume_monthly_cost(resource.volume_size)
    return 0.0


def apply_optimization_flags(resource: Resource) -> None:
    """
    Evaluate and set idle / oversized / unattached flags based on simple rules.
    """
    # 1. Unattached EBS
    if resource.resource_type == "ebs_volume":
        # Check AWS "State" string
        if resource.state == "available":
            resource.is_unattached = True
        else:
            resource.is_unattached = False
            
    # 2. Idle EC2 (CPU < 2%)
    if resource.resource_type == "ec2_instance":
        if resource.cpu_utilization is not None and resource.cpu_utilization < 2.0:
            resource.is_idle = True
        else:
            resource.is_idle = False

    # 3. Oversized (CPU < 10% but large instance type)
    if resource.resource_type == "ec2_instance":
        large_types = ["t3.xlarge", "t3.2xlarge", "m5.large", "m5.xlarge", "m5.2xlarge"]
        if (
            resource.instance_type in large_types
            and resource.cpu_utilization is not None
            and resource.cpu_utilization < 10.0
        ):
            resource.is_oversized = True
        else:
            resource.is_oversized = False
