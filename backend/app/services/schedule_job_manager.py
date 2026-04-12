"""
APScheduler-based execution for EC2 start/stop schedules stored in the database.
"""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, List, Optional, Tuple

import boto3
from apscheduler.schedulers.background import BackgroundScheduler
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.aws_account import AwsAccount
from app.models.ec2_schedule_models import Ec2Schedule, SchedulerActionLog
from app.models.models import SystemConfiguration
from app.services.scheduler_savings_util import estimated_savings_for_schedule_stop

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None

SCHEDULER_EXEC_KEY = "scheduler_execution_enabled"


def _truthy_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def is_scheduler_execution_enabled(db: Session) -> bool:
    try:
        row = db.query(SystemConfiguration).filter(SystemConfiguration.key == SCHEDULER_EXEC_KEY).first()
        if row and isinstance(row.value, dict) and "enabled" in row.value:
            return bool(row.value.get("enabled"))
        if row and isinstance(row.value, bool):
            return bool(row.value)
    except Exception:
        pass
    env_v = os.getenv("SCHEDULER_EXECUTION_ENABLED")
    if env_v is not None and env_v.strip() != "":
        return _truthy_env("SCHEDULER_EXECUTION_ENABLED")
    return True


def _set_execution_enabled_db(db: Session, enabled: bool) -> None:
    row = db.query(SystemConfiguration).filter(SystemConfiguration.key == SCHEDULER_EXEC_KEY).first()
    if row is None:
        row = SystemConfiguration(
            key=SCHEDULER_EXEC_KEY,
            value={"enabled": enabled},
            description="When false, APScheduler will not start/stop EC2 (safe mode)",
            is_encrypted=False,
        )
        db.add(row)
    else:
        row.value = {"enabled": enabled}
    db.commit()


def set_scheduler_execution_enabled(enabled: bool) -> None:
    db = SessionLocal()
    try:
        _set_execution_enabled_db(db, enabled)
    finally:
        db.close()


def _parse_hhmm(s: str) -> Tuple[int, int]:
    parts = (s or "00:00").strip().split(":")
    h = int(parts[0]) if parts else 0
    m = int(parts[1]) if len(parts) > 1 else 0
    return h % 24, m % 60


def _day_of_week_cron(pattern: str) -> str:
    p = (pattern or "all").lower().strip()
    if p == "weekdays":
        return "mon-fri"
    if p == "weekends":
        return "sat,sun"
    return "*"


def _instance_tags(ec2_client, instance_id: str) -> Dict[str, str]:
    r = ec2_client.describe_instances(InstanceIds=[instance_id])
    tags: Dict[str, str] = {}
    for res in r.get("Reservations", []):
        for inst in res.get("Instances", []):
            for t in inst.get("Tags") or []:
                if t.get("Key"):
                    tags[t["Key"]] = t.get("Value") or ""
    return tags


def _do_not_schedule(tags: Dict[str, str]) -> bool:
    v = (tags.get("DoNotSchedule") or "").strip().lower()
    return v in {"true", "1", "yes"}


def _log_action(
    db: Session,
    resource_id: str,
    action: str,
    status: str,
    message: str,
    estimated_savings_usd: Optional[float] = None,
) -> None:
    db.add(
        SchedulerActionLog(
            resource_id=resource_id,
            action=action,
            status=status,
            message=message[:2000] if message else None,
            estimated_savings_usd=estimated_savings_usd,
        )
    )
    db.commit()
    print(f"[scheduler] {action} {resource_id} -> {status}: {message}")


def _sns_notify(subject: str, body: str) -> None:
    arn = (os.getenv("AWS_SNS_ALERT_TOPIC_ARN") or "").strip()
    if not arn:
        return
    try:
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-south-1"
        sns = boto3.client("sns", region_name=region)
        sns.publish(TopicArn=arn, Subject=subject[:100], Message=body[:3000])
    except Exception as e:
        logger.warning("SNS alert failed: %s", e)


def _boto_session_for_schedule(db: Session) -> Tuple[Any, str]:
    account = AwsAccount.get_default(db)
    region = (
        os.getenv("AWS_REGION")
        or os.getenv("AWS_DEFAULT_REGION")
        or (account.region if account else None)
        or "ap-south-1"
    )
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


def _run_start(public_id: str) -> None:
    db = SessionLocal()
    try:
        if not is_scheduler_execution_enabled(db):
            logger.info("Scheduler execution disabled; skip start %s", public_id)
            return
        row = db.query(Ec2Schedule).filter(Ec2Schedule.public_id == public_id).first()
        if not row or not row.enabled:
            return
        session, region = _boto_session_for_schedule(db)
        ec2 = session.client("ec2", region_name=region)
        ids: List[str] = list(row.instance_ids or [])
        for iid in ids:
            try:
                tags = _instance_tags(ec2, iid)
                if _do_not_schedule(tags):
                    _log_action(db, iid, "start", "skipped", "DoNotSchedule=true")
                    continue
                ec2.start_instances(InstanceIds=[iid])
                _log_action(db, iid, "start", "success", f"Scheduled start in {region}")
                _sns_notify("EC2 started", f"Instance {iid} started by scheduler in {region}")
            except ClientError as e:
                msg = e.response.get("Error", {}).get("Message", str(e))
                _log_action(db, iid, "start", "failed", msg)
            except Exception as e:
                _log_action(db, iid, "start", "failed", str(e))
    finally:
        db.close()


def _run_stop(public_id: str) -> None:
    db = SessionLocal()
    try:
        if not is_scheduler_execution_enabled(db):
            logger.info("Scheduler execution disabled; skip stop %s", public_id)
            return
        row = db.query(Ec2Schedule).filter(Ec2Schedule.public_id == public_id).first()
        if not row or not row.enabled:
            return
        session, region = _boto_session_for_schedule(db)
        ec2 = session.client("ec2", region_name=region)
        ids: List[str] = list(row.instance_ids or [])
        for iid in ids:
            try:
                tags = _instance_tags(ec2, iid)
                if _do_not_schedule(tags):
                    _log_action(db, iid, "stop", "skipped", "DoNotSchedule=true")
                    continue
                ec2.stop_instances(InstanceIds=[iid])
                savings = estimated_savings_for_schedule_stop(row)
                _log_action(
                    db,
                    iid,
                    "stop",
                    "success",
                    f"Scheduled stop in {region}",
                    estimated_savings_usd=savings,
                )
                _sns_notify("EC2 stopped", f"Instance {iid} stopped by scheduler in {region}")
            except ClientError as e:
                msg = e.response.get("Error", {}).get("Message", str(e))
                _log_action(db, iid, "stop", "failed", msg)
            except Exception as e:
                _log_action(db, iid, "stop", "failed", str(e))
    finally:
        db.close()


def sync_schedule_jobs(sched: BackgroundScheduler, db: Session) -> None:
    """Register cron jobs for all enabled Ec2Schedule rows."""
    for job in list(sched.get_jobs()):
        if job.id.startswith("ec2sched-"):
            try:
                sched.remove_job(job.id)
            except Exception:
                pass

    rows = db.query(Ec2Schedule).all()
    for row in rows:
        if not row.enabled:
            continue
        sh, sm = _parse_hhmm(row.start_time)
        eh, em = _parse_hhmm(row.stop_time)
        dow = _day_of_week_cron(row.days_pattern)
        tz = row.timezone or "UTC"
        try:
            sched.add_job(
                _run_start,
                "cron",
                id=f"ec2sched-{row.public_id}-start",
                replace_existing=True,
                hour=sh,
                minute=sm,
                day_of_week=dow,
                timezone=tz,
                args=[row.public_id],
            )
            sched.add_job(
                _run_stop,
                "cron",
                id=f"ec2sched-{row.public_id}-stop",
                replace_existing=True,
                hour=eh,
                minute=em,
                day_of_week=dow,
                timezone=tz,
                args=[row.public_id],
            )
        except Exception as e:
            logger.error("Failed to register jobs for %s: %s", row.public_id, e)


def reload_schedule_jobs() -> None:
    global _scheduler
    if _scheduler is None:
        return
    db = SessionLocal()
    try:
        sync_schedule_jobs(_scheduler, db)
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler()
    _scheduler.start()
    db = SessionLocal()
    try:
        sync_schedule_jobs(_scheduler, db)
        logger.info("APScheduler started; EC2 schedule jobs synced")
    finally:
        db.close()


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None


__all__ = [
    "start_scheduler",
    "shutdown_scheduler",
    "reload_schedule_jobs",
    "is_scheduler_execution_enabled",
    "set_scheduler_execution_enabled",
    "SCHEDULER_EXEC_KEY",
]
