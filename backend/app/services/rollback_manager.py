"""
Rollback manager.

Several automation modules reference `RollbackManager`, but the original file
was missing. This implementation provides the minimal API required for the
backend to run and for automation endpoints to respond deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class RollbackPlan:
    created_at: datetime
    strategy: str
    details: Dict[str, Any]


class RollbackManager:
    """
    Creates rollback plans and executes them.

    Note: In a real system this would integrate with cloud provider SDKs and
    persist rollback state. For local operation we keep behavior simple and
    side-effect free.
    """

    def create_rollback_plan(self, opportunity_or_action: Any) -> Dict[str, Any]:
        resource_id = getattr(opportunity_or_action, "resource_id", None)
        action_type = getattr(getattr(opportunity_or_action, "action_type", None), "value", None) or str(
            getattr(opportunity_or_action, "action_type", "unknown")
        )

        plan = RollbackPlan(
            created_at=datetime.utcnow(),
            strategy="noop",
            details={
                "resource_id": resource_id,
                "action_type": action_type,
                "note": "Rollback not implemented for local demo mode; plan is a no-op.",
            },
        )
        return {
            "created_at": plan.created_at.isoformat(),
            "strategy": plan.strategy,
            "details": plan.details,
        }

    def execute_rollback(self, action: Any) -> bool:
        # No-op rollback; return True so callers can proceed without crashing.
        return True

    def monitor_post_action_health(self, action: Any) -> Dict[str, Any]:
        # Placeholder health monitor. Always reports healthy.
        return {
            "action_id": str(getattr(action, "id", "")),
            "checked_at": datetime.utcnow().isoformat(),
            "issues_detected": False,
            "details": {},
        }

