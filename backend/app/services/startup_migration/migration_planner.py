from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.services.startup_migration.models import StartupMigrationPlan, CloudProvider

class MigrationPlanner:
    """
    Planner for detailing migration phases and steps.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_plan(self, project_id: UUID, settings: Dict[str, Any]) -> StartupMigrationPlan:
        """Create a migration plan based on recommendations"""
        
        provider_str = settings.get('provider', 'aws')
        try:
            provider = CloudProvider(provider_str.lower())
        except ValueError:
            provider = CloudProvider.AWS

        # Try to find existing recommendations for more accurate pricing
        from app.services.startup_migration.pricing_service import MultiCloudPricingService
        pricing_svc = MultiCloudPricingService(self.db)
        recs = await pricing_svc.get_recommendations(project_id)
        
        selected_rec = next((r for r in recs if r.provider == provider), None)
        
        migration_cost = 5000.00
        first_month_cost = 250.00
        ongoing_monthly_cost = 200.00
        
        if selected_rec:
            ongoing_monthly_cost = float(selected_rec.total_monthly_cost)
            first_month_cost = ongoing_monthly_cost * 1.2 # Buffer for migration month
            # Migration cost could be derived from complexity or flat rate
            migration_cost = ongoing_monthly_cost * 3 # Rule of thumb
            
        plan = StartupMigrationPlan(
            project_id=project_id,
            selected_provider=provider,
            selected_service=selected_rec.service_name if selected_rec else settings.get('service', 'RDS'),
            selected_instance_type=selected_rec.instance_type if selected_rec else settings.get('instance_type', 'db.m5.large'),
            timeline_weeks=4,
            start_date=datetime.now() + timedelta(days=7),
            target_completion_date=datetime.now() + timedelta(days=35),
            migration_cost=migration_cost,
            first_month_cost=first_month_cost,
            ongoing_monthly_cost=ongoing_monthly_cost,
            phases={"phase1": "Assessment", "phase2": "POC", "phase3": "Data Migration", "phase4": "Cutover"},
            checklist={"pre_migration": ["Backup", "Verify schema"], "post_migration": ["Validation", "Monitoring"]},
            risks={"data_loss": "Low", "downtime": "Medium"},
            rollback_plan={"trigger": "Critical failure", "steps": ["Restore backup", "Switch DNS back"]},
            required_tools=["pg_dump", "AWS DMS"],
            documentation_links=["https://docs.aws.amazon.com/dms/"],
            updated_at=datetime.now(),
            created_at=datetime.now()
        )
        
        self.db.add(plan)
        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def get_plan(self, project_id: UUID) -> Optional[StartupMigrationPlan]:
        """Get migration plan for a project"""
        result = await self.db.execute(select(StartupMigrationPlan).where(StartupMigrationPlan.project_id == project_id))
        return result.scalars().first()
