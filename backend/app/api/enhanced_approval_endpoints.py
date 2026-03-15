"""
Enhanced API Endpoints for Approval Workflow with Decision Tracking

This module provides enhanced REST API endpoints that integrate the approval
workflow engine with decision tracking and intelligent notification routing.

Requirements addressed:
- 2.3: Intelligent notification routing based on roles and urgency
- 2.4: Immediate notification to all session participants
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from pydantic import BaseModel, Field, validator
from supabase import Client

from app.database.database import get_supabase
from app.services.startup_migration.models import User
from app.services.approval_workflow_integration import enhanced_workflow_engine
from app.services.decision_tracking_system import decision_tracker, notification_service, NotificationType
from app.core.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/enhanced-approval", tags=["Enhanced Approval Workflow"])

# Request/Response Models

class OptimizationActionRequest(BaseModel):
    """Request model for optimization actions"""
    action_id: str
    action_type: str
    resource_id: str
    resource_type: str
    cost_impact: float = Field(..., ge=0)
    risk_level: str = Field(..., pattern="^(low|medium|high|critical)$")
    description: str
    proposed_changes: Dict[str, Any] = {}
    estimated_savings: float = Field(..., ge=0)
    implementation_timeline: str

class DecisionContextRequest(BaseModel):
    """Request model for decision context"""
    session_id: str
    participants: List[str]
    discussion_summary: str
    data_analyzed: List[Dict[str, Any]] = []
    alternatives_considered: List[Dict[str, Any]] = []
    risk_assessment: Dict[str, Any] = {}
    cost_benefit_analysis: Dict[str, Any] = {}
    timeline_constraints: Dict[str, Any] = {}

class ApprovalDecisionRequest(BaseModel):
    """Request model for approval decisions"""
    approved: bool
    comments: str
    conditions: List[str] = []

class ApprovalSubmissionRequest(BaseModel):
    """Request model for approval submission"""
    decision: OptimizationActionRequest
    context: DecisionContextRequest

class ApprovalStatusResponse(BaseModel):
    """Response model for approval status"""
    request_id: str
    status: str
    current_step: int
    priority: str
    deadline: datetime
    created_at: datetime
    created_by: str
    decision_summary: Dict[str, Any]
    approval_chain: List[Dict[str, Any]]
    history: List[Dict[str, Any]]

class DecisionTrackingResponse(BaseModel):
    """Response model for decision tracking"""
    decision_id: str
    status: str
    session_id: str
    created_by: str
    created_at: str
    last_updated: str
    current_approver: Optional[str]
    approval_progress: int
    timeline: List[Dict[str, Any]]

class NotificationResponse(BaseModel):
    """Response model for notifications"""
    success: bool
    recipients_notified: int
    notification_type: str
    priority: str

# API Endpoints

@router.post("/submit", response_model=Dict[str, Any])
async def submit_for_approval(
    request: ApprovalSubmissionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Client = Depends(get_supabase)
):
    """
    Submit an optimization decision for approval with enhanced tracking
    
    This endpoint integrates approval workflow with decision tracking and
    intelligent notification routing as required by 2.3 and 2.4.
    """
    try:
        # Convert request to internal models
        from app.services.approval_workflow_integration import OptimizationAction, DecisionContext
        
        decision = OptimizationAction(
            action_id=request.decision.action_id,
            action_type=request.decision.action_type,
            resource_id=request.decision.resource_id,
            resource_type=request.decision.resource_type,
            cost_impact=Decimal(str(request.decision.cost_impact)),
            risk_level=request.decision.risk_level,
            description=request.decision.description,
            proposed_changes=request.decision.proposed_changes,
            estimated_savings=Decimal(str(request.decision.estimated_savings)),
            implementation_timeline=request.decision.implementation_timeline
        )
        
        context = DecisionContext(
            session_id=request.context.session_id,
            participants=request.context.participants,
            discussion_summary=request.context.discussion_summary,
            data_analyzed=request.context.data_analyzed,
            alternatives_considered=request.context.alternatives_considered,
            risk_assessment=request.context.risk_assessment,
            cost_benefit_analysis=request.context.cost_benefit_analysis,
            timeline_constraints=request.context.timeline_constraints
        )
        
        # Submit for approval using enhanced engine
        approval_request = await enhanced_workflow_engine.submit_for_approval(decision, context)
        
        # Schedule background monitoring
        background_tasks.add_task(
            _monitor_approval_deadline,
            approval_request.request_id,
            approval_request.deadline
        )
        
        return {
            "success": True,
            "request_id": approval_request.request_id,
            "status": "submitted",
            "priority": approval_request.priority.value,
            "deadline": approval_request.deadline.isoformat(),
            "current_approver": approval_request.approval_chain.steps[0].approver_id,
            "message": "Approval request submitted successfully with intelligent notification routing"
        }
        
    except Exception as e:
        logger.error(f"Error submitting approval request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit approval request: {str(e)}"
        )

@router.post("/approve/{approval_id}", response_model=Dict[str, Any])
async def process_approval_decision(
    approval_id: str,
    decision_request: ApprovalDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: Client = Depends(get_supabase)
):
    """
    Process an approval decision with immediate session participant notification
    
    Implements requirement 2.4: Immediate notification to all session participants
    """
    try:
        # Convert to internal model
        from app.services.approval_workflow_integration import ApprovalDecision
        
        decision = ApprovalDecision(
            decision_id=str(UUID(approval_id)),
            approver_id=str(current_user.id),
            approved=decision_request.approved,
            comments=decision_request.comments,
            conditions=decision_request.conditions,
            decided_at=datetime.utcnow()
        )
        
        # Process approval with enhanced tracking and notifications
        result = await enhanced_workflow_engine.process_approval(approval_id, str(current_user.id), decision)
        
        if result.success:
            return {
                "success": True,
                "request_id": result.request_id,
                "status": result.status.value if result.status else "processed",
                "next_step": result.next_step,
                "approved": decision_request.approved,
                "message": "Approval decision processed and all session participants notified immediately"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error_message or "Failed to process approval decision"
            )
            
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid approval ID format: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error processing approval decision: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process approval decision: {str(e)}"
        )

@router.post("/escalate/{approval_id}", response_model=Dict[str, Any])
async def escalate_approval(
    approval_id: str,
    reason: str = "deadline_approaching",
    current_user: User = Depends(get_current_user),
    db: Client = Depends(get_supabase)
):
    """
    Escalate an approval request with intelligent notification routing
    
    Implements requirement 2.3: Intelligent notification routing based on roles and urgency
    """
    try:
        from app.services.approval_workflow_integration import EscalationReason
        
        # Map string reason to enum
        escalation_reason = EscalationReason(reason)
        
        # Escalate with enhanced notifications
        result = await enhanced_workflow_engine.escalate_approval(approval_id, escalation_reason)
        
        if result.success:
            return {
                "success": True,
                "escalated_to": result.escalated_to,
                "reason": result.reason.value if result.reason else reason,
                "message": "Approval escalated with intelligent notification routing to appropriate stakeholders"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error_message or "Failed to escalate approval"
            )
            
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid escalation reason: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error escalating approval: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to escalate approval: {str(e)}"
        )

@router.get("/status/{approval_id}", response_model=ApprovalStatusResponse)
async def get_approval_status(
    approval_id: str,
    current_user: User = Depends(get_current_user),
    db: Client = Depends(get_supabase)
):
    """Get detailed approval status with tracking information"""
    try:
        # Get approval status from enhanced engine
        status_data = await enhanced_workflow_engine.get_approval_status(approval_id)
        
        if "error" in status_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=status_data["error"]
            )
        
        return ApprovalStatusResponse(**status_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting approval status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get approval status: {str(e)}"
        )

@router.get("/tracking/{decision_id}", response_model=DecisionTrackingResponse)
async def get_decision_tracking(
    decision_id: str,
    current_user: User = Depends(get_current_user),
    db: Client = Depends(get_supabase)
):
    """Get decision tracking information"""
    try:
        tracking_data = await decision_tracker.get_decision_status(decision_id)
        
        if not tracking_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Decision tracking data not found"
            )
        
        return DecisionTrackingResponse(**tracking_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting decision tracking: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get decision tracking: {str(e)}"
        )

@router.get("/session/{session_id}/decisions", response_model=List[DecisionTrackingResponse])
async def get_session_decisions(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Client = Depends(get_supabase)
):
    """Get all decisions for a collaborative session"""
    try:
        decisions = await decision_tracker.get_session_decisions(session_id)
        
        return [DecisionTrackingResponse(**decision) for decision in decisions]
        
    except Exception as e:
        logger.error(f"Error getting session decisions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session decisions: {str(e)}"
        )

@router.post("/notify/session/{session_id}", response_model=NotificationResponse)
async def send_session_notification(
    session_id: str,
    notification_type: str,
    data: Dict[str, Any],
    priority: str = "medium",
    current_user: User = Depends(get_current_user),
    db: Client = Depends(get_supabase)
):
    """
    Send notification to all session participants
    
    Implements requirement 2.4: Immediate notification to all session participants
    """
    try:
        # Validate notification type
        try:
            notification_type_enum = NotificationType(notification_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid notification type: {notification_type}"
            )
        
        # Send session notification
        results = await notification_service.send_session_notification(
            session_id=session_id,
            notification_type=notification_type_enum,
            data=data,
            priority=priority
        )
        
        success_count = sum(1 for success in results.values() if success)
        
        return NotificationResponse(
            success=success_count > 0,
            recipients_notified=success_count,
            notification_type=notification_type,
            priority=priority
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending session notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send session notification: {str(e)}"
        )

@router.get("/notifications/{user_id}", response_model=List[Dict[str, Any]])
async def get_user_notifications(
    user_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Client = Depends(get_supabase)
):
    """Get notifications for a user"""
    try:
        # Check authorization (users can only get their own notifications unless admin)
        if str(current_user.id) != user_id and current_user.role.value != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access these notifications"
            )
        
        # Get notifications from Redis cache
        from app.core.redis_config import redis_manager
        
        cache_key = f"notifications:{user_id}"
        notifications = await redis_manager.get_json(cache_key) or []
        
        # Return limited results
        return notifications[:limit]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user notifications: {str(e)}"
        )

# Background task functions

async def _monitor_approval_deadline(approval_id: str, deadline: datetime):
    """Monitor approval deadline and send warnings"""
    try:
        # This would be implemented with a proper task scheduler like Celery
        # For now, just log the monitoring setup
        logger.info(f"Monitoring approval deadline for {approval_id} until {deadline}")
        
        # In a real implementation, this would:
        # 1. Schedule deadline warning notifications
        # 2. Automatically escalate if deadline is missed
        # 3. Update approval status appropriately
        
    except Exception as e:
        logger.error(f"Error monitoring approval deadline: {e}")

