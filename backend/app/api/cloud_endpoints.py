"""
Enterprise Cloud Provider Management Endpoints
Handles multi-account AWS environments for large companies
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field, validator
from supabase import Client

from app.core.auth import get_current_active_user, require_permission
from app.services.startup_migration.models import User, CloudProvider, ProviderType, CostData
from app.services.repositories import CloudProviderRepository, CostDataRepository, AuditLogRepository
from app.database.database import get_supabase
from app.services.cloud_providers import CloudProviderService, AWSCredentials
from app.utils.encryption import encryption_service

# Create router
cloud_router = APIRouter(prefix="/cloud-providers", tags=["cloud-providers"])

# Request/Response Models
class AWSCredentialsRequest(BaseModel):
    """AWS credentials input"""
    access_key_id: str = Field(..., min_length=16, max_length=32)
    secret_access_key: str = Field(..., min_length=28, max_length=64)
    region: str = Field(default="us-east-1")
    role_arn: Optional[str] = Field(None, description="Cross-account role ARN for multi-account access")
    external_id: Optional[str] = Field(None, description="External ID for cross-account role")
    
    @validator('access_key_id')
    def validate_access_key(cls, v):
        if not v.startswith('AKIA') and not v.startswith('ASIA'):
            raise ValueError('Invalid AWS access key format')
        return v

class CloudProviderRequest(BaseModel):
    """Cloud provider registration request"""
    name: str = Field(..., min_length=1, max_length=100)
    provider_type: ProviderType
    aws_credentials: Optional[AWSCredentialsRequest] = None
    description: Optional[str] = Field(None, max_length=500)
    
    @validator('aws_credentials')
    def validate_credentials(cls, v, values):
        if values.get('provider_type') == ProviderType.AWS and not v:
            raise ValueError('AWS credentials required for AWS provider')
        return v

class CloudProviderResponse(BaseModel):
    """Cloud provider response"""
    id: UUID
    name: str
    provider_type: ProviderType
    is_active: bool
    last_sync: Optional[datetime]
    sync_frequency_hours: int
    created_at: datetime
    account_count: Optional[int] = None
    total_monthly_cost: Optional[Decimal] = None
    
    class Config:
        from_attributes = True

class AccountInfo(BaseModel):
    """AWS account information"""
    account_id: str
    account_name: str
    email: str
    status: str
    joined_method: str

class CostSummaryResponse(BaseModel):
    """Cost summary response"""
    provider_id: UUID
    total_cost: Decimal
    currency: str
    period_start: date
    period_end: date
    cost_by_service: List[Dict[str, Any]]
    cost_by_account: List[Dict[str, Any]]
    cost_by_team: List[Dict[str, Any]]

class SyncRequest(BaseModel):
    """Cost data sync request"""
    start_date: date
    end_date: date
    accounts: Optional[List[str]] = Field(None, description="Specific accounts to sync (empty = all)")
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        if 'start_date' in values and (v - values['start_date']).days > 90:
            raise ValueError('Date range cannot exceed 90 days')
        return v

# Helper functions
def get_cloud_provider_service() -> CloudProviderService:
    """Get cloud provider service instance"""
    return CloudProviderService(encryption_service)

# Endpoints

@cloud_router.post("/", response_model=CloudProviderResponse, status_code=status.HTTP_201_CREATED)
async def register_cloud_provider(
    provider_data: CloudProviderRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_permission("cloud_providers", "write")),
    db: Client = Depends(get_supabase)
):
    """Register a new cloud provider for enterprise cost management"""
    provider_repo = CloudProviderRepository(db)
    audit_repo = AuditLogRepository(db)
    cloud_service = get_cloud_provider_service()
    
    try:
        # Prepare credentials
        credentials = {}
        if provider_data.provider_type == ProviderType.AWS:
            if not provider_data.aws_credentials:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="AWS credentials required"
                )
            
            credentials = {
                'access_key_id': provider_data.aws_credentials.access_key_id,
                'secret_access_key': provider_data.aws_credentials.secret_access_key,
                'region': provider_data.aws_credentials.region,
                'role_arn': provider_data.aws_credentials.role_arn,
                'external_id': provider_data.aws_credentials.external_id
            }
        
        # Register provider (includes credential validation)
        provider = await cloud_service.register_provider(
            name=provider_data.name,
            provider_type=provider_data.provider_type,
            credentials=credentials,
            created_by=current_user.id
        )
        
        # Save to database
        db_provider = await provider_repo.create(
            name=provider.name,
            provider_type=provider.provider_type,
            credentials_encrypted=provider.credentials_encrypted,
            created_by=current_user.id
        )
        
        # Log registration
        await audit_repo.log_action(
            user_id=current_user.id,
            action="cloud_provider_registered",
            resource_type="cloud_provider",
            resource_id=str(db_provider.id),
            new_values={
                "name": provider_data.name,
                "provider_type": provider_data.provider_type.value
            }
        )
        
        # Schedule initial sync in background
        background_tasks.add_task(
            initial_cost_sync,
            db_provider.id,
            current_user.id
        )
        
        # Pydantic v2: use model_validate (from_attributes=True) instead of from_orm.
        return CloudProviderResponse.model_validate(db_provider)
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register cloud provider: {str(e)}"
        )

@cloud_router.get("/", response_model=List[CloudProviderResponse])
async def list_cloud_providers(
    current_user: User = Depends(require_permission("cloud_providers", "read")),
    db: Client = Depends(get_supabase)
):
    """List all registered cloud providers"""
    provider_repo = CloudProviderRepository(db)
    cost_repo = CostDataRepository(db)
    
    try:
        # Get providers based on user role
        if current_user.role.value in ['admin', 'finance_manager']:
            providers = await provider_repo.get_active_providers()
        else:
            # Regular users see only providers they created
            providers = await provider_repo.get_by_user(current_user.id)
        
        # Enhance with cost summary
        enhanced_providers = []
        for provider in providers:
            # Get recent cost summary
            end_date = date.today()
            start_date = end_date - timedelta(days=30)
            
            cost_summary = await cost_repo.get_cost_summary_by_service(
                provider.id, start_date, end_date
            )
            
            total_cost = sum(item['total_cost'] for item in cost_summary)
            
            provider_response = CloudProviderResponse.model_validate(provider)
            provider_response.total_monthly_cost = total_cost
            enhanced_providers.append(provider_response)
        
        return enhanced_providers
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list cloud providers: {str(e)}"
        )

@cloud_router.get("/{provider_id}", response_model=CloudProviderResponse)
async def get_cloud_provider(
    provider_id: UUID,
    current_user: User = Depends(require_permission("cloud_providers", "read")),
    db: Client = Depends(get_supabase)
):
    """Get detailed information about a cloud provider"""
    provider_repo = CloudProviderRepository(db)
    
    try:
        provider = await provider_repo.get_by_id(provider_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cloud provider not found"
            )
        
        # Check access permissions
        if (current_user.role.value not in ['admin', 'finance_manager'] and 
            provider.created_by != current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Pydantic v2: use model_validate (from_attributes=True) instead of from_orm.
        return CloudProviderResponse.model_validate(provider)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cloud provider: {str(e)}"
        )

@cloud_router.get("/{provider_id}/accounts", response_model=List[AccountInfo])
async def get_provider_accounts(
    provider_id: UUID,
    current_user: User = Depends(require_permission("cloud_providers", "read")),
    db: Client = Depends(get_supabase)
):
    """Get all AWS accounts accessible through this provider"""
    provider_repo = CloudProviderRepository(db)
    cloud_service = get_cloud_provider_service()
    
    try:
        provider = await provider_repo.get_by_id(provider_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cloud provider not found"
            )
        
        # Get adapter and fetch accounts
        adapter = await cloud_service.get_adapter(provider_id)
        if not adapter:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not create provider adapter"
            )
        
        accounts = await adapter.get_accounts()
        return [AccountInfo(**account) for account in accounts]
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get provider accounts: {str(e)}"
        )

@cloud_router.post("/{provider_id}/sync")
async def sync_cost_data(
    provider_id: UUID,
    sync_request: SyncRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_permission("costs", "write")),
    db: Client = Depends(get_supabase)
):
    """Sync cost data from cloud provider"""
    provider_repo = CloudProviderRepository(db)
    audit_repo = AuditLogRepository(db)
    
    try:
        provider = await provider_repo.get_by_id(provider_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cloud provider not found"
            )
        
        # Log sync request
        await audit_repo.log_action(
            user_id=current_user.id,
            action="cost_sync_requested",
            resource_type="cloud_provider",
            resource_id=str(provider_id),
            new_values={
                "start_date": sync_request.start_date.isoformat(),
                "end_date": sync_request.end_date.isoformat(),
                "accounts": sync_request.accounts
            }
        )
        
        # Schedule sync in background
        background_tasks.add_task(
            sync_provider_cost_data,
            provider_id,
            sync_request.start_date,
            sync_request.end_date,
            sync_request.accounts,
            current_user.id
        )
        
        return {
            "message": "Cost data sync started",
            "provider_id": provider_id,
            "date_range": f"{sync_request.start_date} to {sync_request.end_date}",
            "status": "in_progress"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start cost sync: {str(e)}"
        )

@cloud_router.get("/{provider_id}/cost-summary", response_model=CostSummaryResponse)
async def get_cost_summary(
    provider_id: UUID,
    start_date: date,
    end_date: date,
    current_user: User = Depends(require_permission("costs", "read")),
    db: Client = Depends(get_supabase)
):
    """Get comprehensive cost summary for enterprise reporting"""
    cost_repo = CostDataRepository(db)
    
    try:
        # Get cost summary by service
        cost_by_service = await cost_repo.get_cost_summary_by_service(
            provider_id, start_date, end_date
        )
        
        # Get cost by tags (team attribution)
        cost_by_team = await cost_repo.get_cost_by_tags(
            provider_id, start_date, end_date, 'Team'
        )
        
        # Calculate total cost
        total_cost = sum(item['total_cost'] for item in cost_by_service)
        
        return CostSummaryResponse(
            provider_id=provider_id,
            total_cost=total_cost,
            currency="USD",
            period_start=start_date,
            period_end=end_date,
            cost_by_service=cost_by_service,
            cost_by_account=[],  # Would be populated with account-specific data
            cost_by_team=cost_by_team
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cost summary: {str(e)}"
        )

@cloud_router.delete("/{provider_id}")
async def delete_cloud_provider(
    provider_id: UUID,
    current_user: User = Depends(require_permission("cloud_providers", "delete")),
    db: Client = Depends(get_supabase)
):
    """Delete a cloud provider (admin only)"""
    provider_repo = CloudProviderRepository(db)
    audit_repo = AuditLogRepository(db)
    
    try:
        provider = await provider_repo.get_by_id(provider_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cloud provider not found"
            )
        
        # Soft delete (deactivate)
        await provider_repo.update(provider_id, is_active=False)
        
        # Log deletion
        await audit_repo.log_action(
            user_id=current_user.id,
            action="cloud_provider_deleted",
            resource_type="cloud_provider",
            resource_id=str(provider_id),
            old_values={"name": provider.name, "is_active": True},
            new_values={"is_active": False}
        )
        
        return {"message": "Cloud provider deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete cloud provider: {str(e)}"
        )

# Background tasks
async def initial_cost_sync(provider_id: UUID, user_id: UUID):
    """Initial cost sync for new provider (last 30 days)"""
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        await sync_provider_cost_data(provider_id, start_date, end_date, None, user_id)
        
        logger.info("Initial cost sync completed", provider_id=provider_id)
    except Exception as e:
        logger.error("Initial cost sync failed", provider_id=provider_id, error=str(e))

async def sync_provider_cost_data(
    provider_id: UUID, 
    start_date: date, 
    end_date: date, 
    accounts: Optional[List[str]], 
    user_id: UUID
):
    """Background task to sync cost data"""
    try:
        cloud_service = get_cloud_provider_service()
        
        # Sync cost data
        cost_records = await cloud_service.sync_cost_data(
            provider_id, start_date, end_date
        )
        
        # Save to database (would use repository in real implementation)
        # This is where you'd bulk insert the cost records
        
        logger.info("Cost data sync completed", 
                   provider_id=provider_id,
                   records=len(cost_records),
                   date_range=f"{start_date} to {end_date}")
        
    except Exception as e:
        logger.error("Cost data sync failed", 
                    provider_id=provider_id,
                    error=str(e))
