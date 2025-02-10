import os
from supabase import create_client, Client
from datetime import datetime, timezone
from typing import List, Dict, Any

class Database:
    def __init__(self):
        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_KEY")
        self.supabase: Client = create_client(url, key)

    def insert_properties(self, properties: List[Dict[str, Any]], source: str) -> None:
        """Insert or update properties in the database.
        
        For each property:
        1. Check if a property with same address and floor exists
        2. If exists, update the existing record
        3. If not exists, insert as new record
        """
        for prop in properties:
            # Add source and timestamps
            prop["source"] = source
            current_time = datetime.now(timezone.utc).isoformat()
            
            # Query for existing property
            existing = self.supabase.table("properties") \
                .select("*") \
                .eq("address", prop["address"]) \
                .eq("floor_suite", prop["floor_suite"]) \
                .eq("source", source) \
                .execute()
                
            if existing.data:
                # Property exists, update it
                prop_id = existing.data[0]["id"]
                prop["updated_at"] = current_time
                
                # Store changes in property_changes table
                old_prop = existing.data[0]
                if self._has_changes(old_prop, prop):
                    try:
                        # Track changes for each field we care about
                        fields_to_track = ["property_name", "space_available", "price", "listing_url"]
                        changes = []
                        
                        for field in fields_to_track:
                            old_val = str(old_prop.get(field, ''))
                            new_val = str(prop.get(field, ''))
                            if old_val != new_val:
                                changes.append({
                                    "property_id": prop_id,
                                    "field_name": field,
                                    "old_value": old_val,
                                    "new_value": new_val,
                                    "source": source,
                                    "modified_at": current_time
                                })
                        
                        if changes:
                            self.supabase.table("property_changes").insert(changes).execute()
                            
                    except Exception as e:
                        print(f"Warning: Could not record property changes: {str(e)}")
                
                # Update the property
                self.supabase.table("properties") \
                    .update(prop) \
                    .eq("id", prop_id) \
                    .execute()
            else:
                # New property, insert it
                prop["created_at"] = current_time
                prop["updated_at"] = current_time
                self.supabase.table("properties").insert(prop).execute()
    
    def _has_changes(self, old_prop: Dict[str, Any], new_prop: Dict[str, Any]) -> bool:
        """Check if there are meaningful changes between old and new property data."""
        fields_to_compare = ["property_name", "space_available", "price", "listing_url"]
        return any(old_prop.get(field) != new_prop.get(field) for field in fields_to_compare)

    def get_latest_properties(self) -> List[Dict[str, Any]]:
        """Get all properties from the database."""
        try:
            response = self.supabase.table("properties") \
                .select("*") \
                .order("created_at", desc=True) \
                .execute()
            
            return response.data if response and hasattr(response, 'data') else []
        except Exception as e:
            print(f"Error fetching properties: {str(e)}")
            raise

    def get_changes_since_last_scrape(self, source: str) -> Dict[str, List[Dict[str, Any]]]:
        """Get new and modified properties since the last scrape."""
        last_scrape = self.supabase.table("scrape_logs") \
            .select("created_at") \
            .eq("source", source) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()

        if not last_scrape.data:
            return {"new": [], "modified": []}

        last_scrape_time = last_scrape.data[0]["created_at"]

        new_properties = self.supabase.table("properties") \
            .select("*") \
            .eq("source", source) \
            .gt("created_at", last_scrape_time) \
            .execute()

        modified_properties = self.supabase.table("property_changes") \
            .select("*") \
            .eq("source", source) \
            .gt("modified_at", last_scrape_time) \
            .execute()

        return {
            "new": new_properties.data,
            "modified": modified_properties.data
        }

    def log_scrape(self, source: str, status: str, properties_count: int) -> None:
        """Log a scrape operation."""
        self.supabase.table("scrape_logs").insert({
            "source": source,
            "status": status,
            "properties_count": properties_count,
            "created_at": datetime.now().isoformat()
        }).execute()
