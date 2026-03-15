"""
Automated Pricing Update Tasks

Celery tasks for automated pricing data synchronization across
AWS, GCP, and Azure with change detection and alerting.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from decimal import Decimal

from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from core.celery_config import celery_app
from core.database import get_async_db_session, db_config
from core.multi_cloud_repository import MultiCloudRepository
from core.models import ProviderPricing, User
from core.pricing_validator import PricingDataValidator, ValidationResult
from core.notification_service import NotificationService

logger = structlog.get_logger(__name__)

class PricingUpdateTask(Task):
    """Base class for pricing update tasks with error handling and retry logic"""
    
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3, 'countdown': 60}
    retry_backoff = True
    retry_jitter = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(
            "Pricing update task failed",
            task_id=task_id,
            exception=str(exc),
            args=args,
            kwargs=kwargs
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry"""
        logger.warning(
            "Retrying pricing update task",
            task_id=task_id,
            exception=str(exc),
            retry_count=self.request.retries
        )

    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success"""
        logger.info(
            "Pricing update task completed successfully",
            task_id=task_id,
            result=retval
        )


@celery_app.task(bind=True, base=PricingUpdateTask, name='update_aws_pricing')
def update_aws_pricing(self, regions: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Update AWS pricing data from AWS Price List API
    
    Args:
        regions: List of AWS regions to update (optional, defaults to all supported regions)
        
    Returns:
        Dict containing update results and statistics
    """
    logger.info("Starting AWS pricing update", regions=regions)
    
    try:
        # Run async function in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_update_aws_pricing_async(regions))
        loop.close()
        
        return result
        
    except Exception as e:
        logger.error("AWS pricing update failed", error=str(e))
        raise


@celery_app.task(bind=True, base=PricingUpdateTask, name='update_gcp_pricing')
def update_gcp_pricing(self, regions: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Update GCP pricing data from GCP Cloud Billing API
    
    Args:
        regions: List of GCP regions to update (optional, defaults to all supported regions)
        
    Returns:
        Dict containing update results and statistics
    """
    logger.info("Starting GCP pricing update", regions=regions)
    
    try:
        # Run async function in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_update_gcp_pricing_async(regions))
        loop.close()
        
        return result
        
    except Exception as e:
        logger.error("GCP pricing update failed", error=str(e))
        raise


@celery_app.task(bind=True, base=PricingUpdateTask, name='update_azure_pricing')
def update_azure_pricing(self, regions: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Update Azure pricing data from Azure Retail Prices API
    
    Args:
        regions: List of Azure regions to update (optional, defaults to all supported regions)
        
    Returns:
        Dict containing update results and statistics
    """
    logger.info("Starting Azure pricing update", regions=regions)
    
    try:
        # Run async function in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_update_azure_pricing_async(regions))
        loop.close()
        
        return result
        
    except Exception as e:
        logger.error("Azure pricing update failed", error=str(e))
        raise


@celery_app.task(bind=True, base=PricingUpdateTask, name='update_all_provider_pricing')
def update_all_provider_pricing(self, regions: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Update pricing data for all cloud providers (AWS, GCP, Azure)
    
    Args:
        regions: List of regions to update (optional, defaults to all supported regions)
        
    Returns:
        Dict containing update results for all providers
    """
    logger.info("Starting pricing update for all providers", regions=regions)
    
    results = {
        'aws': None,
        'gcp': None,
        'azure': None,
        'total_updated': 0,
        'total_errors': 0,
        'start_time': datetime.utcnow().isoformat(),
        'end_time': None
    }
    
    try:
        # Update AWS pricing
        try:
            results['aws'] = update_aws_pricing.apply(args=[regions]).get()
            results['total_updated'] += results['aws'].get('updated_count', 0)
        except Exception as e:
            logger.error("AWS pricing update failed in batch job", error=str(e))
            results['aws'] = {'error': str(e)}
            results['total_errors'] += 1
        
        # Update GCP pricing
        try:
            results['gcp'] = update_gcp_pricing.apply(args=[regions]).get()
            results['total_updated'] += results['gcp'].get('updated_count', 0)
        except Exception as e:
            logger.error("GCP pricing update failed in batch job", error=str(e))
            results['gcp'] = {'error': str(e)}
            results['total_errors'] += 1
        
        # Update Azure pricing
        try:
            results['azure'] = update_azure_pricing.apply(args=[regions]).get()
            results['total_updated'] += results['azure'].get('updated_count', 0)
        except Exception as e:
            logger.error("Azure pricing update failed in batch job", error=str(e))
            results['azure'] = {'error': str(e)}
            results['total_errors'] += 1
        
        results['end_time'] = datetime.utcnow().isoformat()
        
        logger.info(
            "Completed pricing update for all providers",
            total_updated=results['total_updated'],
            total_errors=results['total_errors']
        )
        
        return results
        
    except Exception as e:
        logger.error("Batch pricing update failed", error=str(e))
        results['end_time'] = datetime.utcnow().isoformat()
        results['error'] = str(e)
        raise


@celery_app.task(bind=True, base=PricingUpdateTask, name='detect_pricing_changes')
def detect_pricing_changes(self, threshold_percentage: float = 10.0) -> Dict[str, Any]:
    """
    Detect significant pricing changes and send alerts
    
    Args:
        threshold_percentage: Percentage change threshold for alerts (default: 10%)
        
    Returns:
        Dict containing detected changes and alert results
    """
    logger.info("Starting pricing change detection", threshold=threshold_percentage)
    
    try:
        # Run async function in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_detect_pricing_changes_async(threshold_percentage))
        loop.close()
        
        return result
        
    except Exception as e:
        logger.error("Pricing change detection failed", error=str(e))
        raise


@celery_app.task(bind=True, base=PricingUpdateTask, name='validate_pricing_data')
def validate_pricing_data(self, provider: Optional[str] = None) -> Dict[str, Any]:
    """
    Validate pricing data for consistency and accuracy
    
    Args:
        provider: Specific provider to validate (optional, defaults to all)
        
    Returns:
        Dict containing validation results
    """
    logger.info("Starting pricing data validation", provider=provider)
    
    try:
        # Run async function in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_validate_pricing_data_async(provider))
        loop.close()
        
        return result
        
    except Exception as e:
        logger.error("Pricing data validation failed", error=str(e))
        raise


# Async implementation functions

async def _update_aws_pricing_async(regions: Optional[List[str]] = None) -> Dict[str, Any]:
    """Async implementation of AWS pricing update"""
    
    # Default regions if not specified
    if not regions:
        regions = [
            'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
            'eu-west-1', 'eu-west-2', 'eu-central-1',
            'ap-southeast-1', 'ap-southeast-2', 'ap-northeast-1'
        ]
    
    async with get_async_db_session() as Client:
        repository = MultiCloudRepository(Client)
        validator = PricingDataValidator()
        
        updated_count = 0
        error_count = 0
        validation_errors = []
        
        # Mock AWS pricing data (in production, this would call AWS Price List API)
        aws_services = [
            {'service': 'EC2', 'category': 'compute'},
            {'service': 'RDS', 'category': 'database'},
            {'service': 'S3', 'category': 'storage'},
            {'service': 'Lambda', 'category': 'compute'},
            {'service': 'ELB', 'category': 'network'}
        ]
        
        for region in regions:
            for service_info in aws_services:
                try:
                    # Mock pricing data (replace with actual AWS API call)
                    pricing_data = {
                        'provider': 'aws',
                        'service_name': service_info['service'],
                        'service_category': service_info['category'],
                        'region': region,
                        'pricing_unit': 'hour',
                        'price_per_unit': Decimal(str(0.096 + (hash(f"{region}{service_info['service']}") % 100) / 1000)),
                        'currency': 'USD',
                        'effective_date': datetime.utcnow(),
                        'pricing_details': {
                            'instance_type': 'm5.large' if service_info['category'] == 'compute' else None,
                            'storage_type': 'gp2' if service_info['category'] == 'storage' else None
                        },
                        'last_updated': datetime.utcnow()
                    }
                    
                    # Validate pricing data
                    validation_result = validator.validate_pricing_data(pricing_data)
                    if not validation_result.is_valid:
                        validation_errors.extend(validation_result.errors)
                        error_count += 1
                        continue
                    
                    # Update pricing in database
                    await repository.update_pricing_data(
                        provider='aws',
                        service=service_info['service'],
                        region=region,
                        **pricing_data
                    )
                    
                    updated_count += 1
                    
                except Exception as e:
                    logger.error(
                        "Failed to update AWS pricing",
                        region=region,
                        service=service_info['service'],
                        error=str(e)
                    )
                    error_count += 1
        
        return {
            'provider': 'aws',
            'updated_count': updated_count,
            'error_count': error_count,
            'validation_errors': validation_errors,
            'regions_processed': len(regions),
            'services_processed': len(aws_services),
            'timestamp': datetime.utcnow().isoformat()
        }


async def _update_gcp_pricing_async(regions: Optional[List[str]] = None) -> Dict[str, Any]:
    """Async implementation of GCP pricing update"""
    
    # Default regions if not specified
    if not regions:
        regions = [
            'us-central1', 'us-east1', 'us-west1', 'us-west2',
            'europe-west1', 'europe-west2', 'europe-west3',
            'asia-southeast1', 'asia-northeast1', 'asia-east1'
        ]
    
    async with get_async_db_session() as Client:
        repository = MultiCloudRepository(Client)
        validator = PricingDataValidator()
        
        updated_count = 0
        error_count = 0
        validation_errors = []
        
        # Mock GCP pricing data (in production, this would call GCP Cloud Billing API)
        gcp_services = [
            {'service': 'Compute Engine', 'category': 'compute'},
            {'service': 'Cloud SQL', 'category': 'database'},
            {'service': 'Cloud Storage', 'category': 'storage'},
            {'service': 'Cloud Functions', 'category': 'compute'},
            {'service': 'Cloud Load Balancing', 'category': 'network'}
        ]
        
        for region in regions:
            for service_info in gcp_services:
                try:
                    # Mock pricing data (replace with actual GCP API call)
                    pricing_data = {
                        'provider': 'gcp',
                        'service_name': service_info['service'],
                        'service_category': service_info['category'],
                        'region': region,
                        'pricing_unit': 'hour',
                        'price_per_unit': Decimal(str(0.091 + (hash(f"{region}{service_info['service']}") % 100) / 1000)),
                        'currency': 'USD',
                        'effective_date': datetime.utcnow(),
                        'pricing_details': {
                            'machine_type': 'n1-standard-2' if service_info['category'] == 'compute' else None,
                            'storage_class': 'standard' if service_info['category'] == 'storage' else None
                        },
                        'last_updated': datetime.utcnow()
                    }
                    
                    # Validate pricing data
                    validation_result = validator.validate_pricing_data(pricing_data)
                    if not validation_result.is_valid:
                        validation_errors.extend(validation_result.errors)
                        error_count += 1
                        continue
                    
                    # Update pricing in database
                    await repository.update_pricing_data(
                        provider='gcp',
                        service=service_info['service'],
                        region=region,
                        **pricing_data
                    )
                    
                    updated_count += 1
                    
                except Exception as e:
                    logger.error(
                        "Failed to update GCP pricing",
                        region=region,
                        service=service_info['service'],
                        error=str(e)
                    )
                    error_count += 1
        
        return {
            'provider': 'gcp',
            'updated_count': updated_count,
            'error_count': error_count,
            'validation_errors': validation_errors,
            'regions_processed': len(regions),
            'services_processed': len(gcp_services),
            'timestamp': datetime.utcnow().isoformat()
        }


async def _update_azure_pricing_async(regions: Optional[List[str]] = None) -> Dict[str, Any]:
    """Async implementation of Azure pricing update"""
    
    # Default regions if not specified
    if not regions:
        regions = [
            'East US', 'East US 2', 'West US', 'West US 2',
            'West Europe', 'North Europe', 'UK South',
            'Southeast Asia', 'East Asia', 'Japan East'
        ]
    
    async with get_async_db_session() as Client:
        repository = MultiCloudRepository(Client)
        validator = PricingDataValidator()
        
        updated_count = 0
        error_count = 0
        validation_errors = []
        
        # Mock Azure pricing data (in production, this would call Azure Retail Prices API)
        azure_services = [
            {'service': 'Virtual Machines', 'category': 'compute'},
            {'service': 'Azure SQL Database', 'category': 'database'},
            {'service': 'Blob Storage', 'category': 'storage'},
            {'service': 'Azure Functions', 'category': 'compute'},
            {'service': 'Load Balancer', 'category': 'network'}
        ]
        
        for region in regions:
            for service_info in azure_services:
                try:
                    # Mock pricing data (replace with actual Azure API call)
                    pricing_data = {
                        'provider': 'azure',
                        'service_name': service_info['service'],
                        'service_category': service_info['category'],
                        'region': region,
                        'pricing_unit': 'hour',
                        'price_per_unit': Decimal(str(0.101 + (hash(f"{region}{service_info['service']}") % 100) / 1000)),
                        'currency': 'USD',
                        'effective_date': datetime.utcnow(),
                        'pricing_details': {
                            'vm_size': 'Standard_D2s_v3' if service_info['category'] == 'compute' else None,
                            'tier': 'Standard' if service_info['category'] == 'storage' else None
                        },
                        'last_updated': datetime.utcnow()
                    }
                    
                    # Validate pricing data
                    validation_result = validator.validate_pricing_data(pricing_data)
                    if not validation_result.is_valid:
                        validation_errors.extend(validation_result.errors)
                        error_count += 1
                        continue
                    
                    # Update pricing in database
                    await repository.update_pricing_data(
                        provider='azure',
                        service=service_info['service'],
                        region=region,
                        **pricing_data
                    )
                    
                    updated_count += 1
                    
                except Exception as e:
                    logger.error(
                        "Failed to update Azure pricing",
                        region=region,
                        service=service_info['service'],
                        error=str(e)
                    )
                    error_count += 1
        
        return {
            'provider': 'azure',
            'updated_count': updated_count,
            'error_count': error_count,
            'validation_errors': validation_errors,
            'regions_processed': len(regions),
            'services_processed': len(azure_services),
            'timestamp': datetime.utcnow().isoformat()
        }


async def _detect_pricing_changes_async(threshold_percentage: float) -> Dict[str, Any]:
    """Async implementation of pricing change detection"""
    
    async with get_async_db_session() as Client:
        repository = MultiCloudRepository(Client)
        notification_service = NotificationService()
        
        changes_detected = []
        alerts_sent = 0
        
        # Get pricing data from last 48 hours for comparison
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(hours=48)
        
        providers = ['aws', 'gcp', 'azure']
        
        for provider in providers:
            try:
                # Get recent pricing history
                pricing_history = await repository.get_pricing_history(
                    provider=provider,
                    service='',  # All services
                    days=2
                )
                
                # Group by service and region
                service_pricing = {}
                for pricing in pricing_history:
                    key = f"{pricing.service_name}_{pricing.region}"
                    if key not in service_pricing:
                        service_pricing[key] = []
                    service_pricing[key].append(pricing)
                
                # Detect significant changes
                for service_key, pricing_list in service_pricing.items():
                    if len(pricing_list) < 2:
                        continue
                    
                    # Sort by date
                    pricing_list.sort(key=lambda x: x.effective_date)
                    
                    # Compare latest with previous
                    latest = pricing_list[-1]
                    previous = pricing_list[-2]
                    
                    if previous.price_per_unit > 0:
                        change_percentage = abs(
                            (latest.price_per_unit - previous.price_per_unit) / previous.price_per_unit * 100
                        )
                        
                        if change_percentage >= threshold_percentage:
                            change_info = {
                                'provider': provider,
                                'service': latest.service_name,
                                'region': latest.region,
                                'previous_price': float(previous.price_per_unit),
                                'current_price': float(latest.price_per_unit),
                                'change_percentage': float(change_percentage),
                                'change_direction': 'increase' if latest.price_per_unit > previous.price_per_unit else 'decrease',
                                'detected_at': datetime.utcnow().isoformat()
                            }
                            
                            changes_detected.append(change_info)
                            
                            # Send alert notification
                            try:
                                await notification_service.send_pricing_change_alert(change_info)
                                alerts_sent += 1
                            except Exception as e:
                                logger.error(
                                    "Failed to send pricing change alert",
                                    change_info=change_info,
                                    error=str(e)
                                )
                
            except Exception as e:
                logger.error(
                    "Failed to detect pricing changes for provider",
                    provider=provider,
                    error=str(e)
                )
        
        return {
            'changes_detected': len(changes_detected),
            'alerts_sent': alerts_sent,
            'threshold_percentage': threshold_percentage,
            'changes': changes_detected,
            'timestamp': datetime.utcnow().isoformat()
        }


async def _validate_pricing_data_async(provider: Optional[str] = None) -> Dict[str, Any]:
    """Async implementation of pricing data validation"""
    
    async with get_async_db_session() as Client:
        repository = MultiCloudRepository(Client)
        validator = PricingDataValidator()
        
        validation_results = {
            'total_records': 0,
            'valid_records': 0,
            'invalid_records': 0,
            'anomalies_detected': 0,
            'errors': [],
            'anomalies': [],
            'timestamp': datetime.utcnow().isoformat()
        }
        
        providers_to_check = [provider] if provider else ['aws', 'gcp', 'azure']
        
        for prov in providers_to_check:
            try:
                # Get current pricing data for provider
                current_pricing = await repository.get_current_pricing(
                    provider=prov,
                    region='',  # All regions
                    service_category=None  # All categories
                )
                
                for pricing in current_pricing:
                    validation_results['total_records'] += 1
                    
                    # Validate individual pricing record
                    pricing_dict = {
                        'provider': pricing.provider,
                        'service_name': pricing.service_name,
                        'service_category': pricing.service_category,
                        'region': pricing.region,
                        'pricing_unit': pricing.pricing_unit,
                        'price_per_unit': pricing.price_per_unit,
                        'currency': pricing.currency,
                        'effective_date': pricing.effective_date
                    }
                    
                    validation_result = validator.validate_pricing_data(pricing_dict)
                    
                    if validation_result.is_valid:
                        validation_results['valid_records'] += 1
                    else:
                        validation_results['invalid_records'] += 1
                        validation_results['errors'].extend(validation_result.errors)
                    
                    # Check for anomalies
                    historical_data = await repository.get_pricing_history(
                        provider=prov,
                        service=pricing.service_name,
                        days=30
                    )
                    
                    anomalies = validator.detect_anomalies(pricing_dict, [
                        {
                            'provider': h.provider,
                            'service_name': h.service_name,
                            'price_per_unit': h.price_per_unit,
                            'effective_date': h.effective_date
                        } for h in historical_data
                    ])
                    
                    if anomalies:
                        validation_results['anomalies_detected'] += len(anomalies)
                        validation_results['anomalies'].extend(anomalies)
                
            except Exception as e:
                logger.error(
                    "Failed to validate pricing data for provider",
                    provider=prov,
                    error=str(e)
                )
                validation_results['errors'].append({
                    'provider': prov,
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                })
        
        return validation_results

