"""
Intelligent Resource Scheduler — CloudWatch-based usage analysis + auto-scheduling.

Analyzes CloudWatch metrics for EC2 instances, detects idle patterns, generates
smart start/stop schedules, and executes them to reduce costs.
"""

import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Approximate on-demand pricing (USD/hour) for common instance types
INSTANCE_PRICING: Dict[str, float] = {
    "t2.nano": 0.0058, "t2.micro": 0.0116, "t2.small": 0.023, "t2.medium": 0.0464,
    "t2.large": 0.0928, "t2.xlarge": 0.1856, "t2.2xlarge": 0.3712,
    "t3.nano": 0.0052, "t3.micro": 0.0104, "t3.small": 0.0208, "t3.medium": 0.0416,
    "t3.large": 0.0832, "t3.xlarge": 0.1664, "t3.2xlarge": 0.3328,
    "t3a.nano": 0.0047, "t3a.micro": 0.0094, "t3a.small": 0.0188, "t3a.medium": 0.0376,
    "t3a.large": 0.0752, "t3a.xlarge": 0.1504, "t3a.2xlarge": 0.3008,
    "m5.large": 0.096, "m5.xlarge": 0.192, "m5.2xlarge": 0.384, "m5.4xlarge": 0.768,
    "m6i.large": 0.096, "m6i.xlarge": 0.192, "m6i.2xlarge": 0.384,
    "c5.large": 0.085, "c5.xlarge": 0.17, "c5.2xlarge": 0.34,
    "r5.large": 0.126, "r5.xlarge": 0.252, "r5.2xlarge": 0.504,
}

DEFAULT_HOURLY_RATE = 0.05  # fallback for unknown instance types

# Demo fallback: if AWS discovery fails (no credentials / no running instances),
# return deterministic demo resources so the UI remains usable.
AWS_DEMO_FALLBACK = os.getenv("AWS_DEMO_FALLBACK", "true").lower() == "true"


class SchedulerService:
    """
    Intelligent resource scheduler that analyses CloudWatch metrics, detects
    idle windows, creates schedules, and executes start/stop actions.
    """

    def __init__(self, boto3_session, region: str | None = None):
        self.session = boto3_session
        self.region = region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-south-1"
        # In-memory stores (MVP — production would use a DB)
        self._schedules: Dict[str, Dict[str, Any]] = {}
        self._action_history: List[Dict[str, Any]] = []
        self._savings_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Resource Discovery
    # ------------------------------------------------------------------

    def get_schedulable_resources(self) -> List[Dict[str, Any]]:
        """List EC2 and RDS instances with basic CloudWatch usage data."""
        resources = []
        try:
            ec2 = self.session.client("ec2", region_name=self.region)
            rds = self.session.client("rds", region_name=self.region)
            cw = self.session.client("cloudwatch", region_name=self.region)

            instance_ids_log: List[str] = []

            # --- 1. Fetch EC2 Instances (running / stopped only) ---
            paginator = ec2.get_paginator("describe_instances")
            for page in paginator.paginate():
                for reservation in page.get("Reservations", []):
                    for inst in reservation.get("Instances", []):
                        state = inst.get("State", {}).get("Name", "unknown")
                        if state not in ("running", "stopped"):
                            continue

                        instance_id = inst["InstanceId"]
                        instance_type = inst.get("InstanceType", "unknown")
                        name = ""
                        tag_map: Dict[str, str] = {}
                        for tag in inst.get("Tags", []) or []:
                            if tag.get("Key") == "Name":
                                name = tag.get("Value") or ""
                            if tag.get("Key"):
                                tag_map[tag["Key"]] = tag.get("Value") or ""
                        do_not_schedule = (tag_map.get("DoNotSchedule") or "").strip().lower() in {"true", "1", "yes"}

                        instance_ids_log.append(instance_id)

                        avg_cpu = self._get_avg_cpu(cw, "AWS/EC2", "InstanceId", instance_id, hours=24)
                        sparkline = self._get_cpu_sparkline(cw, "AWS/EC2", "InstanceId", instance_id, days=7)
                        hourly_cost = INSTANCE_PRICING.get(instance_type, DEFAULT_HOURLY_RATE)
                        monthly_cost = round(hourly_cost * 730, 2)

                        cost_thr = float(os.getenv("SCHEDULER_COST_STOP_THRESHOLD", "0.10"))
                        cost_stop_suggested = (
                            state == "running"
                            and avg_cpu < 5.0
                            and hourly_cost >= cost_thr
                            and not do_not_schedule
                        )

                        existing_schedule = next((s["id"] for s in self._schedules.values() if s["instance_id"] == instance_id), None)

                        resources.append({
                            "instance_id": instance_id,
                            "resource_type": "ec2",
                            "name": name or instance_id,
                            "instance_type": instance_type,
                            "state": state,
                            "az": inst.get("Placement", {}).get("AvailabilityZone", self.region),
                            "avg_cpu_24h": avg_cpu,
                            "cpu_sparkline": sparkline,
                            "hourly_cost": hourly_cost,
                            "estimated_hourly_cost": hourly_cost,
                            "monthly_cost": monthly_cost,
                            "schedule_id": existing_schedule,
                            "do_not_schedule": do_not_schedule,
                            "cost_stop_suggested": cost_stop_suggested,
                            "launch_time": inst.get("LaunchTime", "").isoformat() if hasattr(inst.get("LaunchTime", ""), "isoformat") else str(inst.get("LaunchTime", "")),
                        })

            print("Instances fetched:", instance_ids_log)
                        
            # --- 2. Fetch RDS Instances ---
            try:
                rds_paginator = rds.get_paginator("describe_db_instances")
                for page in rds_paginator.paginate():
                    for db in page.get("DBInstances", []):
                        instance_id = db["DBInstanceIdentifier"]
                        instance_type = db.get("DBInstanceClass", "unknown")
                        state = db.get("DBInstanceStatus", "unknown")
                        name = db.get("DBInstanceIdentifier", "")
                        
                        avg_cpu = self._get_avg_cpu(cw, "AWS/RDS", "DBInstanceIdentifier", instance_id, hours=24)
                        sparkline = self._get_cpu_sparkline(cw, "AWS/RDS", "DBInstanceIdentifier", instance_id, days=7)
                        
                        # RDS instances are generally more expensive, using a 1.2x multiplier on EC2 for fallback estimate
                        hourly_cost = INSTANCE_PRICING.get(instance_type.replace("db.", ""),  DEFAULT_HOURLY_RATE * 1.2)
                        monthly_cost = round(hourly_cost * 730, 2)
                        
                        existing_schedule = next((s["id"] for s in self._schedules.values() if s["instance_id"] == instance_id), None)
                        
                        resources.append({
                            "instance_id": instance_id,
                            "resource_type": "rds",
                            "name": name,
                            "instance_type": instance_type,
                            "state": state,
                            "az": db.get("AvailabilityZone", self.region),
                            "avg_cpu_24h": avg_cpu,
                            "cpu_sparkline": sparkline,
                            "hourly_cost": hourly_cost,
                            "monthly_cost": monthly_cost,
                            "schedule_id": existing_schedule,
                            "launch_time": db.get("InstanceCreateTime", "").isoformat() if hasattr(db.get("InstanceCreateTime", ""), "isoformat") else str(db.get("InstanceCreateTime", "")),
                        })
            except Exception as rds_e:
                logger.error(f"Error getting RDS instances: {rds_e}")

        except Exception as e:
            logger.error(f"Error getting schedulable resources: {e}")

        if not resources and AWS_DEMO_FALLBACK:
            return self.get_demo_schedulable_resources()
        return resources

    def get_demo_schedulable_resources(self) -> List[Dict[str, Any]]:
        """
        Return deterministic demo data compatible with the frontend scheduler UI.
        """
        now = datetime.now(timezone.utc)

        def sparkline(seed: int) -> List[Dict[str, Any]]:
            # 48 points across ~7 days (small enough for the UI sparkline)
            points: List[Dict[str, Any]] = []
            for i in range(48):
                ts = now - timedelta(hours=(47 - i) * 3)
                val = (seed + (i % 12)) % 100
                hour = ts.hour
                # Lower values during "night" hours
                night_factor = 0.25 if (hour >= 20 or hour <= 5) else 1.0
                cpu = round((5 + (val % 70)) * night_factor, 1)
                points.append({"timestamp": ts.isoformat(), "cpu": cpu})
            return points

        demo_region_az = "us-east-1a"

        return [
            {
                "instance_id": "i-demo-001",
                "resource_type": "ec2",
                "name": "Demo Web Server",
                "instance_type": "t3.micro",
                "state": "running",
                "az": demo_region_az,
                "avg_cpu_24h": 12,
                "cpu_sparkline": sparkline(1),
                "hourly_cost": INSTANCE_PRICING.get("t3.micro", DEFAULT_HOURLY_RATE),
                "monthly_cost": round(INSTANCE_PRICING.get("t3.micro", DEFAULT_HOURLY_RATE) * 730, 2),
                "schedule_id": None,
                "launch_time": (now - timedelta(days=30)).isoformat(),
            },
            {
                "instance_id": "i-demo-002",
                "resource_type": "ec2",
                "name": "Demo Worker",
                "instance_type": "t3.small",
                "state": "running",
                "az": demo_region_az,
                "avg_cpu_24h": 42,
                "cpu_sparkline": sparkline(7),
                "hourly_cost": INSTANCE_PRICING.get("t3.small", DEFAULT_HOURLY_RATE),
                "monthly_cost": round(INSTANCE_PRICING.get("t3.small", DEFAULT_HOURLY_RATE) * 730, 2),
                "schedule_id": None,
                "launch_time": (now - timedelta(days=60)).isoformat(),
            },
        ]

    # ------------------------------------------------------------------
    # CloudWatch Analysis
    # ------------------------------------------------------------------

    def _get_avg_cpu(self, cw_client, namespace: str, dim_name: str, instance_id: str, hours: int = 24) -> float:
        """Get average CPU utilization over the given period."""
        try:
            end = datetime.now(timezone.utc)
            start = end - timedelta(hours=hours)
            response = cw_client.get_metric_statistics(
                Namespace=namespace,
                MetricName="CPUUtilization",
                Dimensions=[{"Name": dim_name, "Value": instance_id}],
                StartTime=start,
                EndTime=end,
                Period=3600,
                Statistics=["Average"],
            )
            datapoints = response.get("Datapoints", [])
            if not datapoints:
                return 0.0
            return round(sum(d["Average"] for d in datapoints) / len(datapoints), 1)
        except Exception as e:
            logger.debug(f"Could not get CPU for {instance_id}: {e}")
            return 0.0

    def _get_cpu_sparkline(self, cw_client, namespace: str, dim_name: str, instance_id: str, days: int = 7) -> List[Dict[str, Any]]:
        """Get hourly CPU utilization for sparkline display (sampled to 6h intervals)."""
        try:
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=days)
            response = cw_client.get_metric_statistics(
                Namespace=namespace,
                MetricName="CPUUtilization",
                Dimensions=[{"Name": dim_name, "Value": instance_id}],
                StartTime=start,
                EndTime=end,
                Period=21600,  # 6-hour intervals to keep data manageable
                Statistics=["Average"],
            )
            datapoints = response.get("Datapoints", [])
            # Sort by timestamp
            datapoints.sort(key=lambda d: d["Timestamp"])
            return [
                {
                    "timestamp": d["Timestamp"].isoformat(),
                    "cpu": round(d["Average"], 1),
                }
                for d in datapoints
            ]
        except Exception as e:
            logger.debug(f"Could not get sparkline for {instance_id}: {e}")
            return []

    def analyze_resource(self, instance_id: str) -> Dict[str, Any]:
        """
        Deep analysis of resource usage patterns.
        Returns hourly usage profile + idle windows + suggested schedule.
        """
        try:
            cw = self.session.client("cloudwatch")
            ec2 = self.session.client("ec2", region_name=self.region)

            is_ec2 = instance_id.startswith("i-")
            
            # Get instance info
            instance_info = {}
            if is_ec2:
                try:
                    desc = ec2.describe_instances(InstanceIds=[instance_id])
                    inst = desc["Reservations"][0]["Instances"][0]
                    instance_type = inst.get("InstanceType", "unknown")
                    name = ""
                    for tag in inst.get("Tags", []):
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                            break
                    instance_info = {
                        "instance_id": instance_id,
                        "resource_type": "ec2",
                        "name": name or instance_id,
                        "instance_type": instance_type,
                        "state": inst.get("State", {}).get("Name", "unknown"),
                    }
                except Exception:
                    instance_info = {"instance_id": instance_id, "resource_type": "ec2", "name": instance_id,
                                     "instance_type": "unknown", "state": "unknown"}
                    instance_type = "unknown"
            else:
                try:
                    rds = self.session.client("rds")
                    desc = rds.describe_db_instances(DBInstanceIdentifier=instance_id)
                    db = desc["DBInstances"][0]
                    instance_type = db.get("DBInstanceClass", "unknown")
                    instance_info = {
                        "instance_id": instance_id,
                        "resource_type": "rds",
                        "name": instance_id,
                        "instance_type": instance_type,
                        "state": db.get("DBInstanceStatus", "unknown")
                    }
                except Exception:
                    instance_info = {"instance_id": instance_id, "resource_type": "rds", "name": instance_id,
                                     "instance_type": "unknown", "state": "unknown"}
                    instance_type = "unknown"

            # Fetch 7 days of hourly CPU data
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=7)
            response = cw.get_metric_statistics(
                Namespace="AWS/EC2" if is_ec2 else "AWS/RDS",
                MetricName="CPUUtilization",
                Dimensions=[{"Name": "InstanceId" if is_ec2 else "DBInstanceIdentifier", "Value": instance_id}],
                StartTime=start,
                EndTime=end,
                Period=3600,  # 1-hour granularity
                Statistics=["Average", "Maximum"],
            )
            datapoints = response.get("Datapoints", [])
            datapoints.sort(key=lambda d: d["Timestamp"])

            # Build hourly usage profile (0-23 hours, averaged across 7 days)
            hourly_profile = self._build_hourly_profile(datapoints)

            # Detect idle windows
            idle_threshold = 5.0  # CPU% below which we consider "idle"
            idle_windows = self._detect_idle_windows(hourly_profile, idle_threshold)

            # Calculate potential savings
            hourly_cost = INSTANCE_PRICING.get(instance_type, DEFAULT_HOURLY_RATE)
            idle_hours_per_day = sum(1 for h in hourly_profile if h["avg_cpu"] < idle_threshold)
            monthly_savings = round(hourly_cost * idle_hours_per_day * 30, 2)

            # Generate suggested schedule
            suggested_schedule = self._generate_suggested_schedule(
                instance_id, idle_windows, hourly_cost
            )

            # Overall utilization stats
            all_cpu = [d["Average"] for d in datapoints] if datapoints else [0]
            avg_cpu = round(sum(all_cpu) / len(all_cpu), 1) if all_cpu else 0
            max_cpu = round(max(all_cpu), 1) if all_cpu else 0
            peak_hours = [h["hour"] for h in sorted(hourly_profile, key=lambda x: -x["avg_cpu"])[:4]]

            # Network I/O trend (in bytes, 6h intervals)
            network_in = self._get_network_metric(cw, "AWS/EC2" if is_ec2 else "AWS/RDS", "InstanceId" if is_ec2 else "DBInstanceIdentifier", instance_id, "NetworkIn" if is_ec2 else "NetworkReceiveThroughput", days=7)
            network_out = self._get_network_metric(cw, "AWS/EC2" if is_ec2 else "AWS/RDS", "InstanceId" if is_ec2 else "DBInstanceIdentifier", instance_id, "NetworkOut" if is_ec2 else "NetworkTransmitThroughput", days=7)

            return {
                "instance": instance_info,
                "analysis": {
                    "period": "7 days",
                    "avg_cpu": avg_cpu,
                    "max_cpu": max_cpu,
                    "idle_hours_per_day": idle_hours_per_day,
                    "idle_percentage": round((idle_hours_per_day / 24) * 100, 1),
                    "peak_hours": peak_hours,
                    "hourly_profile": hourly_profile,
                    "idle_windows": idle_windows,
                    "idle_threshold": idle_threshold,
                },
                "network": {
                    "inbound_trend": network_in,
                    "outbound_trend": network_out,
                },
                "savings": {
                    "hourly_cost": hourly_cost,
                    "current_monthly_cost": round(hourly_cost * 730, 2),
                    "estimated_monthly_savings": monthly_savings,
                    "savings_percentage": round((idle_hours_per_day / 24) * 100, 1),
                },
                "suggested_schedule": suggested_schedule,
            }
        except Exception as e:
            logger.error(f"Error analyzing resource {instance_id}: {e}")
            if AWS_DEMO_FALLBACK:
                return self.get_demo_analysis(instance_id)
            return {
                "instance": {"instance_id": instance_id, "name": instance_id},
                "analysis": {"error": str(e)},
                "savings": {},
                "suggested_schedule": None,
            }

    def get_demo_analysis(self, instance_id: str) -> Dict[str, Any]:
        """
        Demo analysis response shaped exactly like the production response.
        """
        hourly_profile: List[Dict[str, Any]] = []
        idle_hours_per_day = 6
        idle_threshold = 5.0

        for hour in range(24):
            is_idle = hour >= 20 or hour <= 5
            avg_cpu = 2.0 if is_idle else 55.0
            peak_cpu = avg_cpu + (0.5 if is_idle else 20.0)
            hourly_profile.append(
                {
                    "hour": hour,
                    "label": f"{hour:02d}:00",
                    "avg_cpu": avg_cpu,
                    "peak_cpu": peak_cpu,
                    "samples": 7,
                }
            )

        idle_windows = [
            {"start": "20:00", "end": "06:00", "duration_hours": idle_hours_per_day, "type": "nightly"}
        ]

        hourly_cost = 0.05
        current_monthly_cost = round(hourly_cost * 730, 2)
        monthly_savings = round(hourly_cost * idle_hours_per_day * 30, 2)

        return {
            "instance": {
                "instance_id": instance_id,
                "resource_type": "ec2",
                "name": instance_id,
                "instance_type": "t3.micro",
                "state": "running",
            },
            "analysis": {
                "period": "7 days",
                "avg_cpu": 18.0,
                "max_cpu": 75.0,
                "idle_hours_per_day": idle_hours_per_day,
                "idle_percentage": round((idle_hours_per_day / 24) * 100, 1),
                "peak_hours": [12, 13, 14, 15],
                "hourly_profile": hourly_profile,
                "idle_windows": idle_windows,
                "idle_threshold": idle_threshold,
            },
            "network": {"inbound_trend": [], "outbound_trend": []},
            "savings": {
                "hourly_cost": hourly_cost,
                "current_monthly_cost": current_monthly_cost,
                "estimated_monthly_savings": monthly_savings,
                "savings_percentage": round((idle_hours_per_day / 24) * 100, 1),
            },
            "suggested_schedule": {
                "type": "ai_suggested",
                "action": "stop_during_idle",
                "stop_time": "20:00",
                "start_time": "06:00",
                "idle_window": idle_windows[0],
                "estimated_monthly_savings": monthly_savings,
                "confidence": 85,
                "description": "Demo recommendation: stop during detected idle window to reduce cost.",
            },
        }

    def _build_hourly_profile(self, datapoints: List[Dict]) -> List[Dict[str, Any]]:
        """Build average CPU usage per hour-of-day across all days."""
        hourly_buckets: Dict[int, List[float]] = {h: [] for h in range(24)}

        for dp in datapoints:
            hour = dp["Timestamp"].hour
            hourly_buckets[hour].append(dp["Average"])

        profile = []
        for hour in range(24):
            values = hourly_buckets[hour]
            avg = round(sum(values) / len(values), 1) if values else 0
            peak = round(max(values), 1) if values else 0
            profile.append({
                "hour": hour,
                "label": f"{hour:02d}:00",
                "avg_cpu": avg,
                "peak_cpu": peak,
                "samples": len(values),
            })
        return profile

    def _detect_idle_windows(self, hourly_profile: List[Dict], threshold: float) -> List[Dict[str, Any]]:
        """Detect contiguous idle windows from hourly profile."""
        windows = []
        current_window = None

        for entry in hourly_profile:
            is_idle = entry["avg_cpu"] < threshold
            if is_idle:
                if current_window is None:
                    current_window = {"start_hour": entry["hour"], "end_hour": entry["hour"]}
                else:
                    current_window["end_hour"] = entry["hour"]
            else:
                if current_window is not None:
                    duration = current_window["end_hour"] - current_window["start_hour"] + 1
                    windows.append({
                        "start": f"{current_window['start_hour']:02d}:00",
                        "end": f"{(current_window['end_hour'] + 1) % 24:02d}:00",
                        "duration_hours": duration,
                        "type": "nightly" if current_window["start_hour"] >= 18 or current_window["start_hour"] < 6 else "daytime",
                    })
                    current_window = None

        # Close any window that extends to end of day
        if current_window is not None:
            duration = current_window["end_hour"] - current_window["start_hour"] + 1
            windows.append({
                "start": f"{current_window['start_hour']:02d}:00",
                "end": f"{(current_window['end_hour'] + 1) % 24:02d}:00",
                "duration_hours": duration,
                "type": "nightly" if current_window["start_hour"] >= 18 else "daytime",
            })

        return windows

    def _generate_suggested_schedule(
        self, instance_id: str, idle_windows: List[Dict], hourly_cost: float
    ) -> Optional[Dict[str, Any]]:
        """Generate a suggested schedule based on detected idle windows."""
        if not idle_windows:
            return None

        # Pick the longest idle window
        best_window = max(idle_windows, key=lambda w: w["duration_hours"])
        monthly_savings = round(hourly_cost * best_window["duration_hours"] * 30, 2)

        return {
            "type": "ai_suggested",
            "action": "stop_during_idle",
            "stop_time": best_window["start"],
            "start_time": best_window["end"],
            "idle_window": best_window,
            "estimated_monthly_savings": monthly_savings,
            "confidence": min(95, 60 + best_window["duration_hours"] * 5),
            "description": (
                f"Stop instance during detected idle window "
                f"({best_window['start']}–{best_window['end']}, "
                f"{best_window['duration_hours']}h/day). "
                f"Saves ~${monthly_savings}/month."
            ),
        }

    def _get_network_metric(
        self, cw_client, namespace: str, dim_name: str, instance_id: str, metric_name: str, days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get network metric trend (6h intervals)."""
        try:
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=days)
            response = cw_client.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=[{"Name": dim_name, "Value": instance_id}],
                StartTime=start,
                EndTime=end,
                Period=21600,
                Statistics=["Sum"],
            )
            datapoints = response.get("Datapoints", [])
            datapoints.sort(key=lambda d: d["Timestamp"])
            return [
                {
                    "timestamp": d["Timestamp"].isoformat(),
                    "bytes": round(d["Sum"], 0),
                    "mb": round(d["Sum"] / (1024 * 1024), 2),
                }
                for d in datapoints
            ]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Schedule Management
    # ------------------------------------------------------------------

    def create_schedule(self, schedule_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new schedule."""
        schedule_id = str(uuid.uuid4())[:8]
        schedule = {
            "id": schedule_id,
            "instance_id": schedule_data["instance_id"],
            "instance_name": schedule_data.get("instance_name", schedule_data["instance_id"]),
            "schedule_type": schedule_data.get("schedule_type", "manual"),  # "manual" or "ai_suggested"
            "stop_time": schedule_data.get("stop_time", "20:00"),
            "start_time": schedule_data.get("start_time", "08:00"),
            "days": schedule_data.get("days", ["mon", "tue", "wed", "thu", "fri"]),
            "enabled": schedule_data.get("enabled", True),
            "estimated_monthly_savings": schedule_data.get("estimated_monthly_savings", 0),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_action": None,
            "total_savings": 0.0,
            "executions": 0,
        }
        self._schedules[schedule_id] = schedule
        logger.info(f"Created schedule {schedule_id} for {schedule['instance_id']}")
        return schedule

    def get_schedules(self) -> List[Dict[str, Any]]:
        """Get all schedules."""
        return list(self._schedules.values())

    def get_schedule(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        """Get a single schedule by ID."""
        return self._schedules.get(schedule_id)

    def update_schedule(self, schedule_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a schedule."""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return None

        updatable_fields = ["stop_time", "start_time", "days", "enabled",
                            "schedule_type", "estimated_monthly_savings"]
        for field in updatable_fields:
            if field in data:
                schedule[field] = data[field]

        schedule["updated_at"] = datetime.now(timezone.utc).isoformat()
        return schedule

    def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule."""
        if schedule_id in self._schedules:
            del self._schedules[schedule_id]
            logger.info(f"Deleted schedule {schedule_id}")
            return True
        return False

    # ------------------------------------------------------------------
    # Action Execution
    # ------------------------------------------------------------------

    def execute_action(self, instance_id: str, action: str) -> Dict[str, Any]:
        """Execute a start/stop action on an instance."""
        result = {
            "id": str(uuid.uuid4())[:8],
            "instance_id": instance_id,
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "message": "",
        }

        try:
            is_ec2 = instance_id.startswith("i-")
            
            if is_ec2:
                ec2 = self.session.client("ec2", region_name=self.region)
                if action == "stop":
                    ec2.stop_instances(InstanceIds=[instance_id])
                    result["status"] = "success"
                    result["message"] = f"Stop command sent to EC2 instance {instance_id}"
                elif action == "start":
                    ec2.start_instances(InstanceIds=[instance_id])
                    result["status"] = "success"
                    result["message"] = f"Start command sent to EC2 instance {instance_id}"
                else:
                    result["message"] = f"Unknown action: {action}"
            else:
                rds = self.session.client("rds")
                if action == "stop":
                    rds.stop_db_instance(DBInstanceIdentifier=instance_id)
                    result["status"] = "success"
                    result["message"] = f"Stop command sent to RDS database {instance_id}"
                elif action == "start":
                    rds.start_db_instance(DBInstanceIdentifier=instance_id)
                    result["status"] = "success"
                    result["message"] = f"Start command sent to RDS database {instance_id}"
                else:
                    result["message"] = f"Unknown action: {action}"

        except Exception as e:
            result["message"] = str(e)
            logger.error(f"Action execution failed for {instance_id}: {e}")

        self._action_history.append(result)
        return result

    def execute_delete_volume(self, volume_id: str) -> Dict[str, Any]:
        """Delete an EBS volume."""
        result = {
            "id": str(uuid.uuid4())[:8],
            "resource_id": volume_id,
            "action": "delete_volume",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "message": "",
        }
        try:
            ec2 = self.session.client("ec2", region_name=self.region)
            ec2.delete_volume(VolumeId=volume_id)
            result["status"] = "success"
            result["message"] = f"Volume {volume_id} deleted successfully"
        except Exception as e:
            result["message"] = str(e)
            logger.error(f"Volume deletion failed for {volume_id}: {e}")

        self._action_history.append(result)
        return result

    def execute_release_eip(self, allocation_id: str) -> Dict[str, Any]:
        """Release an Elastic IP."""
        result = {
            "id": str(uuid.uuid4())[:8],
            "resource_id": allocation_id,
            "action": "release_eip",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "message": "",
        }
        try:
            ec2 = self.session.client("ec2", region_name=self.region)
            ec2.release_address(AllocationId=allocation_id)
            result["status"] = "success"
            result["message"] = f"Elastic IP {allocation_id} released successfully"
        except Exception as e:
            result["message"] = str(e)
            logger.error(f"EIP release failed for {allocation_id}: {e}")

        self._action_history.append(result)
        return result

    def get_action_history(self) -> List[Dict[str, Any]]:
        """Get all action execution history."""
        return list(reversed(self._action_history))  # newest first

    # ------------------------------------------------------------------
    # Savings Summary
    # ------------------------------------------------------------------

    def get_savings_summary(self) -> Dict[str, Any]:
        """Get overall savings summary."""
        active_schedules = [s for s in self._schedules.values() if s["enabled"]]
        total_estimated_monthly = sum(s["estimated_monthly_savings"] for s in active_schedules)
        total_realized = sum(s["total_savings"] for s in self._schedules.values())
        total_executions = sum(s["executions"] for s in self._schedules.values())

        successful_actions = len([a for a in self._action_history if a["status"] == "success"])
        failed_actions = len([a for a in self._action_history if a["status"] == "failed"])

        return {
            "active_schedules": len(active_schedules),
            "total_schedules": len(self._schedules),
            "estimated_monthly_savings": round(total_estimated_monthly, 2),
            "estimated_annual_savings": round(total_estimated_monthly * 12, 2),
            "total_realized_savings": round(total_realized, 2),
            "total_executions": total_executions,
            "actions_executed": successful_actions + failed_actions,
            "actions_successful": successful_actions,
            "actions_failed": failed_actions,
            "success_rate": round((successful_actions / max(successful_actions + failed_actions, 1)) * 100, 1),
        }
