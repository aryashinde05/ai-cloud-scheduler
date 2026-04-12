"""
AWS Cost Explorer — aggregated daily costs and service breakdown for the Cost Explorer UI.
Cost Explorer API is only available in us-east-1; credentials use the default account or env chain.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.config import Config as BotoConfig
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.database.session import get_db
from app.models.aws_account import AwsAccount
from app.services.startup_migration.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cost-explorer", tags=["Cost Explorer"])

BOTO_CFG = BotoConfig(retries={"max_attempts": 3, "mode": "standard"}, connect_timeout=8, read_timeout=20)


def _boto_session_for_ce(db: Session) -> Tuple[boto3.Session, Optional[str]]:
    account = AwsAccount.get_default(db)
    if account:
        try:
            ak, sk, _reg = account.get_decrypted_credentials()
            if ak and sk:
                return boto3.Session(aws_access_key_id=ak, aws_secret_access_key=sk), "account"
        except Exception as e:
            logger.info("AWS account session unavailable: %s", e)
    return boto3.Session(), "default_chain"


def _fetch_ce_overview(session: boto3.Session, days: int) -> Dict[str, Any]:
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    ce = session.client("ce", region_name="us-east-1", config=BOTO_CFG)

    daily: Dict[str, float] = {}
    by_service: Dict[str, float] = {}

    resp = ce.get_cost_and_usage(
        TimePeriod={"Start": str(start), "End": str(end)},
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )

    for result in resp.get("ResultsByTime", []):
        d = result["TimePeriod"]["Start"]
        day_total = 0.0
        for group in result.get("Groups", []):
            keys = group.get("Keys") or []
            svc = keys[0] if keys else "Unknown"
            amt = float(group["Metrics"]["UnblendedCost"]["Amount"] or 0)
            day_total += amt
            by_service[svc] = round(by_service.get(svc, 0.0) + amt, 4)
        daily[d] = round(day_total, 4)

    total = round(sum(daily.values()), 2)
    top_services = sorted(by_service.items(), key=lambda x: -x[1])[:25]

    daily_series: List[Dict[str, Any]] = [{"date": k, "amount_usd": v} for k, v in sorted(daily.items())]

    return {
        "period_start": str(start),
        "period_end": str(end),
        "granularity_days": days,
        "total_cost_usd": total,
        "daily": daily_series,
        "by_service": [{"service": s, "amount_usd": round(a, 2)} for s, a in top_services],
        "error": None,
    }


@router.get("/overview")
def cost_explorer_overview(
    days: int = Query(7, ge=1, le=366),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Daily UnblendedCost totals and top services from Cost Explorer.
    Requires ce:GetCostAndUsage on the billing account.
    """
    session, source = _boto_session_for_ce(db)
    try:
        data = _fetch_ce_overview(session, days)
        data["credential_source"] = source
        return data
    except Exception as e:
        logger.warning("Cost Explorer overview failed: %s", e)
        return {
            "period_start": None,
            "period_end": None,
            "granularity_days": days,
            "total_cost_usd": 0.0,
            "daily": [],
            "by_service": [],
            "credential_source": source,
            "error": str(e),
        }
