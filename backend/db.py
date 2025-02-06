import os
from datetime import datetime
from typing import List, Dict, Any
from supabase import create_client, Client

# Initialize Supabase client
supabase: Client = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_KEY')
)

def get_latest_properties() -> List[Dict[str, Any]]:
    """Get all properties from the database"""
    try:
        response = supabase.table('properties').select('*').execute()
        properties = response.data
        
        # Convert datetime objects to ISO format strings for JSON serialization
        for prop in properties:
            if 'last_updated' in prop and isinstance(prop['last_updated'], datetime):
                prop['last_updated'] = prop['last_updated'].isoformat()
        
        return properties
    except Exception as e:
        raise Exception(f"Failed to fetch properties: {str(e)}")

def upsert_properties(properties: List[Dict[str, Any]]) -> None:
    """Insert or update properties in the database"""
    try:
        # Add last_updated timestamp
        for prop in properties:
            prop['last_updated'] = datetime.utcnow().isoformat()
        
        supabase.table('properties').upsert(properties).execute()
    except Exception as e:
        raise Exception(f"Failed to upsert properties: {str(e)}")

def get_property_changes(old_properties: List[Dict[str, Any]], new_properties: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Compare old and new properties to find changes"""
    old_dict = {p['id']: p for p in old_properties}
    new_dict = {p['id']: p for p in new_properties}
    
    new_items = []
    modified_items = []
    removed_items = []
    
    # Find new and modified items
    for id, new_prop in new_dict.items():
        if id not in old_dict:
            new_items.append(new_prop)
        elif new_prop != old_dict[id]:
            modified_items.append(new_prop)
    
    # Find removed items
    for id in old_dict:
        if id not in new_dict:
            removed_items.append(old_dict[id])
    
    return {
        'new': new_items,
        'modified': modified_items,
        'removed': removed_items
    }
