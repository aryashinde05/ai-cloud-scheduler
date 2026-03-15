"""
Repository pattern implementation for data access layer
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Type, TypeVar, Generic, Any
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal

from supabase import Client

from app.services.startup_migration.models import (
    BaseModel, User, CloudProvider, CostData, Budget, BudgetAlert,
    OptimizationRecommendation, AuditLog, SystemConfiguration,
    UserRole, ProviderType, BudgetType, RecommendationType, RecommendationStatus
)

T = TypeVar('T', bound=BaseModel)

class BaseRepository(Generic[T], ABC):
    """Base repository with common CRUD operations using Supabase"""
    
    def __init__(self, client: Client, model_class: Type[T]):
        self.client = client
        self.model_class = model_class
        self.table_name = model_class.__tablename__
    
    async def create(self, **kwargs) -> Dict[str, Any]:
        """Create a new entity"""
        try:
            response = self.client.table(self.table_name).insert(kwargs).execute()
            if not response.data:
                raise ValueError(f"Failed to create {self.model_class.__name__}")
            return response.data[0]
        except Exception as e:
            raise ValueError(f"Failed to create {self.model_class.__name__}: {str(e)}")
    
    async def get_by_id(self, id: UUID) -> Optional[Dict[str, Any]]:
        """Get entity by ID"""
        try:
            response = self.client.table(self.table_name).select("*").eq("id", str(id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            raise ValueError(f"Failed to get {self.model_class.__name__} by ID: {str(e)}")
    
    async def get_all(self, 
                     filters: Optional[Dict[str, Any]] = None,
                     limit: int = 100,
                     offset: int = 0,
                     order_by: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all entities with optional filtering"""
        try:
            query = self.client.table(self.table_name).select("*")
            
            # Apply filters
            if filters:
                for key, value in filters.items():
                    if isinstance(value, list):
                        query = query.in_(key, value)
                    else:
                        query = query.eq(key, value)
            
            # Apply ordering
            if order_by:
                descending = order_by.startswith('-')
                column = order_by[1:] if descending else order_by
                query = query.order(column, desc=descending)
            
            # Apply pagination
            query = query.range(offset, offset + limit - 1)
            
            response = query.execute()
            return response.data
        except Exception as e:
            raise ValueError(f"Failed to get {self.model_class.__name__} entities: {str(e)}")
    
    async def update(self, id: UUID, **kwargs) -> Optional[Dict[str, Any]]:
        """Update entity by ID"""
        try:
            # Remove None values and non-updatable fields
            update_data = {k: v for k, v in kwargs.items() 
                          if v is not None and k not in ['id', 'created_at']}
            
            if not update_data:
                return await self.get_by_id(id)
            
            # Add updated_at timestamp
            update_data['updated_at'] = datetime.utcnow().isoformat()
            
            response = self.client.table(self.table_name).update(update_data).eq("id", str(id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            raise ValueError(f"Failed to update {self.model_class.__name__}: {str(e)}")
    
    async def delete(self, id: UUID) -> bool:
        """Delete entity by ID"""
        try:
            response = self.client.table(self.table_name).delete().eq("id", str(id)).execute()
            return len(response.data) > 0
        except Exception as e:
            raise ValueError(f"Failed to delete {self.model_class.__name__}: {str(e)}")
    
    async def bulk_create(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Bulk create entities"""
        try:
            response = self.client.table(self.table_name).insert(items).execute()
            return response.data
        except Exception as e:
            raise ValueError(f"Failed to bulk create {self.model_class.__name__}: {str(e)}")
    
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count entities with optional filtering"""
        try:
            query = self.client.table(self.table_name).select("*", count="exact")
            
            if filters:
                for key, value in filters.items():
                    if isinstance(value, list):
                        query = query.in_(key, value)
                    else:
                        query = query.eq(key, value)
            
            response = query.limit(1).execute()
            return response.count if response.count is not None else 0
        except Exception as e:
            raise ValueError(f"Failed to count {self.model_class.__name__} entities: {str(e)}")

class UserRepository(BaseRepository[User]):
    """Repository for User entities using Supabase"""
    
    def __init__(self, client: Client):
        super().__init__(client, User)
    
    async def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email address"""
        try:
            response = self.client.table(self.table_name).select("*").eq("email", email.lower()).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            raise ValueError(f"Failed to get user by email: {str(e)}")
    
    async def get_active_users(self) -> List[Dict[str, Any]]:
        """Get all active users"""
        return await self.get_all(filters={'is_active': True})
    
    async def get_users_by_role(self, role: UserRole) -> List[Dict[str, Any]]:
        """Get users by role"""
        return await self.get_all(filters={'role': role, 'is_active': True})
    
    async def update_last_login(self, user_id: UUID) -> None:
        """Update user's last login timestamp"""
        await self.update(user_id, last_login=datetime.utcnow().isoformat())

class CloudProviderRepository(BaseRepository[CloudProvider]):
    """Repository for CloudProvider entities using Supabase"""
    
    def __init__(self, client: Client):
        super().__init__(client, CloudProvider)
    
    async def get_active_providers(self) -> List[Dict[str, Any]]:
        """Get all active cloud providers"""
        return await self.get_all(filters={'is_active': True})
    
    async def get_by_type(self, provider_type: ProviderType) -> List[Dict[str, Any]]:
        """Get providers by type"""
        return await self.get_all(filters={'provider_type': provider_type, 'is_active': True})
    
    async def get_by_user(self, user_id: UUID) -> List[CloudProvider]:
        """Get providers created by a specific user"""
        return await self.get_all(filters={'created_by': user_id})
    
    async def update_last_sync(self, provider_id: UUID) -> None:
        """Update provider's last sync timestamp"""
        await self.update(provider_id, last_sync=datetime.utcnow())

class CostDataRepository(BaseRepository[CostData]):
    """Repository for CostData entities with time-series optimizations"""
    
    def __init__(self, Client: Client):
        super().__init__(Client, CostData)
    
    async def get_cost_data_by_date_range(self, 
                                         provider_id: UUID,
                                         start_date: date,
                                         end_date: date,
                                         resource_types: Optional[List[str]] = None) -> List[CostData]:
        """Get cost data for a date range"""
        try:
            query = select(CostData).where(
                and_(
                    CostData.provider_id == provider_id,
                    CostData.cost_date >= start_date,
                    CostData.cost_date <= end_date
                )
            )
            
            if resource_types:
                query = query.where(CostData.resource_type.in_(resource_types))
            
            query = query.order_by(CostData.cost_date.desc())
            
            result = await self.Client.execute(query)
            return result.scalars().all()
        except Exception as e:
            raise ValueError(f"Failed to get cost data by date range: {str(e)}")
    
    async def get_cost_summary_by_service(self, 
                                         provider_id: UUID,
                                         start_date: date,
                                         end_date: date) -> List[Dict[str, Any]]:
        """Get cost summary grouped by service"""
        try:
            query = select(
                CostData.service_name,
                func.sum(CostData.cost_amount).label('total_cost'),
                func.count(CostData.id).label('resource_count')
            ).where(
                and_(
                    CostData.provider_id == provider_id,
                    CostData.cost_date >= start_date,
                    CostData.cost_date <= end_date
                )
            ).group_by(CostData.service_name).order_by(desc('total_cost'))
            
            result = await self.Client.execute(query)
            return [
                {
                    'service_name': row.service_name,
                    'total_cost': row.total_cost,
                    'resource_count': row.resource_count
                }
                for row in result
            ]
        except Exception as e:
            raise ValueError(f"Failed to get cost summary by service: {str(e)}")
    
    async def get_cost_by_tags(self, 
                              provider_id: UUID,
                              start_date: date,
                              end_date: date,
                              tag_key: str) -> List[Dict[str, Any]]:
        """Get cost data grouped by tag values"""
        try:
            # This is a simplified version - in production, you'd use more sophisticated JSONB queries
            query = select(CostData).where(
                and_(
                    CostData.provider_id == provider_id,
                    CostData.cost_date >= start_date,
                    CostData.cost_date <= end_date,
                    CostData.tags.has_key(tag_key)
                )
            )
            
            result = await self.Client.execute(query)
            cost_data = result.scalars().all()
            
            # Group by tag value
            tag_costs = {}
            for item in cost_data:
                tag_value = item.tags.get(tag_key, 'untagged')
                if tag_value not in tag_costs:
                    tag_costs[tag_value] = {'total_cost': Decimal('0'), 'resource_count': 0}
                tag_costs[tag_value]['total_cost'] += item.cost_amount
                tag_costs[tag_value]['resource_count'] += 1
            
            return [
                {
                    'tag_value': tag_value,
                    'total_cost': data['total_cost'],
                    'resource_count': data['resource_count']
                }
                for tag_value, data in sorted(tag_costs.items(), 
                                            key=lambda x: x[1]['total_cost'], reverse=True)
            ]
        except Exception as e:
            raise ValueError(f"Failed to get cost by tags: {str(e)}")

class BudgetRepository(BaseRepository[Budget]):
    """Repository for Budget entities"""
    
    def __init__(self, Client: Client):
        super().__init__(Client, Budget)
    
    async def get_active_budgets(self) -> List[Budget]:
        """Get all active budgets"""
        return await self.get_all(filters={'is_active': True})
    
    async def get_budgets_by_type(self, budget_type: BudgetType) -> List[Budget]:
        """Get budgets by type"""
        return await self.get_all(filters={'budget_type': budget_type, 'is_active': True})
    
    async def get_budgets_for_date(self, target_date: date) -> List[Budget]:
        """Get budgets that are active for a specific date"""
        try:
            query = select(Budget).where(
                and_(
                    Budget.is_active == True,
                    Budget.start_date <= target_date,
                    or_(Budget.end_date.is_(None), Budget.end_date >= target_date)
                )
            )
            
            result = await self.Client.execute(query)
            return result.scalars().all()
        except Exception as e:
            raise ValueError(f"Failed to get budgets for date: {str(e)}")
    
    async def get_by_user(self, user_id: UUID) -> List[Budget]:
        """Get budgets created by a specific user"""
        return await self.get_all(filters={'created_by': user_id})

class BudgetAlertRepository(BaseRepository[BudgetAlert]):
    """Repository for BudgetAlert entities"""
    
    def __init__(self, Client: Client):
        super().__init__(Client, BudgetAlert)
    
    async def get_unacknowledged_alerts(self) -> List[BudgetAlert]:
        """Get all unacknowledged alerts"""
        return await self.get_all(filters={'acknowledged': False})
    
    async def get_alerts_by_budget(self, budget_id: UUID) -> List[BudgetAlert]:
        """Get alerts for a specific budget"""
        return await self.get_all(
            filters={'budget_id': budget_id},
            order_by='-created_at'
        )
    
    async def acknowledge_alert(self, alert_id: UUID, user_id: UUID) -> Optional[BudgetAlert]:
        """Acknowledge a budget alert"""
        return await self.update(
            alert_id,
            acknowledged=True,
            acknowledged_at=datetime.utcnow(),
            acknowledged_by=user_id
        )

class OptimizationRecommendationRepository(BaseRepository[OptimizationRecommendation]):
    """Repository for OptimizationRecommendation entities"""
    
    def __init__(self, Client: Client):
        super().__init__(Client, OptimizationRecommendation)
    
    async def get_by_provider(self, provider_id: UUID) -> List[OptimizationRecommendation]:
        """Get recommendations for a specific provider"""
        return await self.get_all(
            filters={'provider_id': provider_id},
            order_by='-potential_savings'
        )
    
    async def get_by_type(self, recommendation_type: RecommendationType) -> List[OptimizationRecommendation]:
        """Get recommendations by type"""
        return await self.get_all(
            filters={'recommendation_type': recommendation_type},
            order_by='-potential_savings'
        )
    
    async def get_pending_recommendations(self) -> List[OptimizationRecommendation]:
        """Get all pending recommendations"""
        return await self.get_all(
            filters={'status': RecommendationStatus.PENDING},
            order_by='-potential_savings'
        )
    
    async def get_total_potential_savings(self, provider_id: Optional[UUID] = None) -> Decimal:
        """Get total potential savings"""
        try:
            query = select(func.sum(OptimizationRecommendation.potential_savings))
            
            conditions = [OptimizationRecommendation.status == RecommendationStatus.PENDING]
            if provider_id:
                conditions.append(OptimizationRecommendation.provider_id == provider_id)
            
            query = query.where(and_(*conditions))
            
            result = await self.Client.execute(query)
            total = result.scalar()
            return total or Decimal('0')
        except Exception as e:
            raise ValueError(f"Failed to get total potential savings: {str(e)}")

class AuditLogRepository(BaseRepository[AuditLog]):
    """Repository for AuditLog entities"""
    
    def __init__(self, Client: Client):
        super().__init__(Client, AuditLog)
    
    async def log_action(self, 
                        user_id: UUID,
                        action: str,
                        resource_type: str,
                        resource_id: Optional[str] = None,
                        old_values: Optional[Dict[str, Any]] = None,
                        new_values: Optional[Dict[str, Any]] = None,
                        ip_address: Optional[str] = None,
                        user_agent: Optional[str] = None,
                        correlation_id: Optional[str] = None) -> AuditLog:
        """Log an audit action"""
        return await self.create(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id
        )
    
    async def get_user_actions(self, user_id: UUID, limit: int = 100) -> List[AuditLog]:
        """Get recent actions by a user"""
        return await self.get_all(
            filters={'user_id': user_id},
            limit=limit,
            order_by='-created_at'
        )
    
    async def get_resource_history(self, resource_type: str, resource_id: str) -> List[AuditLog]:
        """Get audit history for a specific resource"""
        return await self.get_all(
            filters={'resource_type': resource_type, 'resource_id': resource_id},
            order_by='-created_at'
        )

class SystemConfigurationRepository(BaseRepository[SystemConfiguration]):
    """Repository for SystemConfiguration entities"""
    
    def __init__(self, Client: Client):
        super().__init__(Client, SystemConfiguration)
    
    async def get_by_key(self, key: str) -> Optional[SystemConfiguration]:
        """Get configuration by key"""
        try:
            result = await self.Client.execute(
                select(SystemConfiguration).where(SystemConfiguration.key == key)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            raise ValueError(f"Failed to get configuration by key: {str(e)}")
    
    async def set_config(self, key: str, value: Any, description: Optional[str] = None, 
                        is_encrypted: bool = False, updated_by: Optional[UUID] = None) -> SystemConfiguration:
        """Set or update a configuration value"""
        existing = await self.get_by_key(key)
        
        if existing:
            return await self.update(
                existing.id,
                value=value,
                description=description,
                is_encrypted=is_encrypted,
                updated_by=updated_by
            )
        else:
            return await self.create(
                key=key,
                value=value,
                description=description,
                is_encrypted=is_encrypted,
                updated_by=updated_by
            )
    
    async def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key"""
        config = await self.get_by_key(key)
        return config.value if config else default

