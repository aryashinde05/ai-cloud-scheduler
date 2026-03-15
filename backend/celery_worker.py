#!/usr/bin/env python3
"""
Celery Worker Startup Script
Starts Celery worker with proper configuration for FinOps Platform
"""

import os
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from core.celery_config import celery_app

if __name__ == '__main__':
    # Set environment variables if not already set
    os.environ.setdefault('CELERY_BROKER_URL', 'memory://')
    os.environ.setdefault('CELERY_RESULT_BACKEND', 'cache+memory://')
    
    # Start the worker
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=4',
        '--queues=default,cost_sync,resource_discovery,monitoring,analysis,maintenance',
        '--hostname=worker@%h',
        '--max-tasks-per-child=1000',
        '--max-memory-per-child=200000',  # 200MB
    ])
