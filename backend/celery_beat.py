#!/usr/bin/env python3
"""
Celery Beat Scheduler Startup Script
Starts Celery beat scheduler for periodic tasks
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
    
    # Start the beat scheduler
    celery_app.start([
        'beat',
        '--loglevel=info',
        '--schedule=/tmp/celerybeat-schedule',
        '--pidfile=/tmp/celerybeat.pid',
    ])
