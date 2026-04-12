"""Persistent EC2 schedule jobs and action history for Smart Scheduler."""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.database.session import Base


class Ec2Schedule(Base):
    __tablename__ = "ec2_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(36), unique=True, nullable=False, index=True)
    instance_ids = Column(JSON, nullable=False)  # list[str]
    start_time = Column(String(8), nullable=False)  # "HH:MM"
    stop_time = Column(String(8), nullable=False)
    timezone = Column(String(64), nullable=False, default="UTC")
    days_pattern = Column(String(32), nullable=False, default="all")  # all | weekdays | weekends
    enabled = Column(Boolean, nullable=False, default=True)
    estimated_hourly_usd = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SchedulerActionLog(Base):
    __tablename__ = "scheduler_action_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_id = Column(String(64), nullable=False, index=True)
    action = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)
    message = Column(Text, nullable=True)
    estimated_savings_usd = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AsgScalingRule(Base):
    """Metadata for ASG CPU-based scaling rules (alarms + policies created in AWS)."""

    __tablename__ = "asg_scaling_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(String(36), unique=True, nullable=False, index=True)
    asg_name = Column(String(255), nullable=False, index=True)
    region = Column(String(32), nullable=False)
    min_size = Column(Integer, nullable=False)
    max_size = Column(Integer, nullable=False)
    scale_up_cpu = Column(Integer, nullable=False, default=70)
    scale_down_cpu = Column(Integer, nullable=False, default=20)
    scale_up_policy_arn = Column(String(512), nullable=True)
    scale_down_policy_arn = Column(String(512), nullable=True)
    scale_up_policy_name = Column(String(256), nullable=True)
    scale_down_policy_name = Column(String(256), nullable=True)
    alarm_high_arn = Column(String(512), nullable=True)
    alarm_low_arn = Column(String(512), nullable=True)
    alarm_high_name = Column(String(256), nullable=True)
    alarm_low_name = Column(String(256), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
