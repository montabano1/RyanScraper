# app.py
from datetime import datetime, date, timezone
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS, cross_origin
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import importlib
from datetime import datetime
from pytz import timezone
import asyncio
from pathlib import Path
import os
import logging
from dotenv import load_dotenv
import pandas as pd
from io import BytesIO

from backend.config import config_by_name, SCRAPERS, SCHEDULER_CONFIG, DATA_DIR
from backend.scrapers import *  # Import all scrapers
from backend.database import Database

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__, static_folder='static', static_url_path='')

# Get environment and configure app
env = os.getenv('FLASK_ENV', 'production')

# Map common environment names to our config names
env_mapping = {
    'dev': 'development',
    'prod': 'production',
    'test': 'test'
}
env = env_mapping.get(env, env)  # Map if it's a known alias, otherwise keep as is

# Enable CORS
CORS(app)

@app.route('/')
def serve_frontend():
    return app.send_static_file('index.html')

@app.errorhandler(404)
def not_found(e):
    if '.' not in request.path:  # No file extension = frontend route
        return app.send_static_file('index.html')
    return jsonify({'error': 'Not found'}), 404

# Load configuration
if env in config_by_name:
    app.config.from_object(config_by_name[env]())
else:
    print(f"Warning: Environment '{env}' not found in config, using 'production'")
    app.config.from_object(config_by_name['production']())

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

# Initialize database
db = Database()

@app.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(timezone('UTC')).isoformat()
    })

# Set up logging
logging.basicConfig(
    level=getattr(logging, app.config['LOG_LEVEL']),
    format=app.config['LOG_FORMAT']
)
logger = logging.getLogger(__name__)

# Initialize scheduler and scraper status tracking
scheduler = BackgroundScheduler(SCHEDULER_CONFIG)
scraper_status = {}

def load_scraper(scraper_id):
    """Dynamically load scraper module"""
    if scraper_id not in SCRAPERS:
        return None
    
    try:
        module_path = SCRAPERS[scraper_id]['class']
        module = importlib.import_module(module_path)
        return module
    except Exception as e:
        logger.error(f"Error loading scraper {scraper_id}: {e}")
        return None

async def run_scraper(scraper_id):
    """Run a scraper and process results"""
    logger.info(f"Starting scraper: {scraper_id}")
    scraper_status[scraper_id] = {'state': 'running', 'start_time': datetime.utcnow().isoformat()}
    
    try:
        scraper_module = load_scraper(scraper_id)
        if not scraper_module:
            logger.error(f"Failed to load scraper: {scraper_id}")
            scraper_status[scraper_id] = {'state': 'failed', 'error': 'Failed to load scraper'}
            return None
        
        results = await scraper_module.extract_property_urls()
        if results:
            # Store results in database
            db.insert_properties(results, scraper_id)
            logger.info(f"Scraper {scraper_id} completed successfully")
            scraper_status[scraper_id] = {'state': 'completed', 'end_time': datetime.utcnow().isoformat()}
            return True
        else:
            logger.warning(f"Scraper {scraper_id} returned no results")
            scraper_status[scraper_id] = {'state': 'failed', 'error': 'No results returned'}
            return False
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error in scraper {scraper_id}: {error_msg}", exc_info=True)
        scraper_status[scraper_id] = {'state': 'failed', 'error': error_msg}
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

@app.route('/api/properties')
@limiter.limit("60 per minute")
def get_properties():
    """Get all properties with optional filtering"""
    source = request.args.get('source')
    
    try:
        properties = db.get_latest_properties()
        
        if source:
            properties = [p for p in properties if p['source'] == source]
        
        # Convert any non-serializable objects to strings
        serializable_properties = []
        for prop in properties:
            serializable_prop = {}
            for key, value in prop.items():
                if isinstance(value, (datetime, date)):
                    serializable_prop[key] = value.isoformat()
                else:
                    serializable_prop[key] = value
            serializable_properties.append(serializable_prop)
            
        logger.debug(f"Sending {len(serializable_properties)} properties")
        return jsonify(serializable_properties)
    except Exception as e:
        logger.error(f"Error getting properties: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Create a background task pool
background_tasks = {}

@app.route('/api/scrapers/<scraper_id>/run', methods=['POST'])
@limiter.limit("5 per minute")
def trigger_scraper(scraper_id):
    """Manually trigger a scraper"""
    try:
        if scraper_id not in SCRAPERS:
            return jsonify({'error': 'Invalid scraper ID'}), 404

        if not SCRAPERS[scraper_id].get('enabled', True):
            return jsonify({'error': 'Scraper is disabled'}), 400

        # Check if scraper is already running
        current_status = scraper_status.get(scraper_id, {})
        if current_status.get('state') == 'running':
            return jsonify({'error': 'Scraper is already running'}), 400

        # Set initial status
        scraper_status[scraper_id] = {'state': 'running', 'start_time': datetime.utcnow().isoformat()}

        # Create a new event loop for this task
        loop = asyncio.new_event_loop()
        
        def run_scraper_task():
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(run_scraper(scraper_id))
            finally:
                loop.close()
        
        # Start the scraper in a separate thread
        import threading
        thread = threading.Thread(target=run_scraper_task)
        thread.start()
        
        # Store the thread in background tasks
        background_tasks[scraper_id] = thread
        
        return jsonify({'status': 'started'})
    except Exception as e:
        logger.error(f"Error triggering scraper {scraper_id}: {e}", exc_info=True)
        scraper_status[scraper_id] = {'state': 'failed', 'error': str(e)}
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/scrapers/<scraper_id>/status', methods=['GET'])
def get_scraper_status(scraper_id):
    """Get the current status of a scraper"""
    try:
        if scraper_id not in SCRAPERS:
            return jsonify({'error': 'Invalid scraper ID'}), 404

        status = scraper_status.get(scraper_id, {'state': 'idle'})
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting scraper status {scraper_id}: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


        
    except Exception as e:
        logger.error(f"Error exporting data: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'error': 'Rate limit exceeded'}), 429

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
    return jsonify({'error': 'Internal server error', 'message': str(e)}), 500

@app.route('/api/changes', methods=['GET'])
def get_changes():
    """Get properties that have changed since last scrape."""
    try:
        # Get changes from property_changes table
        changes = db.get_property_changes()
        return jsonify({
            'success': True,
            'changes': changes
        })
    except Exception as e:
        logging.error(f"Error getting property changes: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/export', methods=['POST', 'OPTIONS'])
@cross_origin()
def export_data():
    """Export properties as CSV"""
    
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        # Get filtered properties from request
        data = request.get_json()
        
        properties = data.get('properties', [])
        logger.debug(f"Properties length: {len(properties)}")
        
        if not properties:
            logger.debug("No properties found in request")
            return jsonify({
                'status': 'error',
                'message': 'No data available'
            }), 404
            
        
        # Convert to DataFrame - data is already formatted from frontend
        df = pd.DataFrame(properties)
        
        # Export to CSV
        logger.debug("Exporting to CSV")
        output = BytesIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        logger.debug("Sending file response")
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'properties_{datetime.now().strftime("%Y%m%d")}.csv'
        )
    except Exception as e:
        logger.error(f"Error exporting data: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    print('\nRegistered Routes:')
    for rule in app.url_map.iter_rules():
        print(f"{rule.endpoint}: {rule.methods} {rule}")
    print('\n')
    app.run(host='0.0.0.0', port=5000)