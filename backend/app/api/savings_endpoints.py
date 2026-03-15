"""
REST API endpoints for Savings Calculator

Provides HTTP endpoints for cost tracking and savings calculation
functionality in the automated cost optimization system.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from supabase import Client

from app.database.database import get_supabase
from app.services.savings_calculator import SavingsCalculator, SavingsReport, SavingsMetrics
from app.models.automation_models import OptimizationAction, ActionStatus
from app.core.auth import get_current_user

router = APIRouter(prefix="/api/v1/savings", tags=["savings"])


# Pydantic models for API responses
class SavingsMetricsResponse(BaseModel):
    """Response model for savings metrics"""
    action_id: str
    estimated_monthly_savings: float
    actual_monthly_savings: Optional[float]
    total_savings_to_date: float
    cost_before_action: float
    cost_after_action: Optional[float]
    savings_percentage: Optional[float]
    payback_period_days: Optional[int]
    roi_percentage: Optional[float]

    class Config:
        from_attributes = True


class SavingsReportResponse(BaseModel):
    """Response model for savings reports"""
    period_start: datetime
    period_end: datetime
    total_estimated_savings: float
    total_actual_savings: float
    savings_by_category: Dict[str, float]
    savings_by_action_type: Dict[str, float]
    top_performing_actions: List[SavingsMetricsResponse]
    rollback_impact: float
    net_savings: float
    actions_count: int
    success_rate: float

    class Config:
        from_attributes = True


class MonthlySavingsTrendResponse(BaseModel):
    """Response model for monthly savings trend"""
    month: str
    savings: float
    actions_count: int
    average_savings_per_action: float


class HistoricalSummaryResponse(BaseModel):
    """Response model for historical savings summary"""
    total_actions: int
    total_savings: float
    average_monthly_savings: float
    best_performing_action_type: Optional[str]
    total_rollback_impact: float


def get_savings_calculator(db: Client = Depends(get_supabase)) -> SavingsCalculator:
    """Dependency to get SavingsCalculator instance"""
    return SavingsCalculator(db)

