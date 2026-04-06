"""
Safety checks used by automation, optimizers, and scaling engines.

The project references a `SafetyChecker` from multiple modules but the file was
missing, which prevents the API from starting.

This implementation is intentionally conservative and dependency-light:
- It provides the interfaces used throughout the codebase.
- It supports basic tag/business-hour checks and returns structured results.
- For cloud-provider specific checks, it returns "passed" with details unless
  enough context is provided to safely fail.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass
class SafetyCheckResult:
    check_name: str
    check_result: bool
    check_details: Dict[str, Any]
    checked_at: datetime


class SafetyChecker:
    """
    Central place for validating whether an automated action is safe.

    Many higher-level services treat safety checks as a gate. To avoid breaking
    core flows during local development, the default behavior is to pass checks
    unless we can confidently determine a violation.
    """

    PRODUCTION_TAG_KEYS = {"environment", "env", "stage"}
    PRODUCTION_TAG_VALUES = {"prod", "production"}

    def validate_action_safety(self, action_or_opportunity: Any, policy: Any) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate safety for an optimization action or opportunity.

        Returns:
            (passed, details)
        """
        results: List[SafetyCheckResult] = []

        metadata = getattr(action_or_opportunity, "resource_metadata", None) or {}
        tags = metadata.get("tags") or metadata.get("Tags") or {}

        # Tag-based protection
        has_prod_tags = self.check_production_tags(tags)
        results.append(
            SafetyCheckResult(
                check_name="production_tag_protection",
                check_result=not has_prod_tags,
                check_details={
                    "has_production_tags": has_prod_tags,
                    "reason": "Protected resource (production tags found)" if has_prod_tags else "No production tags found",
                },
                checked_at=datetime.utcnow(),
            )
        )

        # Business hours constraint (policy may include windows)
        business_hours = getattr(policy, "business_hours", None) or getattr(policy, "businessHours", None)
        if business_hours:
            ok = self.verify_business_hours(business_hours)
            results.append(
                SafetyCheckResult(
                    check_name="business_hours_window",
                    check_result=ok,
                    check_details={"configured": True, "ok_now": ok, "business_hours": business_hours},
                    checked_at=datetime.utcnow(),
                )
            )

        passed = all(r.check_result for r in results)
        return passed, {
            "passed": passed,
            "checks": [self._to_dict(r) for r in results],
        }

    async def check_scaling_safety(
        self,
        resource_id: str,
        action_type: Any,
        current_capacity: int,
        target_capacity: int,
        resource_metadata: Optional[Dict[str, Any]] = None,
    ) -> SafetyCheckResult:
        """
        Lightweight async check used by predictive scaling.
        """
        resource_metadata = resource_metadata or {}
        tags = resource_metadata.get("tags") or {}

        has_prod_tags = self.check_production_tags(tags)
        if has_prod_tags and target_capacity < current_capacity:
            # Be conservative: allow scale-up, but be stricter on scale-down in prod-tagged workloads.
            return SafetyCheckResult(
                check_name="prod_scale_down_guard",
                check_result=False,
                check_details={
                    "resource_id": resource_id,
                    "current_capacity": current_capacity,
                    "target_capacity": target_capacity,
                    "reason": "Scale-down blocked for production-tagged resource",
                },
                checked_at=datetime.utcnow(),
            )

        return SafetyCheckResult(
            check_name="basic_scaling_safety",
            check_result=True,
            check_details={
                "resource_id": resource_id,
                "current_capacity": current_capacity,
                "target_capacity": target_capacity,
                "action_type": getattr(action_type, "value", str(action_type)),
            },
            checked_at=datetime.utcnow(),
        )

    def check_production_tags(self, tags: Any) -> bool:
        """
        Returns True if tags indicate a production resource.
        Accepts dict-like tags or list-of-dicts (AWS style).
        """
        if not tags:
            return False

        # AWS often returns [{"Key": "...", "Value": "..."}]
        if isinstance(tags, list):
            try:
                tags = {t.get("Key") or t.get("key"): t.get("Value") or t.get("value") for t in tags if isinstance(t, dict)}
            except Exception:
                return False

        if not isinstance(tags, dict):
            return False

        for k, v in tags.items():
            if k is None or v is None:
                continue
            key = str(k).strip().lower()
            val = str(v).strip().lower()
            if key in self.PRODUCTION_TAG_KEYS and val in self.PRODUCTION_TAG_VALUES:
                return True
        return False

    def verify_business_hours(self, config: Any, now_utc: Optional[datetime] = None) -> bool:
        """
        Very small helper used by optimizers to decide if a time window is valid.

        Accepts:
          - dict with "start" and "end" in HH:MM
          - dict with "start_hour"/"end_hour" ints
        """
        if config is None:
            return True

        now_utc = now_utc or datetime.utcnow()

        if isinstance(config, dict):
            start_s = config.get("start")
            end_s = config.get("end")
            if start_s and end_s and isinstance(start_s, str) and isinstance(end_s, str):
                try:
                    sh, sm = [int(x) for x in start_s.split(":")]
                    eh, em = [int(x) for x in end_s.split(":")]
                    start_t = time(sh, sm)
                    end_t = time(eh, em)
                    return self._is_within_window(now_utc.time(), start_t, end_t)
                except Exception:
                    return True

            start_h = config.get("start_hour")
            end_h = config.get("end_hour")
            if isinstance(start_h, int) and isinstance(end_h, int):
                start_t = time(start_h, 0)
                end_t = time(end_h, 0)
                return self._is_within_window(now_utc.time(), start_t, end_t)

        # Unknown format: don't block.
        return True

    def validate_action_safety_for_batch(self, actions: Iterable[Any], policy: Any) -> Tuple[bool, Dict[str, Any]]:
        results = []
        for a in actions:
            ok, details = self.validate_action_safety(a, policy)
            results.append({"ok": ok, "details": details})
        passed = all(r["ok"] for r in results)
        return passed, {"passed": passed, "results": results}

    @staticmethod
    def _is_within_window(now: time, start: time, end: time) -> bool:
        if start <= end:
            return start <= now <= end
        # overnight window (e.g., 22:00-06:00)
        return now >= start or now <= end

    @staticmethod
    def _to_dict(r: SafetyCheckResult) -> Dict[str, Any]:
        return {
            "check_name": r.check_name,
            "check_result": r.check_result,
            "check_details": r.check_details,
            "checked_at": r.checked_at,
        }

