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
        """Insert new properties into the database."""
        for prop in properties:
            prop["source"] = source
            prop["created_at"] = datetime.now(timezone.utc).isoformat()
            
        self.supabase.table("properties").insert(properties).execute()

    def get_latest_properties(self) -> List[Dict[str, Any]]:
        """Get the latest properties from all sources."""
        try:
            print("Fetching properties from Supabase...")
            response = self.supabase.table("properties") \
                .select("*") \
                .order("created_at", desc=True) \
                .limit(1000) \
                .execute()
            print(f"Supabase response: {response}")
            data = response.data if response and hasattr(response, 'data') else []
            print(f"Returning {len(data)} properties")
            return data
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
