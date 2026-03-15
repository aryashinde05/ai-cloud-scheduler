"""
REST API endpoints for webhook management
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Query, Path
from pydantic import BaseModel, Field, validator
from supabase import Client

from app.database.database import get_supabase
from app.services.webhook_manager import (
    WebhookManager, WebhookEndpoint, WebhookEventType, 
    WebhookSecurityType, WebhookStatus, get_webhook_manager,
    WebhookEndpointModel, WebhookDelivery
)
from app.core.auth import get_current_user

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


# Pydantic models for API
class WebhookEndpointCreate(BaseModel):
    """Request model for creating webhook endpoint"""
    name: str = Field(..., min_length=1, max_length=200)
    url: str = Field(..., min_length=1, max_length=500)
    event_types: List[str] = Field(..., min_items=1)
    security_type: str = Field(default="none")
    security_config: Dict[str, Any] = Field(default_factory=dict)
    headers: Dict[str, str] = Field(default_factory=dict)
    timeout: int = Field(default=30, ge=5, le=300)
    retry_attempts: int = Field(default=3, ge=1, le=10)
    retry_delay: int = Field(default=5, ge=1, le=60)
    is_active: bool = Field(default=True)
    
    @validator('event_types')
    def validate_event_types(cls, v):
        """Validate event types are valid"""
        valid_events = {e.value for e in WebhookEventType}
        for event_type in v:
            if event_type not in valid_events:
                raise ValueError(f"Invalid event type: {event_type}")
        return v
    
    @validator('security_type')
    def validate_security_type(cls, v):
        """Validate security type is valid"""
        valid_types = {s.value for s in WebhookSecurityType}
        if v not in valid_types:
            raise ValueError(f"Invalid security type: {v}")
        return v


class WebhookEndpointUpdate(BaseModel):
    """Request model for updating webhook endpoint"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    url: Optional[str] = Field(None, min_length=1, max_length=500)
    event_types: Optional[List[str]] = Field(None, min_items=1)
    security_type: Optional[str] = None
    security_config: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None
    timeout: Optional[int] = Field(None, ge=5, le=300)
    retry_attempts: Optional[int] = Field(None, ge=1, le=10)
    retry_delay: Optional[int] = Field(None, ge=1, le=60)
    is_active: Optional[bool] = None
    
    @validator('event_types')
    def validate_event_types(cls, v):
        """Validate event types are valid"""
        if v is not None:
            valid_events = {e.value for e in WebhookEventType}
            for event_type in v:
                if event_type not in valid_events:
                    raise ValueError(f"Invalid event type: {event_type}")
        return v
    
    @validator('security_type')
    def validate_security_type(cls, v):
        """Validate security type is valid"""
        if v is not None:
            valid_types = {s.value for s in WebhookSecurityType}
            if v not in valid_types:
                raise ValueError(f"Invalid security type: {v}")
        return v


class WebhookEndpointResponse(BaseModel):
    """Response model for webhook endpoint"""
    id: str
    name: str
    url: str
    event_types: List[str]
    security_type: str
    headers: Dict[str, str]
    timeout: int
    retry_attempts: int
    retry_delay: int
    is_active: bool
    status: str
    last_success: Optional[str]
    last_failure: Optional[str]
    failure_count: int
    total_deliveries: int
    successful_deliveries: int
    success_rate: float
    recent_deliveries_24h: int
    created_at: str


class WebhookDeliveryResponse(BaseModel):
    """Response model for webhook delivery"""
    id: str
    endpoint_id: str
    event_id: str
    event_type: str
    response_status: Optional[int]
    attempt_number: int
    success: bool
    error_message: Optional[str]
    created_at: str


class WebhookTestRequest(BaseModel):
    """Request model for testing webhook endpoint"""
    event_type: str = Field(default="system.test")
    test_data: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('event_type')
    def validate_event_type(cls, v):
        """Validate event type is valid"""
        valid_events = {e.value for e in WebhookEventType}
        if v not in valid_events and v != "system.test":
            raise ValueError(f"Invalid event type: {v}")
        return v


@router.post("/endpoints", response_model=WebhookEndpointResponse)
async def create_webhook_endpoint(
    endpoint_data: WebhookEndpointCreate,
    current_user = Depends(get_current_user),
    webhook_manager: WebhookManager = Depends(get_webhook_manager)
):
    """Create a new webhook endpoint"""
    try:
        # Convert to WebhookEndpoint object
        endpoint = WebhookEndpoint(
            id=str(uuid.uuid4()),
            name=endpoint_data.name,
            url=endpoint_data.url,
            event_types=[WebhookEventType(et) for et in endpoint_data.event_types],
            security_type=WebhookSecurityType(endpoint_data.security_type),
            security_config=endpoint_data.security_config,
            headers=endpoint_data.headers,
            timeout=endpoint_data.timeout,
            retry_attempts=endpoint_data.retry_attempts,
            retry_delay=endpoint_data.retry_delay,
            is_active=endpoint_data.is_active
        )
        
        # Register endpoint
        endpoint_id = webhook_manager.register_endpoint(endpoint)
        
        # Get status for response
        status = webhook_manager.get_endpoint_status(endpoint_id)
        if not status:
            raise HTTPException(status_code=500, detail="Failed to create endpoint")
        
        return WebhookEndpointResponse(**status)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create webhook endpoint: {str(e)}")


@router.get("/endpoints", response_model=List[WebhookEndpointResponse])
async def list_webhook_endpoints(
    current_user = Depends(get_current_user),
    webhook_manager: WebhookManager = Depends(get_webhook_manager)
):
    """List all webhook endpoints"""
    try:
        endpoints = webhook_manager.list_endpoints()
        return [WebhookEndpointResponse(**endpoint) for endpoint in endpoints]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list endpoints: {str(e)}")


@router.get("/endpoints/{endpoint_id}", response_model=WebhookEndpointResponse)
async def get_webhook_endpoint(
    endpoint_id: str = Path(..., description="Webhook endpoint ID"),
    current_user = Depends(get_current_user),
    webhook_manager: WebhookManager = Depends(get_webhook_manager)
):
    """Get webhook endpoint details"""
    try:
        status = webhook_manager.get_endpoint_status(endpoint_id)
        if not status:
            raise HTTPException(status_code=404, detail="Webhook endpoint not found")
        
        return WebhookEndpointResponse(**status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get endpoint: {str(e)}")


@router.put("/endpoints/{endpoint_id}", response_model=WebhookEndpointResponse)
async def update_webhook_endpoint(
    endpoint_id: str = Path(..., description="Webhook endpoint ID"),
    endpoint_data: WebhookEndpointUpdate = ...,
    current_user = Depends(get_current_user),
    webhook_manager: WebhookManager = Depends(get_webhook_manager),
    db: Client = Depends(get_supabase)
):
    """Update webhook endpoint"""
    try:
        # Check if endpoint exists
        db_endpoint = db.query(WebhookEndpointModel).filter(
            WebhookEndpointModel.id == uuid.UUID(endpoint_id)
        ).first()
        
        if not db_endpoint:
            raise HTTPException(status_code=404, detail="Webhook endpoint not found")
        
        # Update fields
        update_data = {}
        if endpoint_data.name is not None:
            update_data["name"] = endpoint_data.name
        if endpoint_data.url is not None:
            update_data["url"] = endpoint_data.url
        if endpoint_data.event_types is not None:
            update_data["event_types"] = endpoint_data.event_types
        if endpoint_data.security_type is not None:
            update_data["security_type"] = endpoint_data.security_type
        if endpoint_data.security_config is not None:
            update_data["security_config"] = endpoint_data.security_config
        if endpoint_data.headers is not None:
            update_data["headers"] = endpoint_data.headers
        if endpoint_data.timeout is not None:
            update_data["timeout"] = endpoint_data.timeout
        if endpoint_data.retry_attempts is not None:
            update_data["retry_attempts"] = endpoint_data.retry_attempts
        if endpoint_data.retry_delay is not None:
            update_data["retry_delay"] = endpoint_data.retry_delay
        if endpoint_data.is_active is not None:
            update_data["is_active"] = endpoint_data.is_active
        
        # Update database
        db.query(WebhookEndpointModel).filter(
            WebhookEndpointModel.id == uuid.UUID(endpoint_id)
        ).update(update_data)
        db.commit()
        
        # Update in-memory endpoint if it exists
        if endpoint_id in webhook_manager.endpoints:
            endpoint = webhook_manager.endpoints[endpoint_id]
            if endpoint_data.name is not None:
                endpoint.name = endpoint_data.name
            if endpoint_data.url is not None:
                endpoint.url = endpoint_data.url
            if endpoint_data.event_types is not None:
                endpoint.event_types = [WebhookEventType(et) for et in endpoint_data.event_types]
            if endpoint_data.security_type is not None:
                endpoint.security_type = WebhookSecurityType(endpoint_data.security_type)
            if endpoint_data.security_config is not None:
                endpoint.security_config = endpoint_data.security_config
            if endpoint_data.headers is not None:
                endpoint.headers = endpoint_data.headers
            if endpoint_data.timeout is not None:
                endpoint.timeout = endpoint_data.timeout
            if endpoint_data.retry_attempts is not None:
                endpoint.retry_attempts = endpoint_data.retry_attempts
            if endpoint_data.retry_delay is not None:
                endpoint.retry_delay = endpoint_data.retry_delay
            if endpoint_data.is_active is not None:
                endpoint.is_active = endpoint_data.is_active
        
        # Get updated status
        status = webhook_manager.get_endpoint_status(endpoint_id)
        if not status:
            raise HTTPException(status_code=500, detail="Failed to update endpoint")
        
        return WebhookEndpointResponse(**status)
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update endpoint: {str(e)}")


@router.delete("/endpoints/{endpoint_id}")
async def delete_webhook_endpoint(
    endpoint_id: str = Path(..., description="Webhook endpoint ID"),
    current_user = Depends(get_current_user),
    webhook_manager: WebhookManager = Depends(get_webhook_manager)
):
    """Delete webhook endpoint"""
    try:
        # Check if endpoint exists
        status = webhook_manager.get_endpoint_status(endpoint_id)
        if not status:
            raise HTTPException(status_code=404, detail="Webhook endpoint not found")
        
        # Unregister endpoint
        webhook_manager.unregister_endpoint(endpoint_id)
        
        return {"message": "Webhook endpoint deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete endpoint: {str(e)}")


@router.post("/endpoints/{endpoint_id}/test")
async def test_webhook_endpoint(
    endpoint_id: str = Path(..., description="Webhook endpoint ID"),
    test_request: WebhookTestRequest = ...,
    current_user = Depends(get_current_user),
    webhook_manager: WebhookManager = Depends(get_webhook_manager)
):
    """Test webhook endpoint with sample data"""
    try:
        # Check if endpoint exists
        status = webhook_manager.get_endpoint_status(endpoint_id)
        if not status:
            raise HTTPException(status_code=404, detail="Webhook endpoint not found")
        
        # Create test event
        from app.services.webhook_manager import WebhookEvent, WebhookEventType
        
        test_event = WebhookEvent(
            event_type=WebhookEventType.SYSTEM_ERROR if test_request.event_type == "system.test" else WebhookEventType(test_request.event_type),
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            data={
                "test": True,
                "message": "This is a test webhook delivery",
                **test_request.test_data
            }
        )
        
        # Get endpoint and deliver directly
        if endpoint_id in webhook_manager.endpoints:
            endpoint = webhook_manager.endpoints[endpoint_id]
            await webhook_manager._deliver_webhook(endpoint, test_event)
            return {"message": "Test webhook sent successfully"}
        else:
            raise HTTPException(status_code=404, detail="Endpoint not found in manager")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test endpoint: {str(e)}")


@router.post("/endpoints/{endpoint_id}/activate")
async def activate_webhook_endpoint(
    endpoint_id: str = Path(..., description="Webhook endpoint ID"),
    current_user = Depends(get_current_user),
    webhook_manager: WebhookManager = Depends(get_webhook_manager)
):
    """Activate webhook endpoint"""
    try:
        webhook_manager.update_endpoint_status(endpoint_id, WebhookStatus.ACTIVE)
        return {"message": "Webhook endpoint activated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to activate endpoint: {str(e)}")


@router.post("/endpoints/{endpoint_id}/deactivate")
async def deactivate_webhook_endpoint(
    endpoint_id: str = Path(..., description="Webhook endpoint ID"),
    current_user = Depends(get_current_user),
    webhook_manager: WebhookManager = Depends(get_webhook_manager)
):
    """Deactivate webhook endpoint"""
    try:
        webhook_manager.update_endpoint_status(endpoint_id, WebhookStatus.INACTIVE)
        return {"message": "Webhook endpoint deactivated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to deactivate endpoint: {str(e)}")


@router.get("/endpoints/{endpoint_id}/deliveries", response_model=List[WebhookDeliveryResponse])
async def get_webhook_deliveries(
    endpoint_id: str = Path(..., description="Webhook endpoint ID"),
    limit: int = Query(default=50, ge=1, le=1000, description="Number of deliveries to return"),
    offset: int = Query(default=0, ge=0, description="Number of deliveries to skip"),
    success_only: Optional[bool] = Query(default=None, description="Filter by success status"),
    current_user = Depends(get_current_user),
    db: Client = Depends(get_supabase)
):
    """Get webhook delivery history for an endpoint"""
    try:
        # Check if endpoint exists
        endpoint_exists = db.query(WebhookEndpointModel).filter(
            WebhookEndpointModel.id == uuid.UUID(endpoint_id)
        ).first()
        
        if not endpoint_exists:
            raise HTTPException(status_code=404, detail="Webhook endpoint not found")
        
        # Build query
        query = db.query(WebhookDelivery).filter(
            WebhookDelivery.endpoint_id == uuid.UUID(endpoint_id)
        )
        
        if success_only is not None:
            query = query.filter(WebhookDelivery.success == success_only)
        
        # Get deliveries with pagination
        deliveries = query.order_by(
            WebhookDelivery.created_at.desc()
        ).offset(offset).limit(limit).all()
        
        return [
            WebhookDeliveryResponse(
                id=str(delivery.id),
                endpoint_id=str(delivery.endpoint_id),
                event_id=delivery.event_id,
                event_type=delivery.event_type,
                response_status=delivery.response_status,
                attempt_number=delivery.attempt_number,
                success=delivery.success,
                error_message=delivery.error_message,
                created_at=delivery.created_at.isoformat()
            )
            for delivery in deliveries
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get deliveries: {str(e)}")


@router.get("/event-types")
async def list_webhook_event_types(
    current_user = Depends(get_current_user)
):
    """List all available webhook event types"""
    return {
        "event_types": [
            {
                "value": event.value,
                "description": event.name.replace("_", " ").title()
            }
            for event in WebhookEventType
        ]
    }


@router.get("/security-types")
async def list_webhook_security_types(
    current_user = Depends(get_current_user)
):
    """List all available webhook security types"""
    return {
        "security_types": [
            {
                "value": security.value,
                "description": security.name.replace("_", " ").title(),
                "required_config": _get_security_config_schema(security)
            }
            for security in WebhookSecurityType
        ]
    }


def _get_security_config_schema(security_type: WebhookSecurityType) -> Dict[str, Any]:
    """Get required configuration schema for security type"""
    if security_type == WebhookSecurityType.BEARER_TOKEN:
        return {"token": "string (required)"}
    elif security_type == WebhookSecurityType.HMAC_SHA256:
        return {"secret": "string (required)"}
    elif security_type == WebhookSecurityType.BASIC_AUTH:
        return {"username": "string (required)", "password": "string (required)"}
    else:
        return {}

