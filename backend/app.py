# app.py
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import importlib
from datetime import datetime
import asyncio
from pathlib import Path
import os
import logging
from dotenv import load_dotenv

from config import config_by_name, SCRAPERS, SCHEDULER_CONFIG, DATA_DIR
from storage import StorageManager

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Get environment, default to 'dev' if not specified
env = os.getenv('FLASK_ENV', 'dev')
if env not in config_by_name:
    print(f"Warning: Environment '{env}' not found in config, using 'dev'")
    env = 'dev'

app.config.from_object(config_by_name[env])

# Initialize CORS
CORS(app)

# Initialize rate limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[app.config['RATELIMIT_DEFAULT']],
    storage_uri=app.config['RATELIMIT_STORAGE_URL']
)

# Set up logging
logging.basicConfig(
    filename=app.config['LOG_FILE'],
    level=getattr(logging, app.config['LOG_LEVEL']),
    format=app.config['LOG_FORMAT']
)
logger = logging.getLogger(__name__)

# Initialize storage
storage = StorageManager(DATA_DIR)

# Initialize scheduler
scheduler = BackgroundScheduler(SCHEDULER_CONFIG)

def load_scraper(scraper_id):
    """Dynamically load scraper class"""
    if scraper_id not in SCRAPERS:
        return None
    
    try:
        module_path, class_name = SCRAPERS[scraper_id]['class'].rsplit('.', 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)()
    except Exception as e:
        logger.error(f"Error loading scraper {scraper_id}: {e}")
        return None

async def run_scraper(scraper_id):
    """Run a scraper and process results"""
    logger.info(f"Starting scraper: {scraper_id}")
    try:
        scraper = load_scraper(scraper_id)
        if not scraper:
            logger.error(f"Failed to load scraper: {scraper_id}")
            return None
        
        results, error = await scraper.run()
        if error:
            logger.error(f"Error in scraper {scraper_id}: {error}")
            return False
        
        if results:
            logger.info(f"Scraper {scraper_id} completed successfully")
            return True
        else:
            logger.warning(f"Scraper {scraper_id} returned no results")
            return False
            
    except Exception as e:
        logger.error(f"Unexpected error in scraper {scraper_id}: {e}", exc_info=True)
        return False

# Set up scheduled jobs
for scraper_id, config in SCRAPERS.items():
    if config.get('enabled', True):
        scheduler.add_job(
            func=lambda sid=scraper_id: asyncio.run(run_scraper(sid)),
            trigger=CronTrigger.from_crontab(config['schedule']),
            id=f'scraper_{scraper_id}',
            name=f'Scheduled {config["name"]}',
            replace_existing=True
        )
        logger.info(f"Scheduled {config['name']} with cron: {config['schedule']}")

scheduler.start()

@app.route('/api/scrapers')
@limiter.limit("30 per minute")
def get_scrapers():
    """Get list of available scrapers and their status"""
    scrapers = []
    for scraper_id, config in SCRAPERS.items():
        job = scheduler.get_job(f'scraper_{scraper_id}')
        scrapers.append({
            'id': scraper_id,
            'name': config['name'],
            'schedule': config['schedule'],
            'enabled': config.get('enabled', True),
            'next_run': job.next_run_time.isoformat() if job else None
        })
    return jsonify(scrapers)

@app.route('/api/scrapers/<scraper_id>/results')
@limiter.limit("60 per minute")
def get_results(scraper_id):
    """Get current results with change tracking"""
    try:
        if scraper_id not in SCRAPERS:
            return jsonify({'error': 'Invalid scraper ID'}), 404
            
        results = storage.get_current_results(scraper_id)
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error getting results for {scraper_id}: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/scrapers/<scraper_id>/run', methods=['POST'])
@limiter.limit("5 per minute")
def trigger_scraper(scraper_id):
    """Manually trigger a scraper"""
    try:
        if scraper_id not in SCRAPERS:
            return jsonify({'error': 'Invalid scraper ID'}), 404

        if not SCRAPERS[scraper_id].get('enabled', True):
            return jsonify({'error': 'Scraper is disabled'}), 400

        # Run scraper asynchronously
        asyncio.run(run_scraper(scraper_id))
        return jsonify({'status': 'started'})
    except Exception as e:
        logger.error(f"Error triggering scraper {scraper_id}: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/scrapers/<scraper_id>/export')
@limiter.limit("10 per minute")
def export_data(scraper_id):
    """Export scraper data to CSV"""
    try:
        if scraper_id not in SCRAPERS:
            return jsonify({'error': 'Invalid scraper ID'}), 404

        csv_file = storage.export_to_csv(scraper_id)
        if not csv_file:
            return jsonify({'error': 'No data available'}), 404
        
        return send_file(
            csv_file,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"{scraper_id}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
    except Exception as e:
        logger.error(f"Error exporting data for {scraper_id}: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'error': 'Rate limit exceeded'}), 429

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal server error: {e}", exc_info=True)
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)