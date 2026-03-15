"""
Celery Configuration for FinOps Platform
"""

import os
from celery import Celery
from celery.schedules import crontab
from kombu import Queue

def create_celery_app() -> Celery:
    """Create and configure Celery application"""
    
    # Get configuration from environment
    # Use memory or filesystem for broker and result backend (Not Redis)
    broker_url = os.getenv('CELERY_BROKER_URL', 'memory://')
    result_backend = os.getenv('CELERY_RESULT_BACKEND', 'cache+memory://')
    
    # Create Celery app
    celery_app = Celery('finops_platform')
    
    # Basic configuration
    celery_app.conf.update(
        # Broker settings
        broker_url=broker_url,
        result_backend=result_backend,
        
        # Serialization
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        
        # Timezone
        timezone='UTC',
        enable_utc=True,
        
        # Task execution
        task_track_started=True,
        task_time_limit=30 * 60,  # 30 minutes
        task_soft_time_limit=25 * 60,  # 25 minutes
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        
        # Performance
        worker_disable_rate_limits=False,
        task_compression='gzip',
        result_compression='gzip',
        
        # Result backend settings
        result_expires=3600,  # 1 hour
        result_persistent=True,
        
        # Worker settings
        worker_max_tasks_per_child=1000,
        worker_max_memory_per_child=200000,  # 200MB
        
        # Queue configuration
        task_routes={
            'core.tasks.sync_provider_cost_data': {'queue': 'cost_sync'},
            'core.tasks.sync_all_providers_cost_data': {'queue': 'cost_sync'},
            'core.tasks.discover_provider_resources': {'queue': 'resource_discovery'},
            'core.tasks.discover_all_resources': {'queue': 'resource_discovery'},
            'core.tasks.monitor_budget': {'queue': 'monitoring'},
            'core.tasks.monitor_all_budgets': {'queue': 'monitoring'},
            'core.tasks.analyze_optimization_opportunities': {'queue': 'analysis'},
            'core.tasks.detect_cost_anomalies': {'queue': 'analysis'},
            'core.tasks.cleanup_old_data': {'queue': 'maintenance'},
            # Multi-cloud pricing update tasks
            'tasks.pricing_update_tasks.update_aws_pricing': {'queue': 'pricing_updates'},
            'tasks.pricing_update_tasks.update_gcp_pricing': {'queue': 'pricing_updates'},
            'tasks.pricing_update_tasks.update_azure_pricing': {'queue': 'pricing_updates'},
            'tasks.pricing_update_tasks.update_all_provider_pricing': {'queue': 'pricing_updates'},
            'tasks.pricing_update_tasks.detect_pricing_changes': {'queue': 'pricing_analysis'},
            'tasks.pricing_update_tasks.validate_pricing_data': {'queue': 'pricing_analysis'},
        },
        
        # Define queues
        task_default_queue='default',
        task_queues=(
            Queue('default', routing_key='default'),
            Queue('cost_sync', routing_key='cost_sync'),
            Queue('resource_discovery', routing_key='resource_discovery'),
            Queue('monitoring', routing_key='monitoring'),
            Queue('analysis', routing_key='analysis'),
            Queue('maintenance', routing_key='maintenance'),
            Queue('pricing_updates', routing_key='pricing_updates'),
            Queue('pricing_analysis', routing_key='pricing_analysis'),
        ),
        
        # Beat schedule for periodic tasks
        beat_schedule={
            # Sync cost data every 6 hours
            'sync-cost-data': {
                'task': 'core.tasks.sync_all_providers_cost_data',
                'schedule': 6 * 60 * 60,  # 6 hours in seconds
                'options': {'queue': 'cost_sync'}
            },
            
            # Monitor budgets every hour
            'monitor-budgets': {
                'task': 'core.tasks.monitor_all_budgets',
                'schedule': 60 * 60,  # 1 hour in seconds
                'options': {'queue': 'monitoring'}
            },
            
            # Discover resources daily at 2 AM UTC
            'discover-resources': {
                'task': 'core.tasks.discover_all_resources',
                'schedule': 24 * 60 * 60,  # Daily
                'options': {'queue': 'resource_discovery'}
            },
            
            # Generate optimization recommendations daily at 3 AM UTC
            'optimization-analysis': {
                'task': 'core.tasks.analyze_optimization_opportunities',
                'schedule': 24 * 60 * 60,  # Daily
                'options': {'queue': 'analysis'}
            },
            
            # Detect anomalies every 4 hours
            'anomaly-detection': {
                'task': 'core.tasks.detect_cost_anomalies',
                'schedule': 4 * 60 * 60,  # 4 hours in seconds
                'options': {'queue': 'analysis'}
            },
            
            # Cleanup old data weekly (every 7 days)
            'cleanup-old-data': {
                'task': 'core.tasks.cleanup_old_data',
                'schedule': 7 * 24 * 60 * 60,  # Weekly
                'options': {'queue': 'maintenance'}
            },
            
            # Multi-cloud pricing update tasks
            # Update all provider pricing daily at 1 AM UTC
            'update-all-pricing': {
                'task': 'tasks.pricing_update_tasks.update_all_provider_pricing',
                'schedule': 24 * 60 * 60,  # Daily
                'options': {'queue': 'pricing_updates'}
            },
            
            # Detect pricing changes every 6 hours
            'detect-pricing-changes': {
                'task': 'tasks.pricing_update_tasks.detect_pricing_changes',
                'schedule': 6 * 60 * 60,  # 6 hours in seconds
                'options': {'queue': 'pricing_analysis'}
            },
            
            # Validate pricing data daily at 4 AM UTC
            'validate-pricing-data': {
                'task': 'tasks.pricing_update_tasks.validate_pricing_data',
                'schedule': 24 * 60 * 60,  # Daily
                'options': {'queue': 'pricing_analysis'}
            },
        },
        
        # Error handling
        task_reject_on_worker_lost=True,
        task_ignore_result=False,
        
        # Security
        worker_hijack_root_logger=False,
        worker_log_color=False,
    )
    

    # Schedule
    celery_app.conf.beat_schedule = {
        "collect-aws-metrics-every-6-hours": {
            "task": "app.workers.aws_tasks.collect_aws_metrics",
            "schedule": crontab(minute=0, hour='*/6'),
        },
        "run-resource-optimizer-every-6-hours": {
            "task": "app.workers.aws_tasks.run_resource_optimizer",
            "schedule": crontab(minute=30, hour='*/6'),
        },
    }

    return celery_app

# Create the Celery app instance
celery_app = create_celery_app()

# Auto-discover tasks
celery_app.autodiscover_tasks(['core', 'tasks'])

if __name__ == '__main__':
    celery_app.start()
