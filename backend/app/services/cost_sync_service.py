\"\"\"
Azure Cost Data Sync Service

Background task for periodic ingestion of Azure cost data into the shared database schema.
\"\"\"

import logging
import asyncio
import uuid
from datetime import datetime, date, timedelta
from typing import List, Dict, Any

from sqlalchemy import select
from app.database.database import AsyncSessionLocal
from app.models.models import CloudProvider, CostData, ProviderType, OptimizationRecommendation
from app.cloud.azure.azure_cost_analyzer import AzureCostAnalyzer
from app.utils.encryption import encryption_service

logger = logging.getLogger(__name__)

async def sync_azure_cost_data(provider_id: uuid.UUID):
    \"\"\"
    Pull cost data from Azure and normalize it into our local database.
    \"\"\"
    logger.info(f\"Starting Azure cost sync for provider {provider_id}\")
    
    async with AsyncSessionLocal() as session:
        # 1. Fetch Provider Credentials
        provider = await session.get(CloudProvider, provider_id)
        if not provider or provider.provider_type != ProviderType.AZURE:
            logger.error(f\"Invalid Azure provider ID {provider_id}\")
            return

        try:
            # Decrypt credentials
            creds = encryption_service.decrypt_dict(provider.credentials_encrypted)
            
            # 2. Initialize Analyzer
            analyzer = AzureCostAnalyzer(
                tenant_id=creds['tenant_id'],
                client_id=creds['client_id'],
                client_secret=creds['client_secret'],
                subscription_id=creds['subscription_id']
            )

            # 3. Fetch Raw Cost Data (Daily for last 30 days)
            days_back = 30
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # We use a custom query to get resource-level granularity for ingestion
            # Note: This is a simplified version of actual production ingestion
            from azure.mgmt.costmanagement.models import (
                QueryDefinition, QueryTimePeriod, QueryDataset, QueryAggregation, QueryGrouping
            )
            
            query_def = QueryDefinition(
                type=\"ActualCost\",
                timeframe=\"Custom\",
                time_period=QueryTimePeriod(from_property=start_date, to=end_date),
                dataset=QueryDataset(
                    granularity=\"Daily\",
                    aggregation={\"totalCost\": QueryAggregation(name=\"PreTaxCost\", function=\"Sum\")},
                    grouping=[
                        QueryGrouping(type=\"Dimension\", name=\"ResourceId\"),
                        QueryGrouping(type=\"Dimension\", name=\"ServiceName\"),
                        QueryGrouping(type=\"Dimension\", name=\"UsageDate\")
                    ]
                )
            )
            
            cost_results = analyzer.cost_client.query.usage(analyzer.scope, query_def)
            
            # 4. Normalize and Store in cost_data
            if cost_results and cost_results.rows:
                for row in cost_results.rows:
                    # Row: [cost, resource_id, service_name, usage_date, currency]
                    cost_amount = float(row[0])
                    res_id = str(row[1])
                    service_name = str(row[2])
                    cost_date_str = str(row[3])
                    currency = str(row[4])
                    
                    cost_date = datetime.strptime(cost_date_str[:8], '%Y%m%d').date() if len(cost_date_str) >= 8 else date.today()

                    # Create or update cost record
                    # In production, we'd check for duplicates
                    new_cost = CostData(
                        provider_id=provider_id,
                        resource_id=res_id,
                        resource_type=\"AzureResource\", # Could be more specific by parsing res_id
                        service_name=service_name,
                        cost_amount=cost_amount,
                        currency=currency,
                        cost_date=cost_date,
                        usage_quantity=0, # Optional: fetch usage metrics separately
                        tags={},
                        resource_metadata={\"last_sync\": datetime.utcnow().isoformat()}
                    )
                    session.add(new_cost)

            # 5. Fetch and Store Recommendations
            recs = analyzer.get_optimization_recommendations()
            for r in recs:
                new_rec = OptimizationRecommendation(
                    provider_id=provider_id,
                    resource_id=r.service, # Resource ID for advisor is often service-scoped
                    resource_type=\"AzureService\",
                    recommendation_type=r.opportunity_type,
                    description=r.description,
                    potential_savings=r.potential_monthly_savings,
                    confidence_score=0.9 if r.confidence_level == 'high' else 0.7,
                    status=\"new\",
                    generated_at=datetime.utcnow()
                )
                session.add(new_rec)

            # 6. Update Provider last_sync
            provider.last_sync = datetime.utcnow()
            
            await session.commit()
            logger.info(f\"Successfully synced Azure cost data for provider {provider_id}\")

        except Exception as e:
            await session.rollback()
            logger.error(f\"Azure cost sync failed for {provider_id}: {str(e)}\")
            raise
async def schedule_azure_syncs():
    \"\"\"Discover all active Azure providers and schedule sync jobs\"\"\"
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CloudProvider).where(
                CloudProvider.provider_type == ProviderType.AZURE,
                CloudProvider.is_active == True
            )
        )
        providers = result.scalars().all()
        
        for p in providers:
            # In a real system, we'd use Celery or a scheduler here
            # For now, we just log the scheduling
            logger.info(f\"Scheduling sync for Azure provider: {p.name} ({p.id})\")
            asyncio.create_task(sync_azure_cost_data(p.id))
