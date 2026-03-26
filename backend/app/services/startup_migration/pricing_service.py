from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.services.startup_migration.models import (
    StartupMigrationProject,
    StartupDatabaseAssessment,
    StartupCloudRecommendation,
    CloudProvider
)

from app.services.multi_cloud_cost_engine import MultiCloudCostEngine
from app.models.multi_cloud_models import WorkloadSpec, ProviderCostSummary

class MultiCloudPricingService:
    """
    Service to compare cloud database pricing based on assessment.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_cloud_costs(self, project_id: UUID) -> List[StartupCloudRecommendation]:
        """
        Mock implementation to generate cloud recommendations.
        Ideally this would query real pricing APIs.
        """
        
        # 1. Fetch assessment
        result = await self.db.execute(select(StartupDatabaseAssessment).where(StartupDatabaseAssessment.project_id == project_id))
        assessment = result.scalars().first()
        
        if not assessment:
            return []

        # 2. Get real pricing from MultiCloudCostEngine
        engine = MultiCloudCostEngine(self.db)
        
        # Create a workload spec based on the assessment
        workload_spec = WorkloadSpec(
            name=f"Migration-{project_id}",
            description=f"Automated assessment for {assessment.database_engine}",
            vcpus=int(assessment.cpu_cores),
            memory_gb=float(assessment.memory_gb),
            storage_gb=float(assessment.database_size_gb),
            os="linux",
            region="us-east-1"
        )
        
        comparison = await engine.compare_workload_costs(workload_spec)
        
        recommendations = []
        for provider_type, summary in comparison.provider_costs.items():
             # Map engine summary back to StartupCloudRecommendation
             rec = StartupCloudRecommendation(
                project_id=project_id,
                provider=CloudProvider(provider_type.value.lower()),
                service_name=summary.compute_cost.service_name if hasattr(summary.compute_cost, 'service_name') else "Managed Service",
                instance_type=summary.compute_cost.instance_type if hasattr(summary.compute_cost, 'instance_type') else "Standard",
                region=summary.region,
                instance_cost=float(summary.compute_cost.monthly_cost),
                storage_cost=float(summary.storage_cost.monthly_cost),
                backup_cost=float(summary.storage_cost.monthly_cost) * 0.2, # Still a factor but based on real storage cost
                data_transfer_cost=float(summary.network_cost.monthly_cost),
                total_monthly_cost=float(summary.total_monthly_cost),
                cost_score=85.00, # Simplified scoring for now
                performance_score=90.00,
                feature_score=88.00,
                compliance_score=95.00,
                migration_complexity_score=80.00,
                overall_score=87.60,
                is_recommended=(provider_type.value.lower() == "aws")
             )
             self.db.add(rec)
             recommendations.append(rec)
             
        await self.db.commit()
        return recommendations

    async def get_recommendations(self, project_id: UUID) -> List[StartupCloudRecommendation]:
        """Get recommendations for a project"""
        result = await self.db.execute(select(StartupCloudRecommendation).where(StartupCloudRecommendation.project_id == project_id))
        return result.scalars().all()
