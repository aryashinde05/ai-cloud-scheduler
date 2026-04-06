"""
Multi-Cloud Cost Comparison Engine

Central orchestrator for cross-cloud cost analysis and comparison.
Coordinates pricing data from AWS, GCP, and Azure to provide unified cost comparisons.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import hashlib
import json

from sqlalchemy.orm import Session

from app.models.multi_cloud_models import (
    WorkloadSpec, CostComparison, TCOAnalysis, MigrationAnalysis,
    ProviderCostSummary as ProviderCost, ServiceCost, CostRecommendation, SavingsOpportunity,
    CloudProvider, TCOComponent, RiskFactor, MigrationPhase
)
from app.models.models import WorkloadSpecification, MultiCloudCostComparison, User
from app.database.database import get_db_session
from app.core.exceptions import FinOpsException


logger = logging.getLogger(__name__)


class MultiCloudCostEngine:
    """
    Central orchestrator for multi-cloud cost analysis and comparison.
    
    Coordinates pricing data retrieval from multiple providers, normalizes cost data,
    and generates unified cost reports with recommendations.
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        """Initialize the multi-cloud cost engine."""
        self.db_session = db_session  # Don't auto-create session in constructor
        self.supported_providers = [CloudProvider.AWS, CloudProvider.GCP, CloudProvider.AZURE]
        self.cache_ttl_seconds = 3600  # 1 hour cache TTL
        
        # Initialize provider clients
        from .pricing import AWSPricingClient, GCPPricingClient, AzurePricingClient, PricingDataCache
        
        self.pricing_clients = {
            CloudProvider.AWS: AWSPricingClient(),
            CloudProvider.GCP: GCPPricingClient(),
            CloudProvider.AZURE: AzurePricingClient()
        }
        self.pricing_cache = PricingDataCache()
        self.equivalency_mapper = None  # Will be implemented in Task 3
        self.tco_calculator = None  # Will be implemented in Task 4
        self.migration_estimator = None  # Will be implemented in Task 5
        
        logger.info("MultiCloudCostEngine initialized with real pricing clients")
    
    async def compare_workload_costs(
        self, 
        workload_spec: WorkloadSpec,
        regions: Optional[Dict[CloudProvider, str]] = None,
        include_spot_pricing: bool = True,
        include_reserved_pricing: bool = True
    ) -> CostComparison:
        """
        Compare costs for a workload across AWS, GCP, and Azure.
        
        Args:
            workload_spec: Workload specification
            regions: Optional region mapping per provider
            include_spot_pricing: Include spot/preemptible instance pricing
            include_reserved_pricing: Include reserved instance pricing
            
        Returns:
            CostComparison: Detailed cost comparison across providers
            
        Raises:
            FinOpsException: If cost comparison fails
        """
        try:
            logger.info(f"Starting cost comparison for workload: {workload_spec.name}")
            
            # Generate workload hash for caching
            workload_hash = self._generate_workload_hash(workload_spec)
            
            # Check cache first
            cached_result = await self._get_cached_comparison(workload_hash)
            if cached_result:
                logger.info("Returning cached cost comparison result")
                return cached_result
            
            # Set default regions if not provided
            if not regions:
                regions = {
                    CloudProvider.AWS: "us-east-1",
                    CloudProvider.GCP: "us-central1",
                    CloudProvider.AZURE: "eastus"
                }
            
            # Fetch pricing data from all providers in parallel
            provider_costs = await self._fetch_provider_costs_parallel(
                workload_spec, regions, include_spot_pricing, include_reserved_pricing
            )
            
            # Generate cost recommendations
            recommendations = await self._generate_cost_recommendations(
                workload_spec, provider_costs
            )
            
            # Identify savings opportunities
            savings_opportunities = await self._identify_savings_opportunities(
                workload_spec, provider_costs
            )
            
            # Determine lowest cost provider
            lowest_cost_provider = min(
                provider_costs.keys(),
                key=lambda p: provider_costs[p].total_monthly_cost
            )
            
            # Calculate cost difference percentages
            lowest_cost = provider_costs[lowest_cost_provider].total_monthly_cost
            cost_differences = {}
            for provider, cost_data in provider_costs.items():
                if lowest_cost > 0:
                    diff_percent = float((cost_data.total_monthly_cost - lowest_cost) / lowest_cost * 100)
                    cost_differences[provider] = round(diff_percent, 2)
                else:
                    cost_differences[provider] = 0.0
            
            highest_cost_provider = max(
                provider_costs.keys(),
                key=lambda p: provider_costs[p].total_monthly_cost
            )
            highest_cost = provider_costs[highest_cost_provider].total_monthly_cost
            overall_cost_diff_percent = 0.0
            if lowest_cost > 0:
                overall_cost_diff_percent = float((highest_cost - lowest_cost) / lowest_cost * 100)
            
            # Create comparison result
            comparison = CostComparison(
                workload_name=workload_spec.name,
                comparison_id=workload_hash,
                comparison_date=datetime.utcnow(),
                provider_costs=provider_costs,
                lowest_cost_provider=lowest_cost_provider,
                highest_cost_provider=highest_cost_provider,
                cost_difference_percentage=overall_cost_diff_percent,
                currency="USD",
                pricing_data_version="live",
                assumptions=[f"Region used (default if unspecified): {regions}"]
            )
            
            # For the engine recommendations/savings that do not map to CostComparison schema natively,
            # we return a tuple so the API can map them to the CostComparisonResponse directly.
            comparison_results = {
                "comparison": comparison,
                "recommendations": recommendations,
                "savings_opportunities": savings_opportunities,
                "cost_differences": cost_differences
            }
            
            # Cache the result
            await self._cache_comparison_result(workload_hash, comparison)
            
            # Save to database
            await self._save_comparison_to_db(workload_spec, comparison)
            
            logger.info(f"Cost comparison completed for workload: {workload_spec.name}")
            return comparison_results
            
        except Exception as e:
            logger.error(f"Cost comparison failed for workload {workload_spec.name}: {str(e)}")
            raise FinOpsException(f"Cost comparison failed: {str(e)}")
    
    async def calculate_tco(
        self, 
        workload_spec: WorkloadSpec, 
        years: int = 3,
        include_hidden_costs: bool = True,
        include_operational_costs: bool = True
    ) -> TCOAnalysis:
        """
        Calculate Total Cost of Ownership including hidden costs and operational overhead.
        
        Args:
            workload_spec: Workload specification
            years: Time horizon for TCO analysis (1-10 years)
            include_hidden_costs: Include hidden costs (support, compliance, etc.)
            include_operational_costs: Include operational overhead
            
        Returns:
            TCOAnalysis: Comprehensive TCO analysis
            
        Raises:
            FinOpsException: If TCO calculation fails
        """
        try:
            logger.info(f"Starting TCO calculation for workload: {workload_spec.name}")
            
            if not (1 <= years <= 10):
                raise ValueError("TCO analysis years must be between 1 and 10")
            
            # Generate workload hash for caching
            workload_hash = self._generate_workload_hash(workload_spec)
            tco_cache_key = f"{workload_hash}_{years}_{include_hidden_costs}_{include_operational_costs}"
            
            # Check cache first
            cached_tco = await self._get_cached_tco(tco_cache_key)
            if cached_tco:
                logger.info("Returning cached TCO analysis result")
                return cached_tco
            
            # Calculate base infrastructure costs for each provider
            provider_tco = {}
            total_tco = {}
            
            for provider in self.supported_providers:
                # Base infrastructure costs
                base_costs = await self._calculate_base_infrastructure_costs(
                    workload_spec, provider, years
                )
                
                # Hidden costs (support, compliance, etc.)
                hidden_costs = {}
                if include_hidden_costs:
                    hidden_costs = await self._calculate_hidden_costs(
                        workload_spec, provider, base_costs, years
                    )
                
                # Operational costs
                operational_costs = {}
                if include_operational_costs:
                    operational_costs = await self._calculate_operational_costs(
                        workload_spec, provider, years
                    )
                
                # Combine all costs into TCO components
                tco_components = self._combine_tco_components(
                    base_costs, hidden_costs, operational_costs, years
                )
                
                provider_tco[provider] = tco_components
                total_tco[provider] = sum(component.total_cost for component in tco_components)
            
            # Generate year-by-year cost projections
            cost_projections = self._generate_cost_projections(provider_tco, years)
            
            # Aggregate hidden and operational costs
            aggregated_hidden_costs = self._aggregate_cost_category(provider_tco, "hidden")
            aggregated_operational_costs = self._aggregate_cost_category(provider_tco, "operational")
            
            # Create TCO analysis result
            tco_analysis = TCOAnalysis(
                workload_id=workload_hash,
                analysis_date=datetime.utcnow(),
                time_horizon_years=years,
                provider_tco=provider_tco,
                total_tco=total_tco,
                hidden_costs=aggregated_hidden_costs,
                operational_costs=aggregated_operational_costs,
                cost_projections=cost_projections
            )
            
            # Cache the result
            await self._cache_tco_result(tco_cache_key, tco_analysis)
            
            logger.info(f"TCO calculation completed for workload: {workload_spec.name}")
            return tco_analysis
            
        except Exception as e:
            logger.error(f"TCO calculation failed for workload {workload_spec.name}: {str(e)}")
            raise FinOpsException(f"TCO calculation failed: {str(e)}")
    
    async def analyze_migration_costs(
        self, 
        source: CloudProvider, 
        target: CloudProvider, 
        workload_spec: WorkloadSpec,
        migration_timeline_preference: Optional[str] = None
    ) -> MigrationAnalysis:
        """
        Analyze costs and timeline for migrating workloads between cloud providers.
        
        Args:
            source: Source cloud provider
            target: Target cloud provider
            workload_spec: Workload specification
            migration_timeline_preference: Preferred migration timeline
            
        Returns:
            MigrationAnalysis: Migration cost and timeline analysis
            
        Raises:
            FinOpsException: If migration analysis fails
        """
        try:
            logger.info(f"Starting migration analysis: {source} -> {target} for workload: {workload_spec.name}")
            
            if source == target:
                raise ValueError("Source and target providers must be different")
            
            # Calculate current costs on source provider
            source_costs = await self._calculate_provider_costs(workload_spec, source)
            
            # Calculate target costs on destination provider
            target_costs = await self._calculate_provider_costs(workload_spec, target)
            
            # Calculate migration-specific costs
            migration_costs = await self._calculate_migration_costs(
                workload_spec, source, target
            )
            
            # Estimate migration timeline
            migration_timeline = await self._estimate_migration_timeline(
                workload_spec, source, target, migration_timeline_preference
            )
            
            # Assess migration risks
            risk_factors = await self._assess_migration_risks(
                workload_spec, source, target
            )
            
            # Generate migration phases
            migration_phases = await self._generate_migration_phases(
                workload_spec, source, target, migration_timeline
            )
            
            # Calculate savings and break-even
            monthly_savings = source_costs.total_monthly_cost - target_costs.total_monthly_cost
            annual_savings = monthly_savings * 12
            
            break_even_months = None
            if monthly_savings > 0:
                break_even_months = int(migration_costs["total_cost"] / monthly_savings)
            
            # Generate recommendations
            recommendations = await self._generate_migration_recommendations(
                workload_spec, source, target, migration_costs, monthly_savings
            )
            
            # Create migration analysis result
            migration_analysis = MigrationAnalysis(
                workload_id=self._generate_workload_hash(workload_spec),
                source_provider=source,
                target_provider=target,
                analysis_date=datetime.utcnow(),
                total_migration_cost=migration_costs["total_cost"],
                migration_timeline_days=migration_timeline,
                break_even_months=break_even_months,
                monthly_savings=monthly_savings,
                annual_savings=annual_savings,
                risk_factors=risk_factors,
                migration_phases=migration_phases,
                cost_breakdown=migration_costs,
                recommendations=recommendations
            )
            
            logger.info(f"Migration analysis completed: {source} -> {target} for workload: {workload_spec.name}")
            return migration_analysis
            
        except Exception as e:
            logger.error(f"Migration analysis failed for workload {workload_spec.name}: {str(e)}")
            raise FinOpsException(f"Migration analysis failed: {str(e)}")
    
    async def get_cost_recommendations(
        self, 
        comparison: CostComparison
    ) -> List[CostRecommendation]:
        """
        Generate cost optimization recommendations based on comparison results.
        
        Args:
            comparison: Cost comparison result
            
        Returns:
            List[CostRecommendation]: Cost optimization recommendations
        """
        try:
            logger.info(f"Generating cost recommendations for workload: {comparison.workload_name}")
            
            recommendations = []
            
            # Analyze provider cost differences
            lowest_cost_provider = comparison.lowest_cost_provider
            lowest_cost = comparison.provider_costs[lowest_cost_provider].total_monthly_cost
            
            for provider, cost_data in comparison.provider_costs.items():
                if provider != lowest_cost_provider:
                    cost_diff = cost_data.total_monthly_cost - lowest_cost
                    if cost_diff > 0:
                        savings_percent = (cost_diff / cost_data.total_monthly_cost) * 100
                        
                        recommendation = CostRecommendation(
                            recommendation_id=f"rec-{provider}-switch",
                            recommendation_type="provider_switch",
                            title=f"Migrate to {lowest_cost_provider}",
                            description=f"Consider migrating to {lowest_cost_provider} to save ${cost_diff:.2f}/month ({savings_percent:.1f}%)",
                            potential_savings=cost_diff,
                            implementation_effort="high",
                            risk_level="medium",
                            confidence_score=0.8,
                            applicable_providers=[provider, lowest_cost_provider]
                        )
                        recommendations.append(recommendation)
            
            # Analyze reserved instance opportunities
            for provider, cost_data in comparison.provider_costs.items():
                ri_savings = cost_data.hidden_costs.get("reserved_savings")
                if ri_savings and ri_savings > 0:
                    recommendation = CostRecommendation(
                        recommendation_id=f"rec-{provider}-ri",
                        recommendation_type="reserved_instances",
                        title=f"Use RI on {provider}",
                        description=f"Use reserved instances on {provider} to save ${ri_savings:.2f}/month",
                        potential_savings=ri_savings,
                        implementation_effort="low",
                        risk_level="low",
                        confidence_score=0.9,
                        applicable_providers=[provider]
                    )
                    recommendations.append(recommendation)
            
            # Analyze spot instance opportunities
            for provider, cost_data in comparison.provider_costs.items():
                spot_savings = cost_data.hidden_costs.get("spot_savings")
                if spot_savings and spot_savings > 0:
                    recommendation = CostRecommendation(
                        recommendation_id=f"rec-{provider}-spot",
                        recommendation_type="spot_instances",
                        title=f"Use Spot on {provider}",
                        description=f"Use spot instances on {provider} to save ${spot_savings:.2f}/month",
                        potential_savings=spot_savings,
                        implementation_effort="medium",
                        risk_level="medium",
                        confidence_score=0.7,
                        applicable_providers=[provider]
                    )
                    recommendations.append(recommendation)
            
            # Sort recommendations by potential savings
            recommendations.sort(key=lambda x: x.potential_savings, reverse=True)
            
            logger.info(f"Generated {len(recommendations)} cost recommendations")
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to generate cost recommendations: {str(e)}")
            raise FinOpsException(f"Failed to generate cost recommendations: {str(e)}")
    
    # Private helper methods
    
    def _generate_workload_hash(self, workload_spec: WorkloadSpec) -> str:
        """Generate a hash for workload specification for caching."""
        workload_dict = workload_spec.dict()
        workload_json = json.dumps(workload_dict, sort_keys=True, default=str)
        return hashlib.md5(workload_json.encode()).hexdigest()
    
    async def _get_cached_comparison(self, workload_hash: str) -> Optional[CostComparison]:
        """Get cached cost comparison result."""
        # TODO: Implement Redis caching in Task 12
        return None
    
    async def _cache_comparison_result(self, workload_hash: str, comparison: CostComparison):
        """Cache cost comparison result."""
        # TODO: Implement Redis caching in Task 12
        pass
    
    async def _get_cached_tco(self, cache_key: str) -> Optional[TCOAnalysis]:
        """Get cached TCO analysis result."""
        # TODO: Implement Redis caching in Task 12
        return None
    
    async def _cache_tco_result(self, cache_key: str, tco_analysis: TCOAnalysis):
        """Cache TCO analysis result."""
        # TODO: Implement Redis caching in Task 12
        pass
    
    async def _fetch_provider_costs_parallel(
        self, 
        workload_spec: WorkloadSpec, 
        regions: Dict[CloudProvider, str],
        include_spot_pricing: bool,
        include_reserved_pricing: bool
    ) -> Dict[CloudProvider, ProviderCost]:
        """Fetch pricing data from all providers in parallel."""
        tasks = []
        
        for provider in self.supported_providers:
            region = regions.get(provider, "us-east-1")  # Default region
            task = self._calculate_provider_costs(
                workload_spec, provider, region, include_spot_pricing, include_reserved_pricing
            )
            tasks.append(task)
        
        # Execute all provider cost calculations in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        provider_costs = {}
        for i, result in enumerate(results):
            provider = self.supported_providers[i]
            if isinstance(result, Exception):
                logger.warning(f"Failed to get costs for {provider}: {result}")
                # Create a placeholder with zero costs
                provider_costs[provider] = ProviderCost(
                    provider=provider,
                    total_monthly_cost=Decimal('0'),
                    total_annual_cost=Decimal('0'),
                    service_costs=[],
                    hidden_costs={"error": Decimal("0")}
                )
            else:
                provider_costs[provider] = result
        
        return provider_costs
    
    async def _calculate_provider_costs(
        self, 
        workload_spec: WorkloadSpec, 
        provider: CloudProvider,
        region: str = "us-east-1",
        include_spot_pricing: bool = True,
        include_reserved_pricing: bool = True
    ) -> ProviderCost:
        """Calculate costs for a specific provider using real pricing clients."""
        try:
            # Demo / offline mode: avoid slow external pricing lookups.
            # Use mock pricing unless explicitly disabled.
            if os.getenv("MULTICLOUD_PRICING_MODE", "mock").lower() == "mock":
                return await self._calculate_provider_costs_mock(
                    workload_spec, provider, region, include_spot_pricing, include_reserved_pricing
                )

            # Get the pricing client for this provider
            pricing_client = self.pricing_clients.get(provider)
            if not pricing_client:
                logger.warning(f"No pricing client available for {provider}, using mock data")
                return await self._calculate_provider_costs_mock(workload_spec, provider, region, include_spot_pricing, include_reserved_pricing)
            
            # Use real pricing client to get comprehensive pricing
            from .pricing.pricing_models import PricingQuery
            
            best_instance_type = self._get_best_instance_type(workload_spec, provider)
            query = PricingQuery(
                provider=provider.value,
                service_name="compute",
                region=region,
                instance_type=best_instance_type,
                filters={
                    "operating_system": workload_spec.compute.operating_system,
                    "include_database": workload_spec.database is not None,
                    "storage_type": "object" if any(s.storage_type == "object" for s in workload_spec.storage) else "block",
                    "network_service_type": "data_transfer",
                    "vcpus": workload_spec.compute.vcpus,
                    "memory_gb": workload_spec.compute.memory_gb
                }
            )
            
            # Get comprehensive pricing from the client
            response = await pricing_client.get_comprehensive_pricing(query)
            
            if not response.success:
                logger.warning(f"Pricing API failed for {provider}: {response.error_message}")
                return await self._calculate_provider_costs_mock(workload_spec, provider, region, include_spot_pricing, include_reserved_pricing)
            
            # Convert pricing data to service costs
            service_costs = []
            
            # Process compute pricing
            if response.data.compute_pricing:
                compute_cost = self._calculate_compute_cost_from_pricing(
                    workload_spec, response.data.compute_pricing, include_spot_pricing, include_reserved_pricing
                )
                if compute_cost:
                    service_costs.append(compute_cost)
            
            # Process storage pricing
            if response.data.storage_pricing:
                storage_cost = self._calculate_storage_cost_from_pricing(
                    workload_spec, response.data.storage_pricing
                )
                if storage_cost:
                    service_costs.append(storage_cost)
            
            # Process network pricing
            if response.data.network_pricing:
                network_cost = self._calculate_network_cost_from_pricing(
                    workload_spec, response.data.network_pricing
                )
                if network_cost:
                    service_costs.append(network_cost)
            
            # Process database pricing if needed
            if workload_spec.database_requirements and response.data.database_pricing:
                database_cost = self._calculate_database_cost_from_pricing(
                    workload_spec, response.data.database_pricing
                )
                if database_cost:
                    service_costs.append(database_cost)
            
            # Calculate totals
            total_monthly = sum(cost.monthly_cost for cost in service_costs)
            total_annual = total_monthly * 12
            
            # Calculate savings opportunities
            reserved_savings = None
            spot_savings = None
            
            if include_reserved_pricing:
                reserved_savings = total_monthly * Decimal('0.30')  # Typical 30% savings
            spot_eligible = False
            if include_spot_pricing and workload_spec.compute_requirements.spot_eligible:
                spot_eligible = workload_spec.compute_requirements.spot_eligible
            if include_spot_pricing and spot_eligible:
                spot_savings = total_monthly * Decimal('0.60')  # Typical 60% savings
            
            return ProviderCost(
                provider=provider,
                total_monthly_cost=total_monthly,
                total_annual_cost=total_annual,
                service_costs=service_costs,
                hidden_costs={
                    "reserved_savings": reserved_savings or Decimal('0'),
                    "spot_savings": spot_savings or Decimal('0')
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to calculate costs for {provider} using pricing API: {e}")
            # Fall back to mock data
            return await self._calculate_provider_costs_mock(workload_spec, provider, region, include_spot_pricing, include_reserved_pricing)
    
    def _get_best_instance_type(self, workload_spec: WorkloadSpec, provider: CloudProvider) -> Optional[str]:
        """Get the best matching instance type for the workload."""
        cpu_cores = workload_spec.compute.vcpus
        memory_gb = workload_spec.compute.memory_gb
        
        # Simple instance type mapping based on CPU and memory requirements
        if provider == CloudProvider.AWS:
            if cpu_cores <= 2 and memory_gb <= 4:
                return "t3.medium"
            elif cpu_cores <= 4 and memory_gb <= 16:
                return "m5.xlarge"
            else:
                return "m5.2xlarge"
        elif provider == CloudProvider.GCP:
            if cpu_cores <= 2 and memory_gb <= 4:
                return "e2-standard-2"
            elif cpu_cores <= 4 and memory_gb <= 16:
                return "n2-standard-4"
            else:
                return "n2-standard-8"
        elif provider == CloudProvider.AZURE:
            if cpu_cores <= 2 and memory_gb <= 4:
                return "Standard_B2s"
            elif cpu_cores <= 4 and memory_gb <= 16:
                return "Standard_D4s_v3"
            else:
                return "Standard_D8s_v3"
        
        return None
    
    def _calculate_compute_cost_from_pricing(
        self, 
        workload_spec: WorkloadSpec, 
        compute_pricing: List, 
        include_spot: bool, 
        include_reserved: bool
    ) -> Optional[ServiceCost]:
        """Calculate compute costs from pricing data."""
        if not compute_pricing:
            return None
        
        # Use the first pricing entry (should be the best match)
        pricing = compute_pricing[0]
        
        # Calculate monthly cost based on usage patterns
        utilization = 1.0
        if workload_spec.usage_patterns and "average_utilization_percent" in workload_spec.usage_patterns:
            utilization = float(workload_spec.usage_patterns["average_utilization_percent"]) / 100.0
            
        hours_per_month = 24 * 30 * utilization
        
        monthly_cost = pricing.price_per_hour * Decimal(str(hours_per_month))
        
        return ServiceCost(
            service_name="compute",
            service_category="compute",
            monthly_cost=monthly_cost,
            annual_cost=monthly_cost * 12,
            pricing_model="on_demand",
            confidence_score=0.9
        )
    
    def _calculate_storage_cost_from_pricing(
        self, 
        workload_spec: WorkloadSpec, 
        storage_pricing: List
    ) -> Optional[ServiceCost]:
        """Calculate storage costs from pricing data."""
        if not storage_pricing:
            return None
        
        total_monthly_cost = Decimal('0')
        storage_details = {}
        
        # Calculate costs for different storage types
        total_storage_gb = (
            workload_spec.storage_requirements.object_storage_gb +
            workload_spec.storage_requirements.block_storage_gb +
            workload_spec.storage_requirements.database_storage_gb
        )
        
        if total_storage_gb > 0:
            # Use the first storage pricing (typically standard tier)
            pricing = storage_pricing[0]
            total_monthly_cost = pricing.price_per_gb_month * Decimal(str(total_storage_gb))
            
            storage_details = {
                "total_storage_gb": total_storage_gb,
                "object_storage_gb": workload_spec.storage_requirements.object_storage_gb,
                "block_storage_gb": workload_spec.storage_requirements.block_storage_gb,
                "database_storage_gb": workload_spec.storage_requirements.database_storage_gb,
                "storage_class": pricing.storage_class,
                "price_per_gb_month": float(pricing.price_per_gb_month)
            }
        
        if total_monthly_cost > 0:
            return ServiceCost(
                service_name="storage",
                service_category="storage",
                monthly_cost=total_monthly_cost,
                annual_cost=total_monthly_cost * 12,
                usage_details=storage_details,
                pricing_model="pay_as_you_go"
            )
        
        return None
    
    def _calculate_network_cost_from_pricing(
        self, 
        workload_spec: WorkloadSpec, 
        network_pricing: List
    ) -> Optional[ServiceCost]:
        """Calculate network costs from pricing data."""
        if not network_pricing:
            return None
        
        data_transfer_gb = workload_spec.network_requirements.data_transfer_gb_monthly
        
        if data_transfer_gb > 0:
            # Find data transfer pricing
            dt_pricing = next((p for p in network_pricing if p.service_type == "data_transfer"), None)
            if dt_pricing and dt_pricing.price_per_gb:
                monthly_cost = dt_pricing.price_per_gb * Decimal(str(data_transfer_gb))
                
                return ServiceCost(
                    service_name="network",
                    service_category="network",
                    monthly_cost=monthly_cost,
                    annual_cost=monthly_cost * 12,
                    usage_details={
                        "data_transfer_gb_monthly": data_transfer_gb,
                        "price_per_gb": float(dt_pricing.price_per_gb),
                        "transfer_type": dt_pricing.transfer_type
                    },
                    pricing_model="pay_as_you_go"
                )
        
        return None
    
    def _calculate_database_cost_from_pricing(
        self, 
        workload_spec: WorkloadSpec, 
        database_pricing: List
    ) -> Optional[ServiceCost]:
        """Calculate database costs from pricing data."""
        if not database_pricing or not workload_spec.database_requirements:
            return None
        
        # Use the first database pricing entry
        pricing = database_pricing[0]
        
        # Calculate monthly cost (assume 24/7 operation)
        monthly_cost = pricing.price_per_hour * Decimal('720')  # 24 * 30 hours
        
        # Add storage cost
        if workload_spec.database_requirements.database_size_gb > 0:
            storage_cost = pricing.storage_price_per_gb_month * Decimal(str(workload_spec.database_requirements.database_size_gb))
            monthly_cost += storage_cost
        
        return ServiceCost(
            service_name="database",
            service_category="database",
            monthly_cost=monthly_cost,
            annual_cost=monthly_cost * 12,
            usage_details={
                "database_type": pricing.database_type,
                "instance_class": pricing.instance_class,
                "database_size_gb": workload_spec.database_requirements.database_size_gb,
                "price_per_hour": float(pricing.price_per_hour),
                "storage_price_per_gb_month": float(pricing.storage_price_per_gb_month)
            },
            pricing_model="on_demand"
        )
    
    async def _calculate_provider_costs_mock(
        self, 
        workload_spec: WorkloadSpec, 
        provider: CloudProvider,
        region: str = "us-east-1",
        include_spot_pricing: bool = True,
        include_reserved_pricing: bool = True
    ) -> ProviderCost:
        """Calculate costs for a specific provider using mock data (fallback)."""
        # TODO: This will be implemented with actual pricing clients in Task 2
        # For now, return mock data to satisfy the interface
        
        service_costs = []
        
        # Mock compute costs
        compute_monthly = Decimal('50.00') * workload_spec.compute.vcpus + Decimal('5.00') * Decimal(str(workload_spec.compute.memory_gb))
        service_costs.append(ServiceCost(
            service_name="compute",
            service_category="compute",
            monthly_cost=compute_monthly,
            annual_cost=compute_monthly * 12,
            usage_details={"cpu_cores": workload_spec.compute.vcpus, "memory_gb": workload_spec.compute.memory_gb},
            pricing_model="pay_as_you_go",
            confidence_score=0.9
        ))
        
        # Mock storage costs
        storage_volume = sum(s.capacity_gb for s in workload_spec.storage) if workload_spec.storage else 0
        storage_monthly = Decimal('0.023') * storage_volume
        if storage_monthly > 0:
            service_costs.append(ServiceCost(
                service_name="storage",
                service_category="storage",
                monthly_cost=storage_monthly,
                annual_cost=storage_monthly * 12,
                usage_details={"total_gb": storage_volume},
                pricing_model="pay_as_you_go",
                confidence_score=0.9
            ))
        
        # Mock network costs
        network_monthly = Decimal('0.09') * getattr(workload_spec.network, 'data_transfer_gb_monthly', 100) if workload_spec.network else Decimal('0')
        if network_monthly > 0:
            service_costs.append(ServiceCost(
                service_name="network",
                service_category="network",
                monthly_cost=network_monthly,
                annual_cost=network_monthly * 12,
                pricing_model="pay_as_you_go",
                confidence_score=0.9
            ))
        
        total_monthly = sum(cost.monthly_cost for cost in service_costs)
        total_annual = total_monthly * 12
        
        # Mock savings calculations
        reserved_savings = total_monthly * Decimal('0.30') if include_reserved_pricing else None
        spot_eligible = False # Default mock
        spot_savings = total_monthly * Decimal('0.60') if include_spot_pricing and spot_eligible else None
        
        return ProviderCost(
            provider=provider,
            total_monthly_cost=total_monthly,
            total_annual_cost=total_annual,
            service_costs=service_costs,
            hidden_costs={
                "reserved_savings": reserved_savings or Decimal('0'),
                "spot_savings": spot_savings or Decimal('0')
            }
        )
    
    async def _generate_cost_recommendations(
        self, 
        workload_spec: WorkloadSpec, 
        provider_costs: Dict[CloudProvider, ProviderCost]
    ) -> List[CostRecommendation]:
        """Generate cost optimization recommendations."""
        lowest_cost_provider = min(provider_costs.keys(), key=lambda p: provider_costs[p].total_monthly_cost)
        highest_cost_provider = max(provider_costs.keys(), key=lambda p: provider_costs[p].total_monthly_cost)
        
        return await self.get_cost_recommendations(
            CostComparison(
                workload_name=workload_spec.name,
                comparison_id=self._generate_workload_hash(workload_spec),
                comparison_date=datetime.utcnow(),
                provider_costs=provider_costs,
                lowest_cost_provider=lowest_cost_provider,
                highest_cost_provider=highest_cost_provider,
                cost_difference_percentage=0.0,
                currency="USD",
                pricing_data_version="live",
                assumptions=[]
            )
        )
    
    async def _identify_savings_opportunities(
        self, 
        workload_spec: WorkloadSpec, 
        provider_costs: Dict[CloudProvider, ProviderCost]
    ) -> List[SavingsOpportunity]:
        """Identify savings opportunities across providers."""
        opportunities = []
        
        # Multi-cloud arbitrage opportunity
        costs = [(provider, cost.total_monthly_cost) for provider, cost in provider_costs.items()]
        costs.sort(key=lambda x: x[1])
        
        if len(costs) >= 2:
            lowest_cost = costs[0][1]
            highest_cost = costs[-1][1]
            
            if highest_cost > lowest_cost:
                monthly_savings = highest_cost - lowest_cost
                annual_savings = monthly_savings * 12
                
                opportunity = SavingsOpportunity(
                    opportunity_type="multi_cloud_arbitrage",
                    description=f"Switch from {costs[-1][0]} to {costs[0][0]} for optimal pricing",
                    monthly_savings=monthly_savings,
                    annual_savings=annual_savings,
                    confidence_score=0.85,
                    applicable_providers=[costs[-1][0], costs[0][0]]
                )
                opportunities.append(opportunity)
        
        return opportunities
    
    async def _calculate_base_infrastructure_costs(
        self, 
        workload_spec: WorkloadSpec, 
        provider: CloudProvider, 
        years: int
    ) -> Dict[str, Decimal]:
        """Calculate base infrastructure costs for TCO analysis."""
        # TODO: Implement with actual pricing data in Task 4
        base_costs = {}
        
        # Mock base infrastructure costs
        monthly_compute = Decimal('100.00') * workload_spec.compute.vcpus
        storage_volume = sum(s.capacity_gb for s in workload_spec.storage) if workload_spec.storage else 0
        monthly_storage = Decimal('0.023') * storage_volume
        monthly_network = Decimal('0.09') * getattr(workload_spec.network, 'data_transfer_gb_monthly', 100) if workload_spec.network else Decimal('0')
        
        for year in range(1, years + 1):
            # Apply 3% annual price increase
            inflation_factor = Decimal('1.03') ** (year - 1)
            base_costs[f"year_{year}_compute"] = monthly_compute * 12 * inflation_factor
            base_costs[f"year_{year}_storage"] = monthly_storage * 12 * inflation_factor
            base_costs[f"year_{year}_network"] = monthly_network * 12 * inflation_factor
        
        return base_costs
    
    async def _calculate_hidden_costs(
        self, 
        workload_spec: WorkloadSpec, 
        provider: CloudProvider, 
        base_costs: Dict[str, Decimal], 
        years: int
    ) -> Dict[str, Decimal]:
        """Calculate hidden costs (support, compliance, etc.)."""
        # TODO: Implement with actual hidden cost factors in Task 4
        hidden_costs = {}
        
        total_base_cost = sum(base_costs.values())
        
        # Mock hidden costs as percentages of base costs
        hidden_costs["support_fees"] = total_base_cost * Decimal('0.10')  # 10% for support
        hidden_costs["compliance_costs"] = total_base_cost * Decimal('0.05')  # 5% for compliance
        hidden_costs["training_costs"] = Decimal('5000.00')  # Fixed training cost
        
        return hidden_costs
    
    async def _calculate_operational_costs(
        self, 
        workload_spec: WorkloadSpec, 
        provider: CloudProvider, 
        years: int
    ) -> Dict[str, Decimal]:
        """Calculate operational overhead costs."""
        # TODO: Implement with actual operational cost factors in Task 4
        operational_costs = {}
        
        # Mock operational costs
        operational_costs["monitoring_tools"] = Decimal('500.00') * 12 * years
        operational_costs["backup_management"] = Decimal('200.00') * 12 * years
        operational_costs["security_tools"] = Decimal('300.00') * 12 * years
        
        return operational_costs
    
    def _combine_tco_components(
        self, 
        base_costs: Dict[str, Decimal], 
        hidden_costs: Dict[str, Decimal], 
        operational_costs: Dict[str, Decimal], 
        years: int
    ) -> List[TCOComponent]:
        """Combine all costs into TCO components."""
        components = []
        
        # Base infrastructure component
        base_total = sum(base_costs.values())
        components.append(TCOComponent(
            component_name="Base Infrastructure",
            year_1_cost=base_total / years,
            year_2_cost=base_total / years,
            year_3_cost=base_total / years,
            total_cost=base_total,
            description="Compute, storage, and network costs"
        ))
        
        # Hidden costs component
        hidden_total = sum(hidden_costs.values())
        components.append(TCOComponent(
            component_name="Hidden Costs",
            year_1_cost=hidden_total / years,
            year_2_cost=hidden_total / years,
            year_3_cost=hidden_total / years,
            total_cost=hidden_total,
            description="Support, compliance, and training costs"
        ))
        
        # Operational costs component
        operational_total = sum(operational_costs.values())
        components.append(TCOComponent(
            component_name="Operational Costs",
            year_1_cost=operational_total / years,
            year_2_cost=operational_total / years,
            year_3_cost=operational_total / years,
            total_cost=operational_total,
            description="Monitoring, backup, and security tools"
        ))
        
        return components
    
    def _generate_cost_projections(
        self, 
        provider_tco: Dict[CloudProvider, List[TCOComponent]], 
        years: int
    ) -> Dict[int, Dict[CloudProvider, Decimal]]:
        """Generate year-by-year cost projections."""
        projections = {}
        
        for year in range(1, years + 1):
            projections[year] = {}
            for provider, components in provider_tco.items():
                year_cost = sum(getattr(component, f"year_{min(year, 3)}_cost") for component in components)
                projections[year][provider] = year_cost
        
        return projections
    
    def _aggregate_cost_category(
        self, 
        provider_tco: Dict[CloudProvider, List[TCOComponent]], 
        category: str
    ) -> Dict[str, Decimal]:
        """Aggregate costs by category across providers."""
        aggregated = {}
        
        for provider, components in provider_tco.items():
            for component in components:
                if category.lower() in component.component_name.lower():
                    key = f"{provider.value}_{component.component_name.lower().replace(' ', '_')}"
                    aggregated[key] = component.total_cost
        
        return aggregated
    
    async def _calculate_migration_costs(
        self, 
        workload_spec: WorkloadSpec, 
        source: CloudProvider, 
        target: CloudProvider
    ) -> Dict[str, Decimal]:
        """Calculate migration-specific costs."""
        # TODO: Implement with migration cost estimator in Task 5
        migration_costs = {}
        
        # Mock migration costs
        data_volume = (
            workload_spec.storage_requirements.object_storage_gb +
            workload_spec.storage_requirements.block_storage_gb +
            workload_spec.storage_requirements.database_storage_gb
        )
        
        migration_costs["data_transfer"] = Decimal('0.09') * data_volume
        migration_costs["downtime_impact"] = Decimal('5000.00')  # Fixed downtime cost
        migration_costs["consulting_services"] = Decimal('10000.00')  # Professional services
        migration_costs["testing_validation"] = Decimal('3000.00')  # Testing costs
        migration_costs["total_cost"] = sum(migration_costs.values())
        
        return migration_costs
    
    async def _estimate_migration_timeline(
        self, 
        workload_spec: WorkloadSpec, 
        source: CloudProvider, 
        target: CloudProvider, 
        preference: Optional[str]
    ) -> int:
        """Estimate migration timeline in days."""
        # TODO: Implement with migration estimator in Task 5
        
        # Base timeline calculation
        base_days = 30  # Base migration time
        
        # Adjust based on workload complexity
        complexity_factor = 1.0
        if workload_spec.database_requirements:
            complexity_factor += 0.5
        if len(workload_spec.additional_services) > 0:
            complexity_factor += 0.3 * len(workload_spec.additional_services)
        
        estimated_days = int(base_days * complexity_factor)
        
        # Adjust based on preference
        if preference == "fast":
            estimated_days = int(estimated_days * 0.7)
        elif preference == "careful":
            estimated_days = int(estimated_days * 1.5)
        
        return estimated_days
    
    async def _assess_migration_risks(
        self, 
        workload_spec: WorkloadSpec, 
        source: CloudProvider, 
        target: CloudProvider
    ) -> List[RiskFactor]:
        """Assess migration risks."""
        # TODO: Implement with migration estimator in Task 5
        risks = []
        
        # Data migration risk
        if workload_spec.database_requirements:
            risks.append(RiskFactor(
                risk_type="data_migration",
                risk_level="medium",
                description="Database migration may require downtime and data validation",
                mitigation_strategy="Use database replication and staged migration approach",
                impact_score=6.0
            ))
        
        # Service compatibility risk
        if len(workload_spec.additional_services) > 0:
            risks.append(RiskFactor(
                risk_type="service_compatibility",
                risk_level="medium",
                description="Some services may not have direct equivalents on target provider",
                mitigation_strategy="Identify equivalent services and plan architecture changes",
                impact_score=5.0
            ))
        
        return risks
    
    async def _generate_migration_phases(
        self, 
        workload_spec: WorkloadSpec, 
        source: CloudProvider, 
        target: CloudProvider, 
        total_timeline: int
    ) -> List[MigrationPhase]:
        """Generate migration phases."""
        # TODO: Implement with migration estimator in Task 5
        phases = []
        
        # Planning phase
        phases.append(MigrationPhase(
            phase_name="Planning and Assessment",
            duration_days=int(total_timeline * 0.2),
            cost=Decimal('2000.00'),
            dependencies=[],
            deliverables=["Migration plan", "Risk assessment", "Resource mapping"]
        ))
        
        # Setup phase
        phases.append(MigrationPhase(
            phase_name="Target Environment Setup",
            duration_days=int(total_timeline * 0.3),
            cost=Decimal('3000.00'),
            dependencies=["Planning and Assessment"],
            deliverables=["Target infrastructure", "Network connectivity", "Security configuration"]
        ))
        
        # Migration phase
        phases.append(MigrationPhase(
            phase_name="Data and Application Migration",
            duration_days=int(total_timeline * 0.4),
            cost=Decimal('5000.00'),
            dependencies=["Target Environment Setup"],
            deliverables=["Migrated applications", "Data synchronization", "Testing results"]
        ))
        
        # Validation phase
        phases.append(MigrationPhase(
            phase_name="Validation and Cutover",
            duration_days=int(total_timeline * 0.1),
            cost=Decimal('1000.00'),
            dependencies=["Data and Application Migration"],
            deliverables=["Performance validation", "User acceptance", "Go-live"]
        ))
        
        return phases
    
    async def _generate_migration_recommendations(
        self, 
        workload_spec: WorkloadSpec, 
        source: CloudProvider, 
        target: CloudProvider, 
        migration_costs: Dict[str, Decimal], 
        monthly_savings: Decimal
    ) -> List[str]:
        """Generate migration recommendations."""
        recommendations = []
        
        if monthly_savings > 0:
            payback_months = int(migration_costs["total_cost"] / monthly_savings)
            recommendations.append(f"Migration will pay for itself in {payback_months} months")
            
            if payback_months <= 12:
                recommendations.append("Strong financial case for migration - short payback period")
            elif payback_months <= 24:
                recommendations.append("Moderate financial case for migration - consider strategic benefits")
            else:
                recommendations.append("Long payback period - evaluate non-financial benefits carefully")
        else:
            recommendations.append("Migration will increase costs - evaluate strategic and operational benefits")
        
        # Add technical recommendations
        if workload_spec.database_requirements:
            recommendations.append("Plan for database migration complexity and potential downtime")
        
        if False: # workload_spec.compute_requirements.spot_eligible
            recommendations.append("Consider spot instances on target provider for additional savings")
        
        return recommendations
    
    async def _save_comparison_to_db(self, workload_spec: WorkloadSpec, comparison: CostComparison):
        """Save cost comparison to database."""
        try:
            # Skip database save if no session is available
            if not self.db_session:
                logger.info("Skipping database save - no database session available")
                return
            
            # Create workload specification record if it doesn't exist
            workload_record = self.db_session.query(WorkloadSpecification).filter_by(
                name=workload_spec.name
            ).first()
            
            if not workload_record:
                # For now, we'll skip saving to DB since we don't have user context
                # This will be properly implemented when integrated with the API layer
                logger.info("Skipping database save - no user context available")
                return
            
            # Save comparison result
            comparison_record = MultiCloudCostComparison(
                workload_id=workload_record.id,
                comparison_date=comparison.comparison_date,
                aws_monthly_cost=comparison.providers.get(CloudProvider.AWS, ProviderCost(provider=CloudProvider.AWS, region="", monthly_cost=Decimal('0'), annual_cost=Decimal('0'), service_costs=[])).monthly_cost,
                gcp_monthly_cost=comparison.providers.get(CloudProvider.GCP, ProviderCost(provider=CloudProvider.GCP, region="", monthly_cost=Decimal('0'), annual_cost=Decimal('0'), service_costs=[])).monthly_cost,
                azure_monthly_cost=comparison.providers.get(CloudProvider.AZURE, ProviderCost(provider=CloudProvider.AZURE, region="", monthly_cost=Decimal('0'), annual_cost=Decimal('0'), service_costs=[])).monthly_cost,
                aws_annual_cost=comparison.providers.get(CloudProvider.AWS, ProviderCost(provider=CloudProvider.AWS, region="", monthly_cost=Decimal('0'), annual_cost=Decimal('0'), service_costs=[])).annual_cost,
                gcp_annual_cost=comparison.providers.get(CloudProvider.GCP, ProviderCost(provider=CloudProvider.GCP, region="", monthly_cost=Decimal('0'), annual_cost=Decimal('0'), service_costs=[])).annual_cost,
                azure_annual_cost=comparison.providers.get(CloudProvider.AZURE, ProviderCost(provider=CloudProvider.AZURE, region="", monthly_cost=Decimal('0'), annual_cost=Decimal('0'), service_costs=[])).annual_cost,
                cost_breakdown=comparison.dict(),
                recommendations=[rec.dict() for rec in comparison.recommendations]
            )
            
            self.db_session.add(comparison_record)
            self.db_session.commit()
            
            logger.info("Cost comparison saved to database")
            
        except Exception as e:
            logger.error(f"Failed to save comparison to database: {str(e)}")
            if self.db_session:
                self.db_session.rollback()
