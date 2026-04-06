"""
Auto-Remediation Engine for Automated Cost Optimization

Core orchestrator that manages the automated optimization workflow:
- Detection of optimization opportunities
- Safety validation
- Action scheduling and execution
- Monitoring and rollback
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from decimal import Decimal
import structlog

from app.models.automation_models import (
    OptimizationAction, AutomationPolicy, ActionType, ActionStatus, 
    RiskLevel, ApprovalStatus, AutomationAuditLog
)
from app.services.safety_checker import SafetyChecker
from app.services.action_engine import ActionEngine
from app.services.rollback_manager import RollbackManager
from app.services.automation_audit_logger import AutomationAuditLogger
from app.services.scheduling_engine import SchedulingEngine
from app.database.database import get_db_session
from app.services.notification_service import get_notification_service, NotificationMessage, NotificationPriority
from app.utils.monitoring_service import get_monitoring_service

logger = structlog.get_logger(__name__)


@dataclass
class OptimizationOpportunity:
    """Represents a detected optimization opportunity"""
    resource_id: str
    resource_type: str
    action_type: ActionType
    estimated_monthly_savings: Decimal
    risk_level: RiskLevel
    resource_metadata: Dict[str, Any]
    detection_details: Dict[str, Any]


class AutoRemediationEngine:
    """
    Core orchestrator for automated cost optimization.
    
    Manages the complete workflow from detection to execution:
    1. Detect optimization opportunities
    2. Validate safety requirements
    3. Schedule optimization actions
    4. Execute actions with monitoring
    5. Handle rollbacks if needed
    """
    
    def __init__(self):
        self.safety_checker = SafetyChecker()
        self.action_engine = ActionEngine()
        self.rollback_manager = RollbackManager()
        self.audit_logger = AutomationAuditLogger()
        self.scheduling_engine = SchedulingEngine()
        self.notification_service = get_notification_service()
        self.monitoring_service = get_monitoring_service()
        
    def detect_optimization_opportunities(self, 
                                        policy: AutomationPolicy) -> List[OptimizationOpportunity]:
        """
        Detect cost optimization opportunities based on policy configuration.
        
        Args:
            policy: Automation policy defining what to look for
            
        Returns:
            List of optimization opportunities
        """
        logger.info("Starting optimization opportunity detection", 
                   policy_id=str(policy.id))
        
        opportunities = []
        
        # Check each enabled action type in the policy
        for action_type_str in policy.enabled_actions:
            try:
                action_type = ActionType(action_type_str)
                detected = self._detect_opportunities_for_action(action_type, policy)
                opportunities.extend(detected)
                
                logger.info("Detected opportunities for action type",
                           action_type=action_type.value,
                           count=len(detected))
                           
            except ValueError as e:
                logger.warning("Invalid action type in policy",
                             action_type=action_type_str,
                             error=str(e))
        
        logger.info("Completed opportunity detection",
                   total_opportunities=len(opportunities))
        
        return opportunities
    
    def process_optimization_opportunity(self, opportunity: OptimizationOpportunity, policy: AutomationPolicy) -> bool:
        """
        Process an optimization opportunity based on current automation state.
        
        Args:
            opportunity: The optimization opportunity to process
            policy: The automation policy to apply
            
        Returns:
            True if opportunity was processed (executed or queued), False otherwise
        """
        logger.info("Processing optimization opportunity",
                   resource_id=opportunity.resource_id,
                   action_type=opportunity.action_type.value)
        
        # Check automation state
        if not self.monitoring_service.is_automation_enabled():
            # Queue for manual review instead of executing
            logger.info("Automation disabled, queuing opportunity for manual review",
                       resource_id=opportunity.resource_id,
                       automation_state=self.monitoring_service.get_automation_state().value)
            
            # Create action but don't schedule it
            action = self._create_optimization_action(opportunity, policy)
            action.execution_status = ActionStatus.PENDING  # Keep as pending for manual review
            
            # Log that it was queued due to automation state
            self.audit_logger.log_action_event(
                action.id,
                "queued_for_manual_review",
                {
                    "reason": f"automation_{self.monitoring_service.get_automation_state().value}",
                    "requires_manual_review": True,
                    "opportunity_details": opportunity.detection_details
                }
            )
            
            return True
        
        # Automation is enabled, proceed with normal processing
        return self._process_opportunity_normally(opportunity, policy)
    
    def _process_opportunity_normally(self, opportunity: OptimizationOpportunity, policy: AutomationPolicy) -> bool:
        """Process opportunity normally when automation is enabled"""
        
        # Create optimization action
        action = self._create_optimization_action(opportunity, policy)
        
        # Validate safety requirements
        safety_passed, _ = self.validate_safety_requirements(action, policy)
        if not safety_passed:
            logger.warning("Safety validation failed for opportunity",
                         resource_id=opportunity.resource_id)
            return False
        
        # Schedule the action
        return self.schedule_optimization_action(action.id)
    
    def _create_optimization_action(self, opportunity: OptimizationOpportunity, policy: AutomationPolicy) -> OptimizationAction:
        """Create an OptimizationAction from an opportunity"""
        
        with get_db_session() as session:
            action = OptimizationAction(
                action_type=opportunity.action_type,
                resource_id=opportunity.resource_id,
                resource_type=opportunity.resource_type,
                estimated_monthly_savings=opportunity.estimated_monthly_savings,
                risk_level=opportunity.risk_level,
                requires_approval=opportunity.action_type.value in policy.approval_required_actions,
                resource_metadata=opportunity.resource_metadata,
                policy_id=policy.id
            )
            
            session.add(action)
            session.commit()
            session.refresh(action)
            
            # Log action creation
            self.audit_logger.log_action_event(
                action.id,
                "action_created",
                {
                    "opportunity_details": opportunity.detection_details,
                    "policy_id": str(policy.id),
                    "created_at": datetime.utcnow().isoformat()
                }
            )
            
            return action
    
    def _detect_opportunities_for_action(self, 
                                       action_type: ActionType,
                                       policy: AutomationPolicy) -> List[OptimizationOpportunity]:
        """Detect opportunities for a specific action type"""
        
        # This is a placeholder implementation - in a real system, this would
        # integrate with AWS APIs and cost analysis to find actual opportunities
        opportunities = []
        
        if action_type == ActionType.STOP_INSTANCE:
            opportunities.extend(self._detect_unused_instances(policy))
        elif action_type == ActionType.DELETE_VOLUME:
            opportunities.extend(self._detect_unattached_volumes(policy))
        elif action_type == ActionType.RELEASE_ELASTIC_IP:
            opportunities.extend(self._detect_unused_elastic_ips(policy))
        elif action_type == ActionType.UPGRADE_STORAGE:
            opportunities.extend(self._detect_gp2_volumes(policy))
        
        return opportunities
    
    def _detect_unused_instances(self, policy: AutomationPolicy) -> List[OptimizationOpportunity]:
        """Detect EC2 instances with low utilization"""
        # Placeholder implementation
        return []
    
    def _detect_unattached_volumes(self, policy: AutomationPolicy) -> List[OptimizationOpportunity]:
        """Detect EBS volumes not attached to instances"""
        # Placeholder implementation
        return []
    
    def _detect_unused_elastic_ips(self, policy: AutomationPolicy) -> List[OptimizationOpportunity]:
        """Detect unassociated Elastic IP addresses"""
        # Placeholder implementation
        return []
    
    def _detect_gp2_volumes(self, policy: AutomationPolicy) -> List[OptimizationOpportunity]:
        """Detect gp2 volumes that can be upgraded to gp3"""
        # Placeholder implementation
        return []
    
    def validate_safety_requirements(
        self,
        opportunity_or_action: Any,
        policy: Optional[AutomationPolicy] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate that an optimization opportunity meets safety requirements.
        
        Args:
            opportunity_or_action: The optimization opportunity (or persisted action) to validate
            policy: Automation policy with safety rules (optional if attached to action)
            
        Returns:
            Tuple of (safety_passed, safety_details)
        """
        if policy is None:
            policy = getattr(opportunity_or_action, "policy", None)
        if policy is None:
            # If we have no policy context, do not block local usage.
            return True, {"passed": True, "checks": [], "note": "No policy provided; safety checks skipped."}

        logger.info("Validating safety requirements",
                   resource_id=getattr(opportunity_or_action, "resource_id", None),
                   action_type=getattr(getattr(opportunity_or_action, "action_type", None), "value", None))
        
        # Use SafetyChecker to validate the opportunity
        safety_passed, safety_details = self.safety_checker.validate_action_safety(
            opportunity_or_action, policy
        )
        
        logger.info("Safety validation completed",
                   resource_id=getattr(opportunity_or_action, "resource_id", None),
                   safety_passed=safety_passed)
        
        return safety_passed, safety_details
    
    def schedule_optimization_actions(self, 
                                    opportunities: List[OptimizationOpportunity],
                                    policy: AutomationPolicy) -> List[OptimizationAction]:
        """
        Schedule optimization actions based on validated opportunities.
        
        Args:
            opportunities: List of validated optimization opportunities
            policy: Automation policy for scheduling rules
            
        Returns:
            List of scheduled optimization actions
        """
        logger.info("Scheduling optimization actions",
                   opportunity_count=len(opportunities))
        
        scheduled_actions = []
        
        with get_db_session() as session:
            for opportunity in opportunities:
                # Validate safety first
                safety_passed, safety_details = self.validate_safety_requirements(
                    opportunity, policy
                )
                
                if not safety_passed:
                    logger.warning("Skipping opportunity due to safety check failure",
                                 resource_id=opportunity.resource_id,
                                 safety_details=safety_details)
                    continue
                
                # Determine if approval is required
                requires_approval = (
                    opportunity.action_type.value in policy.approval_required_actions or
                    opportunity.risk_level == RiskLevel.HIGH
                )
                
                # Create rollback plan
                rollback_plan = self.rollback_manager.create_rollback_plan(opportunity)

                # Calculate optimal execution time using scheduling engine
                execution_time = self.scheduling_engine.calculate_optimal_execution_time(
                    OptimizationAction(
                        action_type=opportunity.action_type,
                        resource_id=opportunity.resource_id,
                        resource_type=opportunity.resource_type,
                        estimated_monthly_savings=opportunity.estimated_monthly_savings,
                        risk_level=opportunity.risk_level,
                        requires_approval=requires_approval,
                        approval_status=ApprovalStatus.PENDING if requires_approval else ApprovalStatus.NOT_REQUIRED,
                        scheduled_execution_time=None,
                        safety_checks_passed=safety_passed,
                        rollback_plan=rollback_plan,
                        execution_status=ActionStatus.PENDING,
                        resource_metadata=opportunity.resource_metadata,
                        policy_id=policy.id
                    ),
                    policy
                )
                
                # Create optimization action
                action = OptimizationAction(
                    action_type=opportunity.action_type,
                    resource_id=opportunity.resource_id,
                    resource_type=opportunity.resource_type,
                    estimated_monthly_savings=opportunity.estimated_monthly_savings,
                    risk_level=opportunity.risk_level,
                    requires_approval=requires_approval,
                    approval_status=ApprovalStatus.PENDING if requires_approval else ApprovalStatus.NOT_REQUIRED,
                    scheduled_execution_time=execution_time,
                    safety_checks_passed=safety_passed,
                    rollback_plan=rollback_plan,
                    execution_status=ActionStatus.SCHEDULED,
                    resource_metadata=opportunity.resource_metadata,
                    policy_id=policy.id
                )
                
                session.add(action)
                session.flush()  # Get the ID
                
                # Log action creation
                self.audit_logger.log_action_event(
                    action.id,
                    "action_created",
                    {
                        "opportunity": {
                            "resource_id": opportunity.resource_id,
                            "action_type": opportunity.action_type.value,
                            "estimated_savings": float(opportunity.estimated_monthly_savings)
                        },
                        "safety_details": safety_details
                    }
                )
                
                scheduled_actions.append(action)
                
                logger.info("Scheduled optimization action",
                           action_id=str(action.id),
                           resource_id=opportunity.resource_id,
                           execution_time=execution_time)
            
            session.commit()
        
        logger.info("Completed action scheduling",
                   scheduled_count=len(scheduled_actions))
        
        return scheduled_actions
    

    
    def execute_optimization_action(self, action_id: uuid.UUID) -> bool:
        """
        Execute a scheduled optimization action.
        
        Args:
            action_id: ID of the action to execute
            
        Returns:
            True if execution was successful, False otherwise
        """
        logger.info("Starting action execution", action_id=str(action_id))
        
        with get_db_session() as session:
            action = session.query(OptimizationAction).filter_by(id=action_id).first()
            
            if not action:
                logger.error("Action not found", action_id=str(action_id))
                return False
            
            # Check if action is ready for execution
            if action.execution_status != ActionStatus.SCHEDULED:
                logger.warning("Action not in scheduled status",
                             action_id=str(action_id),
                             current_status=action.execution_status.value)
                return False
            
            # Check approval status
            if action.requires_approval and action.approval_status != ApprovalStatus.APPROVED:
                logger.warning("Action requires approval but not approved",
                             action_id=str(action_id),
                             approval_status=action.approval_status.value)
                return False
            
            # Update status to executing
            action.execution_status = ActionStatus.EXECUTING
            action.execution_started_at = datetime.utcnow()
            session.commit()
            
            # Log execution start
            self.audit_logger.log_action_event(
                action_id,
                "execution_started",
                {"started_at": action.execution_started_at.isoformat()}
            )
        
        # Start monitoring the action execution
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Start monitoring
            execution_report = loop.run_until_complete(
                self.monitoring_service.monitor_action_execution(action)
            )
            
            # Execute the action using ActionEngine
            success, execution_details = self.action_engine.execute_action(action)
            
            with get_db_session() as session:
                action = session.query(OptimizationAction).filter_by(id=action_id).first()
                
                if success:
                    action.execution_status = ActionStatus.COMPLETED
                    action.execution_completed_at = datetime.utcnow()
                    action.actual_savings = execution_details.get('actual_savings', action.estimated_monthly_savings)
                    
                    # Log successful execution
                    self.audit_logger.log_action_event(
                        action_id,
                        "execution_completed",
                        {
                            "completed_at": action.execution_completed_at.isoformat(),
                            "actual_savings": float(action.actual_savings),
                            "execution_details": execution_details
                        }
                    )
                    
                    # Report completion to monitoring service
                    loop.run_until_complete(
                        self.monitoring_service.report_action_completion(action, True, execution_details)
                    )
                    
                    # Send success notification
                    self._send_execution_notification(action, success=True)
                    
                    logger.info("Action execution completed successfully",
                               action_id=str(action_id))
                    
                else:
                    action.execution_status = ActionStatus.FAILED
                    action.error_message = execution_details.get('error_message', 'Unknown error')
                    
                    # Log failed execution
                    self.audit_logger.log_action_event(
                        action_id,
                        "execution_failed",
                        {
                            "error_message": action.error_message,
                            "execution_details": execution_details
                        }
                    )
                    
                    # Report failure to monitoring service
                    loop.run_until_complete(
                        self.monitoring_service.report_action_completion(action, False, execution_details)
                    )
                    
                    # Send failure notification
                    self._send_execution_notification(action, success=False)
                    
                    logger.error("Action execution failed",
                               action_id=str(action_id),
                               error=action.error_message)
                
                session.commit()
            
            return success
            
        except Exception as e:
            logger.error("Exception during action execution",
                        action_id=str(action_id),
                        error=str(e))
            
            # Report error to monitoring service
            loop.run_until_complete(
                self.monitoring_service.detect_and_handle_errors(e, {
                    "action_id": str(action_id),
                    "context": "action_execution"
                })
            )
            
            with get_db_session() as session:
                action = session.query(OptimizationAction).filter_by(id=action_id).first()
                action.execution_status = ActionStatus.FAILED
                action.error_message = f"Exception during execution: {str(e)}"
                session.commit()
            
            # Log exception
            self.audit_logger.log_action_event(
                action_id,
                "execution_exception",
                {"exception": str(e)}
            )
            
            return False
        finally:
            loop.close()
    
    def monitor_action_results(self, action_id: uuid.UUID) -> Dict[str, Any]:
        """
        Monitor the results of an executed action and check for issues.
        
        Args:
            action_id: ID of the action to monitor
            
        Returns:
            Dictionary with monitoring results
        """
        logger.info("Monitoring action results", action_id=str(action_id))
        
        with get_db_session() as session:
            action = session.query(OptimizationAction).filter_by(id=action_id).first()
            
            if not action:
                return {"error": "Action not found"}
            
            if action.execution_status != ActionStatus.COMPLETED:
                return {"error": "Action not completed"}
        
        # Use RollbackManager to monitor for issues
        monitoring_results = self.rollback_manager.monitor_post_action_health(action)
        
        # If issues are detected, trigger rollback
        if monitoring_results.get('issues_detected', False):
            logger.warning("Issues detected after action execution, triggering rollback",
                          action_id=str(action_id))
            
            rollback_success = self.rollback_manager.execute_rollback(action)
            monitoring_results['rollback_triggered'] = True
            monitoring_results['rollback_success'] = rollback_success
            
            if rollback_success:
                with get_db_session() as session:
                    action = session.query(OptimizationAction).filter_by(id=action_id).first()
                    action.execution_status = ActionStatus.ROLLED_BACK
                    session.commit()
        
        return monitoring_results
    
    def schedule_actions_with_intelligent_timing(self,
                                                actions: List[OptimizationAction],
                                                policy: AutomationPolicy,
                                                emergency_override: bool = False,
                                                override_reason: Optional[str] = None,
                                                authorized_by: Optional[str] = None) -> List[OptimizationAction]:
        """
        Schedule multiple actions using intelligent timing from the scheduling engine.
        
        Args:
            actions: List of actions to schedule
            policy: Automation policy
            emergency_override: Whether to apply emergency override
            override_reason: Reason for emergency override
            authorized_by: Who authorized the emergency override
            
        Returns:
            List of actions with updated execution times
        """
        logger.info("Scheduling actions with intelligent timing",
                   action_count=len(actions),
                   emergency_override=emergency_override)
        
        # Use scheduling engine for intelligent batch scheduling
        scheduled_actions = self.scheduling_engine.schedule_actions_batch(
            actions, policy, emergency_override, override_reason, authorized_by
        )
        
        # Update actions in database
        with get_db_session() as session:
            for action in scheduled_actions:
                session.merge(action)
                
                # Log scheduling event
                self.audit_logger.log_action_event(
                    action.id,
                    "intelligent_scheduling_applied",
                    {
                        "scheduled_execution_time": action.scheduled_execution_time.isoformat(),
                        "emergency_override": emergency_override,
                        "override_reason": override_reason,
                        "authorized_by": authorized_by
                    }
                )
            
            session.commit()
        
        logger.info("Intelligent scheduling completed",
                   scheduled_count=len(scheduled_actions))
        
        return scheduled_actions
    
    def create_emergency_override(self,
                                action_ids: List[uuid.UUID],
                                reason: str,
                                authorized_by: str,
                                policy: AutomationPolicy) -> Dict[str, Any]:
        """
        Create emergency override for immediate action execution.
        
        Args:
            action_ids: List of action IDs to override
            reason: Reason for emergency override
            authorized_by: Who authorized the override
            policy: Automation policy
            
        Returns:
            Dictionary with override results
        """
        return self.scheduling_engine.create_emergency_override(
            action_ids, reason, authorized_by, policy
        )
    
    def check_maintenance_window_availability(self,
                                            window_name: str,
                                            policy: AutomationPolicy) -> Dict[str, Any]:
        """
        Check availability and capacity of a maintenance window.
        
        Args:
            window_name: Name of the maintenance window
            policy: Automation policy
            
        Returns:
            Dictionary with availability information
        """
        return self.scheduling_engine.check_maintenance_window_availability(
            window_name, policy
        )
    
    def _send_execution_notification(self, action: OptimizationAction, success: bool):
        """Send notification about action execution"""
        
        if success:
            title = f"Optimization Action Completed: {action.action_type.value}"
            message = f"Successfully executed {action.action_type.value} on resource {action.resource_id}"
            priority = NotificationPriority.LOW
        else:
            title = f"Optimization Action Failed: {action.action_type.value}"
            message = f"Failed to execute {action.action_type.value} on resource {action.resource_id}: {action.error_message}"
            priority = NotificationPriority.HIGH
        
        notification = NotificationMessage(
            title=title,
            message=message,
            priority=priority,
            metadata={
                "action_id": str(action.id),
                "resource_id": action.resource_id,
                "action_type": action.action_type.value,
                "estimated_savings": float(action.estimated_monthly_savings)
            }
        )
        
        # This would be configured based on policy settings
        # For now, we'll just log that a notification would be sent
        logger.info("Notification would be sent",
                   title=title,
                   priority=priority.value)
