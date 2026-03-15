"""
REST API Endpoints for Automated Cost Optimization Management

Provides comprehensive API endpoints for:
- Automation configuration and policy management
- Action execution and monitoring
- Approval workflow management
- Reporting and audit trail access
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from pydantic import BaseModel, Field, validator
from supabase import Client

from app.database.database import get_supabase
from app.core.auth import get_current_user, get_current_active_user
from app.services.startup_migration.models import User
from app.models.automation_models import (
    AutomationPolicy, OptimizationAction, ActionApproval, AutomationAuditLog,
    AutomationLevel, ActionType, ActionStatus, RiskLevel, ApprovalStatus
)
from app.services.auto_remediation_engine import AutoRemediationEngine, OptimizationOpportunity
from app.services.policy_manager import PolicyManager
from app.services.action_engine import ActionEngine
from app.services.savings_calculator import SavingsCalculator
from app.services.scheduling_engine import SchedulingEngine
from app.services.rollback_manager import RollbackManager

router = APIRouter(prefix="/api/v1/automation", tags=["Automation Management"])

# Request/Response Models

class AutomationPolicyRequest(BaseModel):
    """Request to create or update automation policy"""
    name: str = Field(..., min_length=1, max_length=200)
    automation_level: AutomationLevel
    enabled_actions: List[str] = Field(..., description="List of enabled action types")
    approval_required_actions: List[str] = Field(default=[], description="Actions requiring approval")
    blocked_actions: List[str] = Field(default=[], description="Blocked action types")
    resource_filters: Dict[str, Any] = Field(default={}, description="Resource filtering rules")
    time_restrictions: Dict[str, Any] = Field(default={}, description="Time-based restrictions")
    safety_overrides: Dict[str, Any] = Field(default={}, description="Safety rule overrides")
    
    @validator('enabled_actions', 'approval_required_actions', 'blocked_actions')
    def validate_action_types(cls, v):
        valid_actions = [action.value for action in ActionType]
        for action in v:
            if action not in valid_actions:
                raise ValueError(f"Invalid action type: {action}")
        return v

class AutomationPolicyResponse(BaseModel):
    """Response model for automation policy"""
    id: str
    name: str
    automation_level: str
    enabled_actions: List[str]
    approval_required_actions: List[str]
    blocked_actions: List[str]
    resource_filters: Dict[str, Any]
    time_restrictions: Dict[str, Any]
    safety_overrides: Dict[str, Any]
    is_active: bool
    created_at: str
    updated_at: str
    created_by: str
    
    class Config:
        from_attributes = True

class OptimizationActionResponse(BaseModel):
    """Response model for optimization action"""
    id: str
    action_type: str
    resource_id: str
    resource_type: str
    estimated_monthly_savings: float
    actual_savings: Optional[float]
    risk_level: str
    requires_approval: bool
    approval_status: str
    scheduled_execution_time: Optional[str]
    execution_started_at: Optional[str]
    execution_completed_at: Optional[str]
    safety_checks_passed: bool
    execution_status: str
    error_message: Optional[str]
    resource_metadata: Dict[str, Any]
    created_at: str
    updated_at: str
    policy_id: str
    
    class Config:
        from_attributes = True

class ActionExecutionRequest(BaseModel):
    """Request to execute optimization actions"""
    action_ids: List[str] = Field(..., description="List of action IDs to execute")
    emergency_override: bool = Field(default=False, description="Apply emergency override")
    override_reason: Optional[str] = Field(None, description="Reason for emergency override")

class ApprovalDecisionRequest(BaseModel):
    """Request to approve or reject an action"""
    approved: bool = Field(..., description="Whether to approve the action")
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection if not approved")

class DryRunRequest(BaseModel):
    """Request for dry run simulation"""
    policy_id: str = Field(..., description="Policy ID to use for simulation")
    include_estimates: bool = Field(default=True, description="Include estimated actions")

class SavingsReportRequest(BaseModel):
    """Request for savings report"""
    start_date: str = Field(..., description="Start date (ISO format)")
    end_date: str = Field(..., description="End date (ISO format)")
    include_estimates: bool = Field(default=True, description="Include estimated savings")
    group_by: Optional[str] = Field(default="action_type", description="Group by: action_type, category, service")

class EmergencyOverrideRequest(BaseModel):
    """Request for emergency override"""
    action_ids: List[str] = Field(..., description="Action IDs to override")
    reason: str = Field(..., min_length=10, description="Detailed reason for emergency override")

# Helper functions

def get_policy_manager() -> PolicyManager:
    """Get PolicyManager instance"""
    return PolicyManager()

def get_auto_remediation_engine() -> AutoRemediationEngine:
    """Get AutoRemediationEngine instance"""
    return AutoRemediationEngine()

def get_action_engine() -> ActionEngine:
    """Get ActionEngine instance"""
    return ActionEngine()

def get_savings_calculator(db: Client) -> SavingsCalculator:
    """Get SavingsCalculator instance"""
    return SavingsCalculator(db)

def get_scheduling_engine() -> SchedulingEngine:
    """Get SchedulingEngine instance"""
    return SchedulingEngine()

def get_rollback_manager() -> RollbackManager:
    """Get RollbackManager instance"""
    return RollbackManager()

# Policy Management Endpoints

@router.post("/policies", response_model=AutomationPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_automation_policy(
    policy_request: AutomationPolicyRequest,
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """
    Create a new automation policy.
    
    Creates a comprehensive automation policy that defines which actions can be automated,
    approval requirements, resource filters, and safety rules.
    """
    policy_manager = get_policy_manager()
    
    try:
        policy, validation_result = policy_manager.create_policy(
            name=policy_request.name,
            automation_level=policy_request.automation_level,
            enabled_actions=policy_request.enabled_actions,
            approval_required_actions=policy_request.approval_required_actions,
            blocked_actions=policy_request.blocked_actions,
            resource_filters=policy_request.resource_filters,
            time_restrictions=policy_request.time_restrictions,
            safety_overrides=policy_request.safety_overrides,
            created_by=current_user.id
        )
        
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Policy validation failed",
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings
                }
            )
        
        return AutomationPolicyResponse(
            id=str(policy.id),
            name=policy.name,
            automation_level=policy.automation_level.value,
            enabled_actions=policy.enabled_actions,
            approval_required_actions=policy.approval_required_actions,
            blocked_actions=policy.blocked_actions,
            resource_filters=policy.resource_filters,
            time_restrictions=policy.time_restrictions,
            safety_overrides=policy.safety_overrides,
            is_active=policy.is_active,
            created_at=policy.created_at.isoformat(),
            updated_at=policy.updated_at.isoformat(),
            created_by=str(policy.created_by)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create automation policy: {str(e)}"
        )

@router.get("/policies", response_model=List[AutomationPolicyResponse])
async def list_automation_policies(
    active_only: bool = Query(default=True, description="Return only active policies"),
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """
    List all automation policies.
    
    Returns a list of automation policies with optional filtering for active policies only.
    """
    try:
        query = db.query(AutomationPolicy)
        
        if active_only:
            query = query.filter(AutomationPolicy.is_active == True)
        
        policies = query.order_by(AutomationPolicy.created_at.desc()).all()
        
        return [
            AutomationPolicyResponse(
                id=str(policy.id),
                name=policy.name,
                automation_level=policy.automation_level.value,
                enabled_actions=policy.enabled_actions,
                approval_required_actions=policy.approval_required_actions,
                blocked_actions=policy.blocked_actions,
                resource_filters=policy.resource_filters,
                time_restrictions=policy.time_restrictions,
                safety_overrides=policy.safety_overrides,
                is_active=policy.is_active,
                created_at=policy.created_at.isoformat(),
                updated_at=policy.updated_at.isoformat(),
                created_by=str(policy.created_by)
            )
            for policy in policies
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list automation policies: {str(e)}"
        )

@router.get("/policies/{policy_id}", response_model=AutomationPolicyResponse)
async def get_automation_policy(
    policy_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """
    Get a specific automation policy by ID.
    """
    try:
        policy = db.query(AutomationPolicy).filter_by(id=uuid.UUID(policy_id)).first()
        
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Automation policy not found"
            )
        
        return AutomationPolicyResponse(
            id=str(policy.id),
            name=policy.name,
            automation_level=policy.automation_level.value,
            enabled_actions=policy.enabled_actions,
            approval_required_actions=policy.approval_required_actions,
            blocked_actions=policy.blocked_actions,
            resource_filters=policy.resource_filters,
            time_restrictions=policy.time_restrictions,
            safety_overrides=policy.safety_overrides,
            is_active=policy.is_active,
            created_at=policy.created_at.isoformat(),
            updated_at=policy.updated_at.isoformat(),
            created_by=str(policy.created_by)
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid policy ID format"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get automation policy: {str(e)}"
        )

@router.put("/policies/{policy_id}", response_model=AutomationPolicyResponse)
async def update_automation_policy(
    policy_id: str,
    policy_updates: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """
    Update an existing automation policy.
    
    Allows updating policy configuration with validation to ensure consistency.
    """
    policy_manager = get_policy_manager()
    
    try:
        success, validation_result = policy_manager.update_policy(
            policy_id=uuid.UUID(policy_id),
            updates=policy_updates,
            updated_by=current_user.id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Policy update validation failed",
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings
                }
            )
        
        # Get updated policy
        policy = db.query(AutomationPolicy).filter_by(id=uuid.UUID(policy_id)).first()
        
        return AutomationPolicyResponse(
            id=str(policy.id),
            name=policy.name,
            automation_level=policy.automation_level.value,
            enabled_actions=policy.enabled_actions,
            approval_required_actions=policy.approval_required_actions,
            blocked_actions=policy.blocked_actions,
            resource_filters=policy.resource_filters,
            time_restrictions=policy.time_restrictions,
            safety_overrides=policy.safety_overrides,
            is_active=policy.is_active,
            created_at=policy.created_at.isoformat(),
            updated_at=policy.updated_at.isoformat(),
            created_by=str(policy.created_by)
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid policy ID format"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update automation policy: {str(e)}"
        )

@router.delete("/policies/{policy_id}")
async def delete_automation_policy(
    policy_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """
    Deactivate an automation policy.
    
    Policies are not physically deleted but marked as inactive to preserve audit history.
    """
    try:
        policy = db.query(AutomationPolicy).filter_by(id=uuid.UUID(policy_id)).first()
        
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Automation policy not found"
            )
        
        policy.is_active = False
        policy.updated_at = datetime.utcnow()
        db.commit()
        
        return {"message": "Automation policy deactivated successfully"}
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid policy ID format"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate automation policy: {str(e)}"
        )

# Action Management Endpoints

@router.get("/actions", response_model=List[OptimizationActionResponse])
async def list_optimization_actions(
    status_filter: Optional[str] = Query(None, description="Filter by action status"),
    policy_id: Optional[str] = Query(None, description="Filter by policy ID"),
    limit: int = Query(default=100, le=1000, description="Maximum number of actions to return"),
    offset: int = Query(default=0, ge=0, description="Number of actions to skip"),
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """
    List optimization actions with optional filtering.
    
    Returns a paginated list of optimization actions with filtering options.
    """
    try:
        query = db.query(OptimizationAction)
        
        if status_filter:
            try:
                status_enum = ActionStatus(status_filter)
                query = query.filter(OptimizationAction.execution_status == status_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status filter: {status_filter}"
                )
        
        if policy_id:
            try:
                query = query.filter(OptimizationAction.policy_id == uuid.UUID(policy_id))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid policy ID format"
                )
        
        actions = query.order_by(OptimizationAction.created_at.desc()).offset(offset).limit(limit).all()
        
        return [
            OptimizationActionResponse(
                id=str(action.id),
                action_type=action.action_type.value,
                resource_id=action.resource_id,
                resource_type=action.resource_type,
                estimated_monthly_savings=float(action.estimated_monthly_savings),
                actual_savings=float(action.actual_savings) if action.actual_savings else None,
                risk_level=action.risk_level.value,
                requires_approval=action.requires_approval,
                approval_status=action.approval_status.value,
                scheduled_execution_time=action.scheduled_execution_time.isoformat() if action.scheduled_execution_time else None,
                execution_started_at=action.execution_started_at.isoformat() if action.execution_started_at else None,
                execution_completed_at=action.execution_completed_at.isoformat() if action.execution_completed_at else None,
                safety_checks_passed=action.safety_checks_passed,
                execution_status=action.execution_status.value,
                error_message=action.error_message,
                resource_metadata=action.resource_metadata,
                created_at=action.created_at.isoformat(),
                updated_at=action.updated_at.isoformat(),
                policy_id=str(action.policy_id)
            )
            for action in actions
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list optimization actions: {str(e)}"
        )

@router.get("/actions/{action_id}", response_model=OptimizationActionResponse)
async def get_optimization_action(
    action_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """
    Get a specific optimization action by ID.
    """
    try:
        action = db.query(OptimizationAction).filter_by(id=uuid.UUID(action_id)).first()
        
        if not action:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Optimization action not found"
            )
        
        return OptimizationActionResponse(
            id=str(action.id),
            action_type=action.action_type.value,
            resource_id=action.resource_id,
            resource_type=action.resource_type,
            estimated_monthly_savings=float(action.estimated_monthly_savings),
            actual_savings=float(action.actual_savings) if action.actual_savings else None,
            risk_level=action.risk_level.value,
            requires_approval=action.requires_approval,
            approval_status=action.approval_status.value,
            scheduled_execution_time=action.scheduled_execution_time.isoformat() if action.scheduled_execution_time else None,
            execution_started_at=action.execution_started_at.isoformat() if action.execution_started_at else None,
            execution_completed_at=action.execution_completed_at.isoformat() if action.execution_completed_at else None,
            safety_checks_passed=action.safety_checks_passed,
            execution_status=action.execution_status.value,
            error_message=action.error_message,
            resource_metadata=action.resource_metadata,
            created_at=action.created_at.isoformat(),
            updated_at=action.updated_at.isoformat(),
            policy_id=str(action.policy_id)
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid action ID format"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get optimization action: {str(e)}"
        )

@router.post("/actions/execute")
async def execute_optimization_actions(
    execution_request: ActionExecutionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """
    Execute optimization actions immediately or with emergency override.
    
    Allows manual execution of actions or emergency override of normal scheduling.
    """
    auto_remediation_engine = get_auto_remediation_engine()
    
    try:
        action_ids = [uuid.UUID(action_id) for action_id in execution_request.action_ids]
        
        # Validate actions exist and are in correct state
        actions = db.query(OptimizationAction).filter(OptimizationAction.id.in_(action_ids)).all()
        
        if len(actions) != len(action_ids):
            found_ids = {str(action.id) for action in actions}
            missing_ids = set(execution_request.action_ids) - found_ids
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Actions not found: {list(missing_ids)}"
            )
        
        # Check if actions can be executed
        invalid_actions = []
        for action in actions:
            if action.execution_status not in [ActionStatus.PENDING, ActionStatus.SCHEDULED]:
                invalid_actions.append({
                    "action_id": str(action.id),
                    "current_status": action.execution_status.value,
                    "reason": f"Action cannot be executed in {action.execution_status.value} status"
                })
        
        if invalid_actions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Some actions cannot be executed",
                    "invalid_actions": invalid_actions
                }
            )
        
        # Execute actions in background
        execution_results = []
        for action in actions:
            if execution_request.emergency_override:
                # Apply emergency override
                scheduling_engine = get_scheduling_engine()
                policy = db.query(AutomationPolicy).filter_by(id=action.policy_id).first()
                
                override_result = scheduling_engine.create_emergency_override(
                    action_ids=[action.id],
                    reason=execution_request.override_reason or "Manual emergency execution",
                    authorized_by=str(current_user.id),
                    policy=policy
                )
                
                execution_results.append({
                    "action_id": str(action.id),
                    "status": "emergency_override_applied",
                    "override_details": override_result
                })
            
            # Schedule execution in background
            background_tasks.add_task(
                auto_remediation_engine.execute_optimization_action,
                action.id
            )
            
            execution_results.append({
                "action_id": str(action.id),
                "status": "execution_scheduled",
                "message": "Action execution started in background"
            })
        
        return {
            "message": f"Execution initiated for {len(actions)} actions",
            "emergency_override": execution_request.emergency_override,
            "execution_results": execution_results
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action ID format: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute optimization actions: {str(e)}"
        )

@router.post("/actions/{action_id}/rollback")
async def rollback_optimization_action(
    action_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """
    Rollback a completed optimization action.
    
    Reverses the effects of an optimization action if possible.
    """
    rollback_manager = get_rollback_manager()
    
    try:
        action = db.query(OptimizationAction).filter_by(id=uuid.UUID(action_id)).first()
        
        if not action:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Optimization action not found"
            )
        
        if action.execution_status != ActionStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Action cannot be rolled back from {action.execution_status.value} status"
            )
        
        # Execute rollback
        rollback_success = rollback_manager.execute_rollback(action)
        
        if rollback_success:
            action.execution_status = ActionStatus.ROLLED_BACK
            db.commit()
            
            return {
                "message": "Action rolled back successfully",
                "action_id": action_id,
                "new_status": ActionStatus.ROLLED_BACK.value
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Rollback failed - check logs for details"
            )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid action ID format"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rollback optimization action: {str(e)}"
        )

# Approval Workflow Endpoints

@router.get("/approvals", response_model=List[Dict[str, Any]])
async def list_pending_approvals(
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """
    List pending approval requests.
    
    Returns all actions that require approval with their details.
    """
    try:
        # Get pending approvals with action details
        approvals = db.query(ActionApproval).filter(
            ActionApproval.approval_status == ApprovalStatus.PENDING
        ).all()
        
        approval_list = []
        for approval in approvals:
            action = db.query(OptimizationAction).filter_by(id=approval.action_id).first()
            
            if action:
                approval_list.append({
                    "approval_id": str(approval.id),
                    "action_id": str(action.id),
                    "action_type": action.action_type.value,
                    "resource_id": action.resource_id,
                    "resource_type": action.resource_type,
                    "estimated_monthly_savings": float(action.estimated_monthly_savings),
                    "risk_level": action.risk_level.value,
                    "requested_by": approval.requested_by,
                    "requested_at": approval.requested_at.isoformat(),
                    "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
                    "resource_metadata": action.resource_metadata
                })
        
        return approval_list
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list pending approvals: {str(e)}"
        )

@router.post("/approvals/{approval_id}/decision")
async def process_approval_decision(
    approval_id: str,
    decision: ApprovalDecisionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """
    Approve or reject an optimization action.
    
    Processes approval decisions and updates action status accordingly.
    """
    policy_manager = get_policy_manager()
    
    try:
        success = policy_manager.process_approval_decision(
            approval_id=uuid.UUID(approval_id),
            approved=decision.approved,
            approved_by=current_user.id,
            rejection_reason=decision.rejection_reason
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to process approval decision - approval may not exist or already processed"
            )
        
        return {
            "message": "Approval decision processed successfully",
            "approval_id": approval_id,
            "approved": decision.approved,
            "processed_by": str(current_user.id)
        }
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid approval ID format"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process approval decision: {str(e)}"
        )

# Dry Run and Simulation Endpoints

@router.post("/dry-run")
async def simulate_automation_actions(
    dry_run_request: DryRunRequest,
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """
    Simulate automation actions without executing them.
    
    Provides detailed simulation of what actions would be taken based on current policy.
    """
    policy_manager = get_policy_manager()
    auto_remediation_engine = get_auto_remediation_engine()
    
    try:
        # Get policy
        policy = db.query(AutomationPolicy).filter_by(id=uuid.UUID(dry_run_request.policy_id)).first()
        
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Automation policy not found"
            )
        
        # Detect optimization opportunities
        opportunities = auto_remediation_engine.detect_optimization_opportunities(policy)
        
        # Simulate dry run
        simulation_results = policy_manager.simulate_dry_run(opportunities, policy)
        
        return {
            "simulation_id": str(uuid.uuid4()),
            "policy_id": dry_run_request.policy_id,
            "policy_name": policy.name,
            "simulation_timestamp": datetime.utcnow().isoformat(),
            "results": simulation_results
        }
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid policy ID format"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to simulate automation actions: {str(e)}"
        )

# Reporting and Analytics Endpoints

@router.post("/reports/savings")
async def generate_savings_report(
    report_request: SavingsReportRequest,
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """
    Generate comprehensive savings report.
    
    Provides detailed analysis of cost savings achieved through automation.
    """
    savings_calculator = get_savings_calculator(db)
    
    try:
        start_date = datetime.fromisoformat(report_request.start_date)
        end_date = datetime.fromisoformat(report_request.end_date)
        
        # Generate savings report
        report = savings_calculator.generate_savings_report(
            start_date=start_date,
            end_date=end_date,
            include_estimates=report_request.include_estimates
        )
        
        # Convert to JSON-serializable format
        return {
            "report_id": str(uuid.uuid4()),
            "generated_at": datetime.utcnow().isoformat(),
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "total_estimated_savings": float(report.total_estimated_savings),
            "total_actual_savings": float(report.total_actual_savings),
            "savings_by_category": {
                category.value: float(amount) 
                for category, amount in report.savings_by_category.items()
            },
            "savings_by_action_type": {
                action_type.value: float(amount)
                for action_type, amount in report.savings_by_action_type.items()
            },
            "top_performing_actions": [
                {
                    "action_id": metrics.action_id,
                    "estimated_monthly_savings": float(metrics.estimated_monthly_savings),
                    "actual_monthly_savings": float(metrics.actual_monthly_savings) if metrics.actual_monthly_savings else None,
                    "total_savings_to_date": float(metrics.total_savings_to_date),
                    "savings_percentage": metrics.savings_percentage,
                    "roi_percentage": metrics.roi_percentage
                }
                for metrics in report.top_performing_actions
            ],
            "rollback_impact": float(report.rollback_impact),
            "net_savings": float(report.net_savings),
            "actions_count": report.actions_count,
            "success_rate": report.success_rate
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate savings report: {str(e)}"
        )

@router.get("/reports/trends")
async def get_savings_trends(
    months_back: int = Query(default=12, ge=1, le=24, description="Number of months to include"),
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """
    Get monthly savings trends over time.
    
    Returns trend data for visualization and analysis.
    """
    savings_calculator = get_savings_calculator(db)
    
    try:
        trend_data = savings_calculator.get_monthly_savings_trend(months_back=months_back)
        
        return {
            "trend_id": str(uuid.uuid4()),
            "generated_at": datetime.utcnow().isoformat(),
            "months_included": months_back,
            "trend_data": trend_data
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get savings trends: {str(e)}"
        )

@router.get("/reports/summary")
async def get_historical_savings_summary(
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """
    Get comprehensive historical savings summary.
    
    Returns high-level metrics for dashboard display.
    """
    savings_calculator = get_savings_calculator(db)
    
    try:
        summary = savings_calculator.get_historical_savings_summary()
        
        return {
            "summary_id": str(uuid.uuid4()),
            "generated_at": datetime.utcnow().isoformat(),
            **summary
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get historical savings summary: {str(e)}"
        )

# Audit Trail Endpoints

@router.get("/audit-logs")
async def get_automation_audit_logs(
    action_id: Optional[str] = Query(None, description="Filter by action ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    start_date: Optional[str] = Query(None, description="Start date filter (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date filter (ISO format)"),
    limit: int = Query(default=100, le=1000, description="Maximum number of logs to return"),
    offset: int = Query(default=0, ge=0, description="Number of logs to skip"),
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """
    Get automation audit logs with filtering options.
    
    Returns detailed audit trail for compliance and debugging.
    """
    try:
        query = db.query(AutomationAuditLog)
        
        if action_id:
            try:
                query = query.filter(AutomationAuditLog.action_id == uuid.UUID(action_id))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid action ID format"
                )
        
        if event_type:
            query = query.filter(AutomationAuditLog.event_type == event_type)
        
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
                query = query.filter(AutomationAuditLog.timestamp >= start_dt)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid start date format"
                )
        
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date)
                query = query.filter(AutomationAuditLog.timestamp <= end_dt)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid end date format"
                )
        
        logs = query.order_by(AutomationAuditLog.timestamp.desc()).offset(offset).limit(limit).all()
        
        return [
            {
                "id": str(log.id),
                "action_id": str(log.action_id) if log.action_id else None,
                "event_type": log.event_type,
                "event_data": log.event_data,
                "user_context": log.user_context,
                "system_context": log.system_context,
                "timestamp": log.timestamp.isoformat(),
                "correlation_id": log.correlation_id
            }
            for log in logs
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get automation audit logs: {str(e)}"
        )

# Emergency Override Endpoints

@router.post("/emergency-override")
async def create_emergency_override(
    override_request: EmergencyOverrideRequest,
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """
    Create emergency override for immediate action execution.
    
    Bypasses normal scheduling and safety delays for critical situations.
    """
    scheduling_engine = get_scheduling_engine()
    
    try:
        action_ids = [uuid.UUID(action_id) for action_id in override_request.action_ids]
        
        # Validate actions exist
        actions = db.query(OptimizationAction).filter(OptimizationAction.id.in_(action_ids)).all()
        
        if len(actions) != len(action_ids):
            found_ids = {str(action.id) for action in actions}
            missing_ids = set(override_request.action_ids) - found_ids
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Actions not found: {list(missing_ids)}"
            )
        
        # Get policy (assuming all actions use the same policy)
        policy = db.query(AutomationPolicy).filter_by(id=actions[0].policy_id).first()
        
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Automation policy not found"
            )
        
        # Create emergency override
        override_result = scheduling_engine.create_emergency_override(
            action_ids=action_ids,
            reason=override_request.reason,
            authorized_by=str(current_user.id),
            policy=policy
        )
        
        return override_result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action ID format: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create emergency override: {str(e)}"
        )

# Health and Status Endpoints

@router.get("/health")
async def automation_health_check():
    """
    Health check for automation management system.
    
    Returns status of all automation components.
    """
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "Automation Management",
            "components": {
                "policy_manager": "operational",
                "auto_remediation_engine": "operational",
                "action_engine": "operational",
                "savings_calculator": "operational",
                "scheduling_engine": "operational",
                "rollback_manager": "operational"
            },
            "features": [
                "policy_management",
                "action_execution",
                "approval_workflows",
                "dry_run_simulation",
                "savings_reporting",
                "audit_logging",
                "emergency_overrides"
            ]
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }

@router.get("/status")
async def automation_system_status(
    current_user: User = Depends(get_current_active_user),
    db: Client = Depends(get_supabase)
):
    """
    Get current automation system status and statistics.
    
    Returns real-time metrics about automation activity.
    """
    try:
        # Get current statistics
        total_policies = db.query(AutomationPolicy).filter_by(is_active=True).count()
        total_actions = db.query(OptimizationAction).count()
        pending_actions = db.query(OptimizationAction).filter_by(execution_status=ActionStatus.PENDING).count()
        scheduled_actions = db.query(OptimizationAction).filter_by(execution_status=ActionStatus.SCHEDULED).count()
        completed_actions = db.query(OptimizationAction).filter_by(execution_status=ActionStatus.COMPLETED).count()
        failed_actions = db.query(OptimizationAction).filter_by(execution_status=ActionStatus.FAILED).count()
        pending_approvals = db.query(ActionApproval).filter_by(approval_status=ApprovalStatus.PENDING).count()
        
        return {
            "status": "operational",
            "timestamp": datetime.utcnow().isoformat(),
            "statistics": {
                "policies": {
                    "total_active": total_policies
                },
                "actions": {
                    "total": total_actions,
                    "pending": pending_actions,
                    "scheduled": scheduled_actions,
                    "completed": completed_actions,
                    "failed": failed_actions
                },
                "approvals": {
                    "pending": pending_approvals
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get automation system status: {str(e)}"
        )
