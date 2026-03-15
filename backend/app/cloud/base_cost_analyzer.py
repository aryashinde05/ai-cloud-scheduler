from abc import ABC, abstractmethod
from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class CostOptimizationOpportunity:
    """Represents a specific cost optimization opportunity"""
        
    service: str
    opportunity_type: str  # 'rightsizing', 'unused_resources', 'reserved_instances', 'storage_optimization'
    current_monthly_cost: float
    potential_monthly_savings: float
    confidence_level: str  # 'high', 'medium', 'low'
    description: str
    action_required: str
    implementation_effort: str  # 'low', 'medium', 'high'
    risk_level: str  # 'low', 'medium', 'high'


@dataclass
class ServiceCostBreakdown:
    """Cost breakdown by cloud service"""

    service_name: str
    current_month_cost: float
    last_month_cost: float
    cost_trend: str  # 'increasing', 'decreasing', 'stable'
    percentage_of_total: float
    top_resources: List[Dict[str, Any]]


@dataclass
class CostAnalysisReport:
    """Complete cost analysis report"""

    total_monthly_cost: float
    cost_trend: str
    top_cost_drivers: List[ServiceCostBreakdown]
    optimization_opportunities: List[CostOptimizationOpportunity]
    potential_monthly_savings: float
    roi_analysis: Dict[str, Any]
    recommendations_summary: List[str]


class BaseCostAnalyzer(ABC):
    """
    Abstract Base Class for Cloud Cost Analyzers
    """

    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """Test connection to the cloud provider"""
        pass

    @abstractmethod
    def analyze_costs(self, days_back: int = 30) -> CostAnalysisReport:
        """Perform comprehensive cost analysis"""
        pass

    @abstractmethod
    def get_service_breakdown(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get cost breakdown by service"""
        pass

    @abstractmethod
    def get_cost_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get cost trends over time"""
        pass

    @abstractmethod
    def get_optimization_recommendations(self) -> List[CostOptimizationOpportunity]:
        """Get optimization recommendations from cloud advisor/optimizer"""
        pass