"""
Real AWS Budgets endpoints — reads directly from AWS Budgets API.
"""
import logging
from typing import List, Optional
from datetime import datetime, timezone

import boto3
from botocore.config import Config as BotoConfig
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.aws_account import AwsAccount

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/aws/budgets", tags=["Budgets"])

BOTO_CFG = BotoConfig(retries={"max_attempts": 3, "mode": "standard"}, connect_timeout=8, read_timeout=15)


def _make_session(account: AwsAccount) -> boto3.Session:
    access_key, secret_key, region = account.get_decrypted_credentials()
    return boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )


def _get_account_id(session: boto3.Session) -> str:
    try:
        return session.client("sts").get_caller_identity()["Account"]
    except Exception:
        return ""


def _fetch_budgets(session: boto3.Session, account_id: str) -> List[dict]:
    client = session.client("budgets", region_name="us-east-1", config=BOTO_CFG)
    budgets = []
    try:
        paginator = client.get_paginator("describe_budgets")
        for page in paginator.paginate(AccountId=account_id):
            for b in page.get("Budgets", []):
                limit = b.get("BudgetLimit", {})
                actual = b.get("CalculatedSpend", {}).get("ActualSpend", {})
                forecasted = b.get("CalculatedSpend", {}).get("ForecastedSpend", {})

                amount = float(limit.get("Amount", 0))
                spent = float(actual.get("Amount", 0))
                forecast = float(forecasted.get("Amount", 0)) if forecasted.get("Amount") else None
                utilization = round((spent / amount) * 100, 1) if amount > 0 else 0

                status = "good"
                if utilization >= 90:
                    status = "critical"
                elif utilization >= 75:
                    status = "warning"

                # Fetch alert thresholds
                alerts = []
                try:
                    notifs = client.describe_notifications_for_budget(
                        AccountId=account_id,
                        BudgetName=b["BudgetName"],
                    ).get("Notifications", [])
                    for n in notifs:
                        threshold = n.get("Threshold", 0)
                        triggered = utilization >= threshold
                        alerts.append({"threshold": threshold, "triggered": triggered})
                except Exception:
                    pass

                period = b.get("TimeUnit", "MONTHLY").lower()
                start = b.get("TimePeriod", {}).get("Start")

                budgets.append({
                    "id": b["BudgetName"],
                    "name": b["BudgetName"],
                    "amount": amount,
                    "spent": spent,
                    "forecast": forecast,
                    "utilization": utilization,
                    "status": status,
                    "period": period,
                    "currency": limit.get("Unit", "USD"),
                    "budget_type": b.get("BudgetType", "COST"),
                    "alerts": alerts,
                    "team": "",
                    "start_date": start.isoformat() if hasattr(start, "isoformat") else str(start) if start else None,
                })
    except client.exceptions.NotFoundException:
        pass
    except Exception as e:
        logger.error("Error fetching budgets: %s", e)
        raise RuntimeError(str(e))
    return budgets


@router.get("")
def list_budgets(db: Session = Depends(get_db)):
    account = AwsAccount.get_default(db)
    if not account:
        raise HTTPException(status_code=400, detail="AWS account not configured.")
    try:
        session = _make_session(account)
        account_id = _get_account_id(session)
        if not account_id:
            raise HTTPException(status_code=400, detail="Could not determine AWS account ID.")
        budgets = _fetch_budgets(session, account_id)
        total_budget = sum(b["amount"] for b in budgets)
        total_spent = sum(b["spent"] for b in budgets)
        return {
            "budgets": budgets,
            "summary": {
                "total_budget": round(total_budget, 2),
                "total_spent": round(total_spent, 2),
                "remaining": round(total_budget - total_spent, 2),
                "active_alerts": sum(1 for b in budgets if any(a["triggered"] for a in b["alerts"])),
                "count": len(budgets),
            },
        }
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch budgets: {e}")


@router.post("")
def create_budget(payload: dict, db: Session = Depends(get_db)):
    """Create a new AWS Budget via the Budgets API."""
    account = AwsAccount.get_default(db)
    if not account:
        raise HTTPException(status_code=400, detail="AWS account not configured.")
    try:
        session = _make_session(account)
        account_id = _get_account_id(session)
        client = session.client("budgets", region_name="us-east-1", config=BOTO_CFG)

        amount = float(payload.get("amount", 0))
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than 0.")

        period_map = {"monthly": "MONTHLY", "quarterly": "QUARTERLY", "annual": "ANNUALLY"}
        time_unit = period_map.get(payload.get("period", "monthly"), "MONTHLY")

        client.create_budget(
            AccountId=account_id,
            Budget={
                "BudgetName": payload["name"],
                "BudgetLimit": {"Amount": str(amount), "Unit": "USD"},
                "TimeUnit": time_unit,
                "BudgetType": "COST",
            },
        )

        # Add alert notifications if thresholds provided
        thresholds = payload.get("alerts", [75, 90])
        for threshold in thresholds:
            try:
                client.create_notification(
                    AccountId=account_id,
                    BudgetName=payload["name"],
                    Notification={
                        "NotificationType": "ACTUAL",
                        "ComparisonOperator": "GREATER_THAN",
                        "Threshold": float(threshold),
                        "ThresholdType": "PERCENTAGE",
                    },
                    Subscribers=[],
                )
            except Exception:
                pass

        return {"message": "Budget created successfully", "name": payload["name"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create budget: {e}")


@router.delete("/{budget_name}")
def delete_budget(budget_name: str, db: Session = Depends(get_db)):
    account = AwsAccount.get_default(db)
    if not account:
        raise HTTPException(status_code=400, detail="AWS account not configured.")
    try:
        session = _make_session(account)
        account_id = _get_account_id(session)
        client = session.client("budgets", region_name="us-east-1", config=BOTO_CFG)
        client.delete_budget(AccountId=account_id, BudgetName=budget_name)
        return {"message": f"Budget '{budget_name}' deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete budget: {e}")
