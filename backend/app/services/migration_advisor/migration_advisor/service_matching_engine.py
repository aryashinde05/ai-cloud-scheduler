"""
Service Matching Engine for Cloud Migration Advisor

This module implements the ServiceMatchingModel that evaluates how well cloud providers
match the required services for a migration project. It includes service compatibility
scoring logic and service gap identification.

Requirements: 3.1, 3.4
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum

from app.services.migration_advisor.migration_advisor.provider_catalog import (
    CloudProvider, CloudProviderName, ServiceCategory, 
    ServiceSpecification, ProviderCatalog
)
from app.services.migration_advisor.migration_advisor.service_catalog_data import get_provider_catalog


class MatchQuality(Enum):
    """Quality of service match"""
    EXACT = "exact"  # Perfect match
    EQUIVALENT = "equivalent"  # Functionally equivalent
    PARTIAL = "partial"  # Partially meets requirements
    MISSING = "missing"  # No match available


@dataclass
class ServiceMatch:
    """Represents a match between required and available service"""
    required_service: str
    required_category: ServiceCategory
    provider_service: Optional[ServiceSpecification]
    match_quality: MatchQuality
    compatibility_score: float  # 0.0 to 1.0
    match_reason: str
    alternative_services: List[ServiceSpecification] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    
    def __repr__(self):
        return f"<ServiceMatch(required='{self.required_service}', quality='{self.match_quality.value}', score={self.compatibility_score})>"


@dataclass
class ServiceGap:
    """Represents a gap where required service is not available"""
    required_service: str
    required_category: ServiceCategory
    gap_severity: str  # critical, high, medium, low
    impact_description: str
    workaround_options: List[str] = field(default_factory=list)
    alternative_approaches: List[str] = field(default_factory=list)
    
    def __repr__(self):
        return f"<ServiceGap(service='{self.required_service}', severity='{self.gap_severity}')>"


@dataclass
class ProviderServiceEvaluation:
    """Complete service matching evaluation for a provider"""
    provider: CloudProvider
    total_required_services: int
    matched_services: List[ServiceMatch]
    service_gaps: List[ServiceGap]
    overall_match_score: float  # 0.0 to 1.0
    category_scores: Dict[ServiceCategory, float] = field(default_factory=dict)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    
    def __repr__(self):
        return f"<ProviderServiceEvaluation(provider='{self.provider.provider_name.value}', score={self.overall_match_score})>"


class ServiceMatchingModel:
    """
    ML-based service matching model that evaluates cloud providers against
    required services and identifies service gaps.
    """
    
    def __init__(self, provider_catalog: Optional[ProviderCatalog] = None):
        """
        Initialize the service matching model
        
        Args:
            provider_catalog: Optional provider catalog, uses global instance if not provided
        """
        self.catalog = provider_catalog or get_provider_catalog()
        
        # Service mapping rules for common service names to provider services
        self.service_mappings = self._initialize_service_mappings()
        
        # Category importance weights (can be customized)
        self.category_weights = {
            ServiceCategory.COMPUTE: 1.0,
            ServiceCategory.STORAGE: 1.0,
            ServiceCategory.DATABASE: 1.0,
            ServiceCategory.NETWORKING: 0.8,
            ServiceCategory.MACHINE_LEARNING: 0.9,
            ServiceCategory.ANALYTICS: 0.9,
            ServiceCategory.CONTAINERS: 0.9,
            ServiceCategory.SERVERLESS: 0.8,
            ServiceCategory.SECURITY: 0.7,
            ServiceCategory.MANAGEMENT: 0.6,
        }
    
    def _initialize_service_mappings(self) -> Dict[str, Dict[CloudProviderName, str]]:
        """
        Initialize mappings from generic service names to provider-specific service IDs
        
        Returns:
            Dictionary mapping generic service names to provider service IDs
        """
        return {
            "compute": {
                CloudProviderName.AWS: "ec2",
                CloudProviderName.GCP: "compute_engine",
                CloudProviderName.AZURE: "virtual_machines"
            },
            "storage": {
                CloudProviderName.AWS: "s3",
                CloudProviderName.GCP: "cloud_storage",
                CloudProviderName.AZURE: "blob_storage"
            },
            "database": {
                CloudProviderName.AWS: "rds",
                CloudProviderName.GCP: "cloud_sql",
                CloudProviderName.AZURE: "sql_database"
            },
            # Compute services
            "virtual_machines": {
                CloudProviderName.AWS: "ec2",
                CloudProviderName.GCP: "compute_engine",
                CloudProviderName.AZURE: "virtual_machines"
            },
            "serverless_functions": {
                CloudProviderName.AWS: "lambda",
                CloudProviderName.GCP: "cloud_functions",
                CloudProviderName.AZURE: "azure_functions"
            },
            "kubernetes": {
                CloudProviderName.AWS: "eks",
                CloudProviderName.GCP: "gke",
                CloudProviderName.AZURE: "aks"
            },
            "container_service": {
                CloudProviderName.AWS: "ecs",
                CloudProviderName.GCP: "cloud_run",
                CloudProviderName.AZURE: "container_instances"
            },
            # Storage services
            "object_storage": {
                CloudProviderName.AWS: "s3",
                CloudProviderName.GCP: "cloud_storage",
                CloudProviderName.AZURE: "blob_storage"
            },
            "block_storage": {
                CloudProviderName.AWS: "ebs",
                CloudProviderName.GCP: "persistent_disk",
                CloudProviderName.AZURE: "managed_disks"
            },
            "file_storage": {
                CloudProviderName.AWS: "efs",
                CloudProviderName.GCP: "filestore",
                CloudProviderName.AZURE: "azure_files"
            },
            # Database services
            "relational_database": {
                CloudProviderName.AWS: "rds",
                CloudProviderName.GCP: "cloud_sql",
                CloudProviderName.AZURE: "sql_database"
            },
            "nosql_database": {
                CloudProviderName.AWS: "dynamodb",
                CloudProviderName.GCP: "firestore",
                CloudProviderName.AZURE: "cosmos_db"
            },
            "managed_postgresql": {
                CloudProviderName.AWS: "rds",
                CloudProviderName.GCP: "cloud_sql",
                CloudProviderName.AZURE: "postgresql"
            },
            # ML services
            "ml_platform": {
                CloudProviderName.AWS: "sagemaker",
                CloudProviderName.GCP: "vertex_ai",
                CloudProviderName.AZURE: "machine_learning"
            },
            "computer_vision": {
                CloudProviderName.AWS: "rekognition",
                CloudProviderName.GCP: "vision_ai",
                CloudProviderName.AZURE: "cognitive_services"
            },
            # Analytics services
            "data_warehouse": {
                CloudProviderName.AWS: "redshift",
                CloudProviderName.GCP: "bigquery",
                CloudProviderName.AZURE: "synapse_analytics"
            },
            "big_data_processing": {
                CloudProviderName.AWS: "emr",
                CloudProviderName.GCP: "dataproc",
                CloudProviderName.AZURE: "databricks"
            }
        }
    
    def evaluate_provider(
        self,
        provider_name: CloudProviderName,
        required_services: List[str],
        required_categories: Optional[Dict[ServiceCategory, List[str]]] = None
    ) -> ProviderServiceEvaluation:
        """
        Evaluate how well a provider matches required services
        
        Args:
            provider_name: Name of the cloud provider to evaluate
            required_services: List of required service names (generic or provider-specific)
            required_categories: Optional dict of required services organized by category
            
        Returns:
            ProviderServiceEvaluation with detailed matching results
        """
        provider = self.catalog.get_provider(provider_name)
        if not provider:
            raise ValueError(f"Provider {provider_name.value} not found in catalog")
        
        # Match each required service
        matched_services = []
        service_gaps = []
        
        for required_service in required_services:
            match = self._match_service(provider, required_service)
            
            if match.match_quality == MatchQuality.MISSING:
                gap = self._create_service_gap(required_service, match)
                service_gaps.append(gap)
            
            matched_services.append(match)
        
        # Calculate scores
        overall_score = self._calculate_overall_score(matched_services)
        category_scores = self._calculate_category_scores(matched_services)
        
        # Identify strengths and weaknesses
        strengths, weaknesses = self._analyze_strengths_weaknesses(
            provider, matched_services, service_gaps
        )
        
        return ProviderServiceEvaluation(
            provider=provider,
            total_required_services=len(required_services),
            matched_services=matched_services,
            service_gaps=service_gaps,
            overall_match_score=overall_score,
            category_scores=category_scores,
            strengths=strengths,
            weaknesses=weaknesses
        )
    
    def _match_service(
        self,
        provider: CloudProvider,
        required_service: str
    ) -> ServiceMatch:
        """
        Match a required service to provider's available services
        
        Args:
            provider: Cloud provider to match against
            required_service: Required service name
            
        Returns:
            ServiceMatch object with matching details
        """
        # Try direct service ID match first
        provider_service = provider.get_service(required_service)
        if provider_service:
            return ServiceMatch(
                required_service=required_service,
                required_category=provider_service.category,
                provider_service=provider_service,
                match_quality=MatchQuality.EXACT,
                compatibility_score=1.0,
                match_reason=f"Direct match: {provider_service.service_name}"
            )
        
        # Try generic service mapping
        if required_service in self.service_mappings:
            mapping = self.service_mappings[required_service]
            if provider.provider_name in mapping:
                service_id = mapping[provider.provider_name]
                provider_service = provider.get_service(service_id)
                if provider_service:
                    return ServiceMatch(
                        required_service=required_service,
                        required_category=provider_service.category,
                        provider_service=provider_service,
                        match_quality=MatchQuality.EQUIVALENT,
                        compatibility_score=0.95,
                        match_reason=f"Equivalent service: {provider_service.service_name}"
                    )
        
        # Try fuzzy matching by service name
        fuzzy_match = self._fuzzy_match_service(provider, required_service)
        if fuzzy_match:
            return fuzzy_match
        
        # No match found
        return ServiceMatch(
            required_service=required_service,
            required_category=ServiceCategory.COMPUTE,  # Default category
            provider_service=None,
            match_quality=MatchQuality.MISSING,
            compatibility_score=0.0,
            match_reason=f"No matching service found for '{required_service}'"
        )
    
    def _fuzzy_match_service(
        self,
        provider: CloudProvider,
        required_service: str
    ) -> Optional[ServiceMatch]:
        """
        Attempt fuzzy matching of service by name similarity
        
        Args:
            provider: Cloud provider
            required_service: Required service name
            
        Returns:
            ServiceMatch if fuzzy match found, None otherwise
        """
        required_lower = required_service.lower().replace("_", " ").replace("-", " ")
        best_match = None
        best_score = 0.0
        
        for service_id, service in provider.services.items():
            service_name_lower = service.service_name.lower()
            service_id_lower = service_id.lower().replace("_", " ").replace("-", " ")
            
            # Check if required service name is contained in provider service name
            if required_lower in service_name_lower or required_lower in service_id_lower:
                score = 0.7  # Partial match score
                if score > best_score:
                    best_score = score
                    best_match = service
            
            # Check reverse - if provider service name is in required
            elif service_id_lower in required_lower:
                score = 0.6
                if score > best_score:
                    best_score = score
                    best_match = service
        
        if best_match and best_score >= 0.6:
            return ServiceMatch(
                required_service=required_service,
                required_category=best_match.category,
                provider_service=best_match,
                match_quality=MatchQuality.PARTIAL,
                compatibility_score=best_score,
                match_reason=f"Partial match: {best_match.service_name}",
                limitations=["May require additional configuration or adaptation"]
            )
        
        return None
    
    def _calculate_overall_score(self, matched_services: List[ServiceMatch]) -> float:
        """
        Calculate overall service matching score
        
        Args:
            matched_services: List of service matches
            
        Returns:
            Overall score from 0.0 to 1.0
        """
        if not matched_services:
            return 0.0
        
        total_score = sum(match.compatibility_score for match in matched_services)
        return total_score / len(matched_services)
    
    def _calculate_category_scores(
        self,
        matched_services: List[ServiceMatch]
    ) -> Dict[ServiceCategory, float]:
        """
        Calculate matching scores by service category
        
        Args:
            matched_services: List of service matches
            
        Returns:
            Dictionary of category scores
        """
        category_scores = {}
        category_counts = {}
        
        for match in matched_services:
            category = match.required_category
            if category not in category_scores:
                category_scores[category] = 0.0
                category_counts[category] = 0
            
            category_scores[category] += match.compatibility_score
            category_counts[category] += 1
        
        # Calculate averages
        for category in category_scores:
            if category_counts[category] > 0:
                category_scores[category] /= category_counts[category]
        
        return category_scores
    
    def _create_service_gap(
        self,
        required_service: str,
        match: ServiceMatch
    ) -> ServiceGap:
        """
        Create a service gap for a missing service
        
        Args:
            required_service: Name of required service
            match: ServiceMatch indicating the gap
            
        Returns:
            ServiceGap object
        """
        # Determine severity based on service category
        severity = "medium"
        if match.required_category in [ServiceCategory.COMPUTE, ServiceCategory.DATABASE]:
            severity = "high"
        elif match.required_category in [ServiceCategory.STORAGE, ServiceCategory.NETWORKING]:
            severity = "high"
        elif match.required_category == ServiceCategory.MACHINE_LEARNING:
            severity = "medium"
        
        return ServiceGap(
            required_service=required_service,
            required_category=match.required_category,
            gap_severity=severity,
            impact_description=f"Required service '{required_service}' is not available",
            workaround_options=[
                "Use alternative service from same category",
                "Implement custom solution using available services",
                "Consider third-party integration"
            ],
            alternative_approaches=[
                "Evaluate if requirement can be met with different architecture",
                "Consider multi-cloud approach for this specific service"
            ]
        )
    
    def _analyze_strengths_weaknesses(
        self,
        provider: CloudProvider,
        matched_services: List[ServiceMatch],
        service_gaps: List[ServiceGap]
    ) -> Tuple[List[str], List[str]]:
        """
        Analyze provider strengths and weaknesses based on service matching
        
        Args:
            provider: Cloud provider
            matched_services: List of matched services
            service_gaps: List of service gaps
            
        Returns:
            Tuple of (strengths, weaknesses) lists
        """
        strengths = []
        weaknesses = []
        
        # Analyze by category
        category_scores = self._calculate_category_scores(matched_services)
        
        for category, score in category_scores.items():
            if score >= 0.9:
                strengths.append(f"Excellent {category.value} service coverage")
            elif score >= 0.7:
                strengths.append(f"Good {category.value} service availability")
            elif score < 0.5:
                weaknesses.append(f"Limited {category.value} service options")
        
        # Analyze service gaps
        if not service_gaps:
            strengths.append("All required services available")
        else:
            critical_gaps = [g for g in service_gaps if g.gap_severity in ["critical", "high"]]
            if critical_gaps:
                weaknesses.append(f"{len(critical_gaps)} critical service gaps identified")
            else:
                weaknesses.append(f"{len(service_gaps)} minor service gaps")
        
        # Analyze exact matches
        exact_matches = [m for m in matched_services if m.match_quality == MatchQuality.EXACT]
        if len(exact_matches) >= len(matched_services) * 0.8:
            strengths.append("High number of exact service matches")
        
        return strengths, weaknesses
    
    def compare_providers(
        self,
        required_services: List[str],
        providers: Optional[List[CloudProviderName]] = None
    ) -> Dict[CloudProviderName, ProviderServiceEvaluation]:
        """
        Compare multiple providers for service matching
        
        Args:
            required_services: List of required services
            providers: Optional list of providers to compare (defaults to all)
            
        Returns:
            Dictionary mapping provider names to their evaluations
        """
        if providers is None:
            providers = [CloudProviderName.AWS, CloudProviderName.GCP, CloudProviderName.AZURE]
        
        evaluations = {}
        for provider_name in providers:
            evaluation = self.evaluate_provider(provider_name, required_services)
            evaluations[provider_name] = evaluation
        
        return evaluations
    
    def identify_service_gaps(
        self,
        provider_name: CloudProviderName,
        required_services: List[str]
    ) -> List[ServiceGap]:
        """
        Identify service gaps for a specific provider
        
        Args:
            provider_name: Cloud provider to evaluate
            required_services: List of required services
            
        Returns:
            List of ServiceGap objects
        """
        evaluation = self.evaluate_provider(provider_name, required_services)
        return evaluation.service_gaps
    
    def get_service_alternatives(
        self,
        required_service: str,
        provider_name: CloudProviderName
    ) -> List[ServiceSpecification]:
        """
        Get alternative services that might meet the requirement
        
        Args:
            required_service: Required service name
            provider_name: Cloud provider
            
        Returns:
            List of alternative service specifications
        """
        provider = self.catalog.get_provider(provider_name)
        if not provider:
            return []
        
        # Try to determine the category of the required service
        match = self._match_service(provider, required_service)
        
        if match.provider_service:
            # Return services in the same category
            return provider.get_services_by_category(match.required_category)
        
        return []
