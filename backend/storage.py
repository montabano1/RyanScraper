# storage.py
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple

class StorageManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.results_dir = data_dir / 'results'
        self.results_dir.mkdir(exist_ok=True)

    def get_scraper_dir(self, scraper_id: str) -> Path:
        scraper_dir = self.results_dir / scraper_id
        scraper_dir.mkdir(exist_ok=True)
        return scraper_dir

    def compare_and_save_results(self, scraper_id: str, new_results: List[Dict[str, Any]]) -> Dict[str, List]:
        """
        Compare new results with previous and save them
        Returns dict with new, modified, and removed properties
        """
        scraper_dir = self.get_scraper_dir(scraper_id)
        previous_file = scraper_dir / 'current.json'
        
        # Initialize changes dict
        changes = {
            'new': [],
            'modified': [],
            'removed': []
        }
        
        # Load previous results if they exist
        previous_results = []
        if previous_file.exists():
            with open(previous_file) as f:
                previous_results = json.load(f)
            
            # Create lookup dictionaries using property name and address as key
            prev_lookup = {
                self._get_property_key(prop): prop 
                for prop in previous_results
            }
            new_lookup = {
                self._get_property_key(prop): prop 
                for prop in new_results
            }
            
            # Find new and modified properties
            for prop_key, new_prop in new_lookup.items():
                if prop_key not in prev_lookup:
                    new_prop['_status'] = 'new'
                    changes['new'].append(new_prop)
                elif self._has_changes(prev_lookup[prop_key], new_prop):
                    new_prop['_status'] = 'modified'
                    changes['modified'].append(new_prop)
                else:
                    new_prop['_status'] = 'unchanged'
            
            # Find removed properties
            changes['removed'] = [
                prop for key, prop in prev_lookup.items()
                if key not in new_lookup
            ]
        else:
            # If no previous results, all properties are new
            for prop in new_results:
                prop['_status'] = 'new'
            changes['new'] = new_results

        # Save new results as current
        with open(previous_file, 'w') as f:
            json.dump(new_results, f, indent=2)
        
        # Save changes summary
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        changes_file = scraper_dir / f'changes_{timestamp}.json'
        with open(changes_file, 'w') as f:
            json.dump(changes, f, indent=2)
        
        return changes

    def _get_property_key(self, property_data: Dict) -> str:
        """Create unique key for property based on name and address"""
        return f"{property_data['property_name']}|{property_data['address']}"

    def _has_changes(self, prev_prop: Dict, new_prop: Dict) -> bool:
        """Check if property details have changed"""
        fields_to_compare = ['space_available', 'price', 'floor_suite']
        return any(
            prev_prop.get(field) != new_prop.get(field)
            for field in fields_to_compare
        )

    def get_current_results(self, scraper_id: str) -> List[Dict[str, Any]]:
        """Get the current results with their status"""
        current_file = self.get_scraper_dir(scraper_id) / 'current.json'
        if current_file.exists():
            with open(current_file) as f:
                return json.load(f)
        return []

    def export_to_csv(self, scraper_id: str) -> str:
        """Export current results to CSV"""
        results = self.get_current_results(scraper_id)
        if not results:
            return None

        scraper_dir = self.get_scraper_dir(scraper_id)
        csv_file = scraper_dir / f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Get all unique keys excluding internal _status field
        keys = {key for item in results for key in item.keys() if not key.startswith('_')}
        keys = sorted(list(keys))

        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            # Remove _status before writing
            cleaned_results = [{k: v for k, v in item.items() if not k.startswith('_')} 
                             for item in results]
            writer.writerows(cleaned_results)

        return str(csv_file)