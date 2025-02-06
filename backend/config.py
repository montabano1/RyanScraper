# config.py
import os
from pathlib import Path
from datetime import datetime
from pytz import timezone

# Base directory of the project
BASE_DIR = Path(__file__).parent.parent

# Data storage configuration
DATA_DIR = BASE_DIR / 'data'
RESULTS_DIR = DATA_DIR / 'results'
LOGS_DIR = BASE_DIR / 'logs'

# Ensure directories exist
for directory in [DATA_DIR, RESULTS_DIR, LOGS_DIR]:
    directory.mkdir(exist_ok=True)

# Scraper configurations
SCRAPERS = {
    'cbre': {
        'name': 'CBRE Properties',
        'class': 'scrapers.cbre.CbreScraper',
        'schedule': '0 0 * * *',  # Run at midnight every day
        'enabled': True
    },
    'cushman': {
        'name': 'Cushman & Wakefield Properties',
        'class': 'scrapers.cushman.CushmanScraper',
        'schedule': '0 0 * * *',  # Run at midnight every day
        'enabled': True
    },
    'jll': {
        'name': 'JLL Properties',
        'class': 'scrapers.jll.JLLScraper',
        'schedule': '0 0 * * *',  # Run at midnight every day
        'enabled': True
    },
    'landpark': {
        'name': 'LandPark Properties',
        'class': 'scrapers.landpark.LandParkScraper',
        'schedule': '0 0 * * *',  # Run at midnight every day
        'enabled': True
    },
    'lee': {
        'name': 'Lee & Associates Properties',
        'class': 'scrapers.lee.LeeScraper',
        'schedule': '0 0 * * *',  # Run at midnight every day
        'enabled': True
    },
    'lincoln': {
        'name': 'Lincoln Property Company',
        'class': 'scrapers.lincoln.LincolnScraper',
        'schedule': '0 0 * * *',  # Run at midnight every day
        'enabled': True
    },
    'trinity': {
        'name': 'Trinity Partners Properties',
        'class': 'scrapers.trinity.TrinityScraper',
        'schedule': '0 0 * * *',  # Run at midnight every day
        'enabled': True
    }
}

# Scheduler configuration
SCHEDULER_CONFIG = {
    'timezone': timezone('America/New_York'),
    'job_defaults': {
        'coalesce': True,  # Only run once if multiple executions are missed
        'max_instances': 1,  # Only one instance of each job
        'misfire_grace_time': 3600  # Allow jobs to start up to 1 hour late
    },
    'executors': {
        'default': {'type': 'threadpool', 'max_workers': 4}
    }
}

# Flask configuration
class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-this')
    DEBUG = False
    TESTING = False
    CORS_HEADERS = 'Content-Type'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # API rate limiting
    RATELIMIT_DEFAULT = "100 per minute"
    RATELIMIT_STORAGE_URL = "memory://"
    
    # Logging configuration
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_LEVEL = 'INFO'
    LOG_FILE = LOGS_DIR / 'app.log'

class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'

class ProductionConfig(Config):
    LOG_LEVEL = 'WARNING'
    
    # Use environment variables in production
    def __init__(self):
        self.SECRET_KEY = os.getenv('SECRET_KEY')
        if not self.SECRET_KEY:
            raise ValueError("No SECRET_KEY set for production")

class TestingConfig(Config):
    TESTING = True
    LOG_LEVEL = 'DEBUG'

# Scheduler configuration
SCHEDULER_CONFIG = {
    'timezone': timezone('UTC'),
    'misfire_grace_time': 3600,  # 1 hour
    'coalesce': True
}

# Export configs
config_by_name = {
    'dev': DevelopmentConfig,
    'prod': ProductionConfig,
    'test': TestingConfig
}