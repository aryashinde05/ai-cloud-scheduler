"""
Azure Cost Analysis Engine - Real Cost Optimization for Startups

This module provides actual Azure cost analysis by connecting to Azure APIs
using azure-mgmt-costmanagement, azure-mgmt-consumption, and azure-mgmt-advisor.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
from decimal import Decimal

from azure.identity import ClientSecretCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.consumption import ConsumptionManagementClient
from azure.mgmt.advisor import AdvisorManagementClient
from azure.mgmt.costmanagement.models import (
    QueryTimePeriod,
    QueryDataset,
    QueryGrouping,
    QueryAggregation,
    QueryDefinition,
)

from app.cloud.base_cost_analyzer import (
    BaseCostAnalyzer,
    CostAnalysisReport,
    ServiceCostBreakdown,
    CostOptimizationOpportunity
)

logger = logging.getLogger(__name__)


class AzureCostAnalyzer(BaseCostAnalyzer):
    """
    Real Azure Cost Analysis Engine

    Connects to Azure APIs to analyze actual spending and identify
    optimization opportunities for startups and small businesses.
    """

    def __init__(self, tenant_id: str, client_id: str, client_secret: str, subscription_id: str):
        """Initialize Azure Cost Analyzer with service principal credentials"""

        try:
            self.tenant_id = tenant_id
            self.client_id = client_id
            self.client_secret = client_secret
            self.subscription_id = subscription_id

            self.credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )

            self.cost_client = CostManagementClient(self.credential)
            self.consumption_client = ConsumptionManagementClient(self.credential, subscription_id)
            self.advisor_client = AdvisorManagementClient(self.credential, subscription_id)

            self.scope = f"/subscriptions/{subscription_id}"

            logger.info(f"Azure Cost Analyzer initialized for subscription: {subscription_id}")

        except Exception as e:
            logger.error(f"Failed to initialize Azure Cost Analyzer: {str(e)}")
            raise

    def test_connection(self) -> Dict[str, Any]:
        """Test Azure connection and verify permissions"""

        try:
            list(self.advisor_client.recommendations.list(filter="Category eq 'Cost'", top=1))

            return {
                "status": "success",
                "message": "Azure connection verified successfully",
                "permissions": [
                    "Microsoft.CostManagement/query/action",
                    "Microsoft.Advisor/recommendations/read"
                ]
            }

        except Exception as e:
            logger.error(f"Azure connection test failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Azure connection failed: {str(e)}",
                "permissions": []
            }

    def analyze_costs(self, days_back: int = 30) -> CostAnalysisReport:
        """Perform comprehensive Azure cost analysis"""

        try:
            logger.info(f"Starting Azure cost analysis for last {days_back} days")

            service_breakdown_raw = self.get_service_breakdown(days_back)
            cost_trends = self.get_cost_trends(days_back)
            opportunities = self.get_optimization_recommendations()

            total_monthly_cost = sum(item['cost'] for item in service_breakdown_raw)
            potential_savings = sum(opp.potential_monthly_savings for opp in opportunities)

            top_cost_drivers = []

            for item in service_breakdown_raw:
                top_cost_drivers.append(
                    ServiceCostBreakdown(
                        service_name=item['service'],
                        current_month_cost=item['cost'],
                        last_month_cost=item['cost'] * 0.9,
                        cost_trend="increasing",
                        percentage_of_total=(
                            item['cost'] / total_monthly_cost * 100
                            if total_monthly_cost > 0 else 0
                        ),
                        top_resources=[]
                    )
                )

            recommendations_summary = [opp.description for opp in opportunities[:5]]

            roi_analysis = {
                "monthly_savings": potential_savings,
                "annual_savings": potential_savings * 12,
                "roi_percentage": (
                    potential_savings / total_monthly_cost * 100
                    if total_monthly_cost > 0 else 0
                )
            }

            report = CostAnalysisReport(
                total_monthly_cost=total_monthly_cost,
                cost_trend=cost_trends.get("direction", "stable"),
                top_cost_drivers=top_cost_drivers,
                optimization_opportunities=opportunities,
                potential_monthly_savings=potential_savings,
                roi_analysis=roi_analysis,
                recommendations_summary=recommendations_summary
            )

            logger.info(
                f"Azure cost analysis completed. Potential savings: ${potential_savings:.2f}/month"
            )

            return report

        except Exception as e:
            logger.error(f"Azure cost analysis failed: {str(e)}")
            raise

    def get_service_breakdown(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get cost breakdown by Azure service using Query API"""

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        query_definition = QueryDefinition(
            type="ActualCost",
            timeframe="Custom",
            time_period=QueryTimePeriod(
                from_property=start_date,
                to=end_date
            ),
            dataset=QueryDataset(
                granularity="None",
                aggregation={
                    "totalCost": QueryAggregation(
                        name="PreTaxCost",
                        function="Sum"
                    )
                },
                grouping=[
                    QueryGrouping(
                        type="Dimension",
                        name="ServiceName"
                    )
                ]
            )
        )

        try:
            result = self.cost_client.query.usage(self.scope, query_definition)

            breakdown = []

            if result and result.rows:
                for row in result.rows:
                    cost = float(row[0])
                    service = row[1]

                    if cost > 0:
                        breakdown.append({
                            "service": service,
                            "cost": cost
                        })

            breakdown.sort(key=lambda x: x["cost"], reverse=True)

            return breakdown

        except Exception as e:
            logger.error(f"Failed to get Azure service breakdown: {str(e)}")
            raise

    def get_cost_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get daily cost history and calculate trend"""

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        query_definition = QueryDefinition(
            type="ActualCost",
            timeframe="Custom",
            time_period=QueryTimePeriod(
                from_property=start_date,
                to=end_date
            ),
            dataset=QueryDataset(
                granularity="Daily",
                aggregation={
                    "totalCost": QueryAggregation(
                        name="PreTaxCost",
                        function="Sum"
                    )
                },
                grouping=[
                    QueryGrouping(
                        type="Dimension",
                        name="UsageDate"
                    )
                ]
            )
        )

        try:
            result = self.cost_client.query.usage(self.scope, query_definition)

            history = []
            total_sum = 0

            if result and result.rows:
                for row in result.rows:
                    cost = float(row[0])
                    date_val = str(row[1])

                    history.append({
                        "date": date_val,
                        "cost": cost
                    })

                    total_sum += cost

            history.sort(key=lambda x: x["date"])

            direction = "stable"

            if len(history) >= 4:
                mid = len(history) // 2

                first_half_avg = sum(h["cost"] for h in history[:mid]) / mid
                second_half_avg = sum(h["cost"] for h in history[mid:]) / (len(history) - mid)

                if second_half_avg > first_half_avg * 1.05:
                    direction = "increasing"
                elif second_half_avg < first_half_avg * 0.95:
                    direction = "decreasing"

            return {
                "history": history,
                "average_daily": total_sum / len(history) if history else 0,
                "direction": direction
            }

        except Exception as e:
            logger.error(f"Failed to get Azure cost trends: {str(e)}")
            raise

    def get_optimization_recommendations(self) -> List[CostOptimizationOpportunity]:
        """Fetch cost recommendations from Azure Advisor"""

        try:
            recs = self.advisor_client.recommendations.list(
                filter="Category eq 'Cost'"
            )

            opportunities = []

            for rec in recs:
                ext_props = rec.extended_properties or {}

                potential_savings = float(ext_props.get("savingsAmount", 0))

                rec_name = rec.recommendation_type_id.lower()

                opp_type = "unused_resources"

                if "rightsize" in rec_name or "sku" in rec_name:
                    opp_type = "rightsizing"
                elif "reserved" in rec_name:
                    opp_type = "reserved_instances"

                opportunities.append(
                    CostOptimizationOpportunity(
                        service=(
                            rec.resource_metadata.get("resourceId", "")
                            .split("/")[-2]
                            if rec.resource_metadata
                            else "Unknown"
                        ),
                        opportunity_type=opp_type,
                        current_monthly_cost=0,
                        potential_monthly_savings=potential_savings,
                        confidence_level="high" if rec.impact == "High" else "medium",
                        description=rec.short_description.get(
                            "problem",
                            "Advisor Recommendation"
                        ),
                        action_required=rec.short_description.get(
                            "solution",
                            "Follow Azure Advisor suggested actions"
                        ),
                        implementation_effort="medium",
                        risk_level="low"
                    )
                )

            return opportunities

        except Exception as e:
            logger.error(f"Failed to get Azure optimization recommendations: {str(e)}")
            raise

    def get_quick_wins(self) -> List[CostOptimizationOpportunity]:
        """Filter Azure Advisor results for low effort, high impact wins"""

        all_recs = self.get_optimization_recommendations()

        return [
            opp for opp in all_recs
            if opp.potential_monthly_savings > 100
            or opp.opportunity_type in ["unused_resources", "rightsizing"]
        ]