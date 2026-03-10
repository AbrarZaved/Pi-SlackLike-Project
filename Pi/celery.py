"""
Celery Configuration for Pi Project
====================================

This module contains the Celery application configuration.
Celery is used for handling asynchronous tasks and periodic tasks.

Usage:
    # Start Celery worker
    celery -A Pi worker -l info
    
    # Start Celery beat (for periodic tasks)
    celery -A Pi beat -l info
    
    # Start both worker and beat
    celery -A Pi worker -B -l info
"""

import os
from pathlib import Path
from celery import Celery
from celery.signals import setup_logging

# Set default Django settings module for Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Pi.settings')

# Load environment variables from .env file
import environ
BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / '.env')

# Create Celery app
app = Celery('Pi')

# Load config from Django settings with CELERY namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps (looks for tasks.py)
app.autodiscover_tasks()


@setup_logging.connect
def config_loggers(*args, **kwargs):
    """Configure logging for Celery."""
    import logging
    from logging.config import dictConfig
    
    # Configure logging to output to stdout (which PM2 captures)
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
            'simple': {
                'format': '[%(levelname)s] %(message)s',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'INFO',
                'formatter': 'verbose',
                'stream': 'ext://sys.stdout',
            },
        },
        'root': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'loggers': {
            'celery': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False,
            },
            'authentication': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False,
            },
        },
    }
    
    dictConfig(logging_config)
