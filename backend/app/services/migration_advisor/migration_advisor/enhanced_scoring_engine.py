"""
Enhanced Scoring Engine for Cloud Provider Recommendations

Implements weighted scoring algorithm with hard eliminators as specified in PRD Section 2.
"""

from typing import Dict, List, Tuple, Optional
from enum import Enum
from pydantic import BaseModel
import asyncio
import nest_asyncio
from app.ml.workload_intelligence_system import (
    WorkloadIntelligenceSystem, 
    WorkloadSpec, 
    ResourceRequirements, 
    PerformanceProfile, 
    CostSensitivity,
    WorkloadType
)


class Provider(str, Enum):
    """Supported cloud providers"""
    AWS = "AWS"
    AZURE = "Azure"
    GCP = "GCP"
    IBM = "IBM"
    ORACLE = "Oracle"


class CategoryWeight(BaseModel):
    """Category multipliers for weighted scoring (PRD Section 2.1)"""
    compliance_regulatory: float = 3.0
    workload_type: float = 2.5
    hybrid_integration: float = 2.5
    data_volume_storage: float = 2.0
    budget_cost_model: float = 2.0
    security_encryption: float = 2.0
    ai_ml_requirements: float = 1.5
    support_level: float = 1.5
    vendor_ecosystem: float = 1.5
    scalability: float = 1.5
    open_source_preference: float = 1.0
    existing_vendor_relationship: float = 0.5


class HardEliminator:
    """Pre-scoring filters that eliminate incompatible providers (PRD Section 2.2)"""
    
    @staticmethod
    def check_fedramp(answers: Dict, providers: List[Provider]) -> List[Provider]:
        """Eliminate providers without FedRAMP certification"""
        compliance = answers.get('compliance', {})
        frameworks = compliance.get('regulatory_frameworks', [])
        
        if 'FedRAMP' in frameworks or 'fedramp' in [f.lower() for f in frameworks]:
            # Only AWS and Azure have FedRAMP
            return [p for p in providers if p in [Provider.AWS, Provider.AZURE]]
        return providers
    
    @staticmethod
    def check_data_residency(answers: Dict, providers: List[Provider]) -> List[Provider]:
        """Eliminate providers without required data center"""
        # For now, all major providers have global coverage
        return providers
    
    @staticmethod
    def check_hipaa(answers: Dict, providers: List[Provider]) -> List[Provider]:
        """Eliminate providers without HIPAA BAA"""
        compliance = answers.get('compliance', {})
        frameworks = compliance.get('regulatory_frameworks', [])
        
        if 'HIPAA' in frameworks or 'hipaa' in [f.lower() for f in frameworks]:
            # All major providers support HIPAA with BAA
            return providers
        return providers
    
    @staticmethod
    def check_budget(answers: Dict, providers: List[Provider]) -> List[Provider]:
        """Eliminate providers based on budget constraints"""
        budget = answers.get('budget', {})
        monthly_budget = budget.get('target_monthly_cost', 0)
        
        if monthly_budget > 0 and monthly_budget < 500:
            return [p for p in providers if p != Provider.IBM]
        return providers
    
    @staticmethod
    def apply_all(answers: Dict) -> List[Provider]:
        """Apply all hard eliminators"""
        providers = list(Provider)
        providers = HardEliminator.check_fedramp(answers, providers)
        providers = HardEliminator.check_data_residency(answers, providers)
        providers = HardEliminator.check_hipaa(answers, providers)
        providers = HardEliminator.check_budget(answers, providers)
        return providers


class EnhancedScoringEngine:
    """Weighted scoring algorithm with category multipliers and ML integration"""
    
    def __init__(self):
        self.weights = CategoryWeight()
        self.max_possible_score = 100.0
        self.ml_system = WorkloadIntelligenceSystem()
        self.last_ml_recommendation = None
    
    def calculate_scores(self, answers: Dict) -> Dict[Provider, float]:
        """Calculate weighted scores for all providers including ML insights"""
        scores = {provider: 0.0 for provider in Provider}
        eligible_providers = HardEliminator.apply_all(answers)
        
        for provider in Provider:
            if provider not in eligible_providers:
                scores[provider] = -1
        
        # Calculate ML-based scores
        ml_scores = self._calculate_ml_scores(answers)
        
        for provider in eligible_providers:
            # 1. Heuristic Scores (40% weight)
            h_score = 0.0
            h_score += self._score_workload(answers, provider) * self.weights.workload_type
            h_score += self._score_tech_stack(answers, provider) * self.weights.vendor_ecosystem
            h_score += self._score_compliance(answers, provider) * self.weights.compliance_regulatory
            h_score += self._score_budget(answers, provider) * self.weights.budget_cost_model
            h_score += self._score_ai_ml(answers, provider) * self.weights.ai_ml_requirements
            h_score += self._score_scalability(answers, provider) * self.weights.scalability
            h_score += self._score_hybrid(answers, provider) * self.weights.hybrid_integration
            h_score += self._score_data_volume(answers, provider) * self.weights.data_volume_storage
            h_score += self._score_support(answers, provider) * self.weights.support_level
            h_score += self._score_open_source(answers, provider) * self.weights.open_source_preference
            
            # Normalize heuristic to 0-100 (Max raw is ~32.5)
            h_normalized = min(100.0, (h_score / 32.5) * 100)
            
            # 2. ML Score (60% weight)
            # Map Provder enum to upper string for ML score keys
            ml_normalized = ml_scores.get(provider.value.upper(), 50.0)
            
            # Weighted Blend
            scores[provider] = (ml_normalized * 0.6) + (h_normalized * 0.4)
            
        return scores

    def _calculate_ml_scores(self, answers: Dict) -> Dict[str, float]:
        """Generate ML-based scores using WorkloadIntelligenceSystem"""
        workload_data = answers.get('workload', {})
        perf_data = answers.get('performance', {})
        budget_data = answers.get('budget', {})
        
        resources = ResourceRequirements(
            cpu_cores=workload_data.get('total_compute_cores', 4),
            memory_gb=workload_data.get('total_memory_gb', 16),
            storage_gb=int(workload_data.get('total_storage_tb', 1) * 1024),
            network_bandwidth_mbps=1000,
            gpu_count=1 if answers.get('technical', {}).get('ml_ai_required') else 0
        )
        
        perf_profile = PerformanceProfile(
            cpu_utilization_avg=70.0,
            memory_utilization_avg=60.0,
            network_io_pattern="steady",
            storage_io_pattern="balanced",
            latency_sensitivity="medium",
            throughput_requirements=1000,
            availability_requirement=float(perf_data.get('availability_target', 99.9)),
            scaling_pattern="predictable"
        )
        
        priority_map = {'HIGH': 0.9, 'MEDIUM': 0.5, 'LOW': 0.2}
        cost_prio = priority_map.get(budget_data.get('cost_optimization_priority', 'MEDIUM'), 0.5)
        
        cost_sensitivity = CostSensitivity(
            cost_priority=cost_prio,
            reserved_instance_preference=True
        )
        
        workload_type = WorkloadType.WEB_APPLICATION
        tech_reqs = answers.get('technical', {})
        if tech_reqs.get('ml_ai_required'):
            workload_type = WorkloadType.MACHINE_LEARNING
        elif 'Database' in tech_reqs.get('required_services', []):
            workload_type = WorkloadType.DATABASE
            
        spec = WorkloadSpec(
            workload_id="migration-assessment",
            name="Assessment Workload",
            workload_type=workload_type,
            resource_requirements=resources,
            performance_profile=perf_profile,
            compliance_requirements=[],
            cost_sensitivity=cost_sensitivity
        )
        
        try:
            try:
                loop = asyncio.get_event_loop()
                nest_asyncio.apply()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            recommendation = loop.run_until_complete(
                self.ml_system.analyze_and_recommend_placement(spec)
            )
            
            self.last_ml_recommendation = recommendation
            
            results = {recommendation.recommended_option.provider.upper(): recommendation.recommended_option.overall_score * 100}
            for alt in recommendation.alternative_options:
                results[alt.provider.upper()] = alt.overall_score * 100
                
            return results
        except Exception:
            self.last_ml_recommendation = None
            return {}

    def _score_workload(self, answers: Dict, provider: Provider) -> float:
        tech_data = answers.get('technical', {})
        services = tech_data.get('required_services', [])
        score = 0.0
        
        if 'Compute' in services:
            m = {Provider.AWS: 3, Provider.GCP: 2, Provider.AZURE: 1}
            score += m.get(provider, 0)
        
        if tech_data.get('analytics_required') or 'Analytics' in services:
            m = {Provider.AWS: 2, Provider.GCP: 3, Provider.AZURE: 1}
            score += m.get(provider, 0)
            
        if tech_data.get('ml_ai_required'):
            m = {Provider.AWS: 2, Provider.GCP: 3, Provider.AZURE: 2, Provider.IBM: 1}
            score += m.get(provider, 0)
            
        if tech_data.get('container_orchestration'):
            m = {Provider.AWS: 2, Provider.GCP: 3, Provider.AZURE: 2}
            score += m.get(provider, 0)
            
        if 'Database' in services:
            m = {Provider.AWS: 2, Provider.AZURE: 2, Provider.GCP: 1, Provider.IBM: 1, Provider.ORACLE: 4}
            score += m.get(provider, 0)
            
        return min(score, 4.0)

    def _score_tech_stack(self, answers: Dict, provider: Provider) -> float:
        org_data = answers.get('organization', {})
        tech_data = answers.get('technical', {})
        score = 0.0
        
        if org_data.get('industry') in ['Finance', 'Healthcare', 'Government'] and provider == Provider.AZURE:
            score += 2
            
        if 'Compute' in tech_data.get('required_services', []) and 'Database' in tech_data.get('required_services', []):
            m = {Provider.AWS: 3, Provider.GCP: 3, Provider.AZURE: 1}
            score += m.get(provider, 0)
            
        return min(score, 4.0)

    def _score_compliance(self, answers: Dict, provider: Provider) -> float:
        frameworks = answers.get('compliance', {}).get('regulatory_frameworks', [])
        if not frameworks: return 0.0
        
        count = len(frameworks)
        if count >= 3:
            m = {Provider.AZURE: 3, Provider.AWS: 3, Provider.GCP: 1, Provider.IBM: 2, Provider.ORACLE: 1}
        else:
            m = {Provider.AZURE: 2, Provider.AWS: 2, Provider.GCP: 1, Provider.IBM: 1, Provider.ORACLE: 1}
        return m.get(provider, 0)

    def _score_budget(self, answers: Dict, provider: Provider) -> float:
        priority = answers.get('budget', {}).get('cost_optimization_priority', 'MEDIUM')
        if priority == 'HIGH':
            m = {Provider.GCP: 3, Provider.AWS: 1, Provider.AZURE: 1, Provider.ORACLE: 2}
        elif priority == 'LOW':
            m = {Provider.AWS: 2, Provider.AZURE: 2, Provider.GCP: 1, Provider.IBM: 1, Provider.ORACLE: 1}
        else:
            m = {Provider.AWS: 2, Provider.GCP: 2, Provider.AZURE: 2, Provider.IBM: 1, Provider.ORACLE: 1}
        return m.get(provider, 0)

    def _score_ai_ml(self, answers: Dict, provider: Provider) -> float:
        if answers.get('technical', {}).get('ml_ai_required'):
            m = {Provider.GCP: 3, Provider.AWS: 2, Provider.AZURE: 2, Provider.IBM: 1}
            return m.get(provider, 0)
        return 0.0

    def _score_scalability(self, answers: Dict, provider: Provider) -> float:
        availability = answers.get('performance', {}).get('availability_target', 99.0)
        if availability >= 99.9:
            m = {Provider.AWS: 3, Provider.GCP: 2, Provider.AZURE: 2, Provider.IBM: 1, Provider.ORACLE: 1}
        elif availability >= 99.5:
            m = {Provider.AWS: 2, Provider.GCP: 2, Provider.AZURE: 2, Provider.IBM: 1, Provider.ORACLE: 1}
        else:
            return 0.0
        return m.get(provider, 0)

    def _score_hybrid(self, answers: Dict, provider: Provider) -> float:
        if answers.get('organization', {}).get('current_infrastructure') in ['ON_PREMISES', 'HYBRID']:
            m = {Provider.AZURE: 3, Provider.AWS: 2, Provider.GCP: 1, Provider.IBM: 3, Provider.ORACLE: 1}
            return m.get(provider, 0)
        return 0.0

    def _score_data_volume(self, answers: Dict, provider: Provider) -> float:
        storage = answers.get('workload', {}).get('total_storage_tb', 0)
        if storage > 100:
            m = {Provider.AWS: 2, Provider.GCP: 3, Provider.AZURE: 2, Provider.IBM: 1, Provider.ORACLE: 1}
        elif storage > 10:
            m = {Provider.AWS: 2, Provider.GCP: 2, Provider.AZURE: 2, Provider.IBM: 1, Provider.ORACLE: 1}
        else:
            return 0.0
        return m.get(provider, 0)

    def _score_support(self, answers: Dict, provider: Provider) -> float:
        if answers.get('organization', {}).get('company_size') in ['ENTERPRISE', 'LARGE']:
            m = {Provider.AWS: 3, Provider.AZURE: 3, Provider.GCP: 2, Provider.IBM: 2, Provider.ORACLE: 2}
            return m.get(provider, 0)
        return 0.0

    def _score_open_source(self, answers: Dict, provider: Provider) -> float:
        if answers.get('technical', {}).get('container_orchestration'):
            m = {Provider.GCP: 2, Provider.AWS: 2, Provider.AZURE: 1, Provider.IBM: 1}
            return m.get(provider, 0)
        return 0.0

    def get_recommendation(self, answers: Dict) -> Tuple[Provider, float, Dict]:
        scores = self.calculate_scores(answers)
        eligible = {p: s for p, s in scores.items() if s >= 0}
        if not eligible: raise ValueError("No eligible providers found")
        
        top_provider = max(eligible, key=eligible.get)
        top_score = eligible[top_provider]
        evidence = self._generate_evidence(answers, top_provider, top_score)
        return top_provider, top_score, evidence

    def _generate_evidence(self, answers: Dict, provider: Provider, score: float) -> Dict:
        evidence_points = []
        tech_data = answers.get('technical', {})
        
        required_services = tech_data.get('required_services', [])
        if required_services:
            evidence_points.append(f"Workload matches {provider.value}'s excellence in {', '.join(required_services[:2])}")
            
        if tech_data.get('ml_ai_required'):
            evidence_points.append(f"AI/ML requirements align with {provider.value}'s specialized services")
            
        ml_rec = self.last_ml_recommendation
        if ml_rec:
            opt = ml_rec.recommended_option
            if opt.provider.upper() == provider.value.upper():
                evidence_points.append(f"ML Analysis: {opt.reasoning}")
                if opt.limitations:
                    evidence_points.append(f"Optimization potential: {opt.limitations[0]}")
                    
        return {
            'evidence_points': evidence_points[:5],
            'provider': provider.value,
            'score': round(score, 1),
            'ml_insights': {
                'confidence': round(ml_rec.confidence_score * 100, 1) if ml_rec else 0,
                'complexity': ml_rec.migration_complexity if ml_rec else 'Unknown',
                'timeline': ml_rec.implementation_timeline if ml_rec else 'Unknown'
            } if ml_rec else None
        }

    def get_all_scores_sorted(self, answers: Dict) -> List[Tuple[Provider, float]]:
        scores = self.calculate_scores(answers)
        eligible = [(p, s) for p, s in scores.items() if s >= 0]
        return sorted(eligible, key=lambda x: x[1], reverse=True)
