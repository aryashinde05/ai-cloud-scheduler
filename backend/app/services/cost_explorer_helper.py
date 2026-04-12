"""Optional AWS Cost Explorer helpers for cost-aware scheduling."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def try_daily_costs_by_service(boto3_session, region: str) -> Optional[List[Dict[str, Any]]]:
    """
    Returns last 7 days grouped by service (USD), or None if CE unavailable / denied.
    """
    try:
        ce = boto3_session.client("ce", region_name=region)
        end = date.today()
        start = end - timedelta(days=7)
        resp = ce.get_cost_and_usage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
        out: List[Dict[str, Any]] = []
        for day in resp.get("ResultsByTime", []):
            d = day.get("TimePeriod", {}).get("Start", "")
            for g in day.get("Groups", []):
                svc = g["Keys"][0] if g.get("Keys") else "Unknown"
                amt = float(g["Metrics"]["UnblendedCost"]["Amount"] or 0)
                out.append({"date": d, "service": svc, "amount_usd": round(amt, 4)})
        return out
    except Exception as e:
        logger.info("Cost Explorer unavailable: %s", e)
        return None
