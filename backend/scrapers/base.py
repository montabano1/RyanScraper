# backend/scrapers/base.py
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, TypeVar, Callable
from functools import wraps
from abc import ABC, abstractmethod

from ..storage import StorageManager
from ..config import SCRAPERS

T = TypeVar('T')

def with_retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for adding retry logic to async functions"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(self, *args: Any, **kwargs: Any) -> T:
            last_error = None
            for attempt in range(max_retries):
                try:
                    return await func(self, *args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (backoff ** attempt)
                        self.logger.warning(
                            f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {str(e)}"
                        )
                        await asyncio.sleep(wait_time)
            raise last_error
        return wrapper
    return decorator

class BaseScraper(ABC):
    """
    Base class for all scrapers. Provides common functionality for:
    - Error handling and logging
    - Result storage and comparison
    - Retry logic
    - Configuration management
    """
    def __init__(self, scraper_id: str):
        if scraper_id not in SCRAPERS:
            raise ValueError(f"Invalid scraper ID: {scraper_id}")
        
        self.scraper_id = scraper_id
        self.config: Dict[str, Any] = SCRAPERS[scraper_id]
        self.storage = StorageManager(Path(__file__).parent.parent / 'data')
        self.logger = logging.getLogger(f"scraper.{scraper_id}")
        
        # Set up logging
        handler = logging.FileHandler(
            Path(__file__).parent.parent / 'logs' / f'{scraper_id}.log'
        )
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    async def run(self) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Main entry point for running the scraper.
        Returns (results, error_message).
        """
        try:
            self.logger.info(f"Starting {self.scraper_id} scraper")
            results = await self.scrape()
            
            if not results:
                msg = "No results returned from scraper"
                self.logger.warning(msg)
                return None, msg
            
            # Compare with previous results and save
            changes = self.storage.compare_and_save_results(self.scraper_id, results)
            
            self.logger.info(
                f"Scraping completed: {len(changes['new'])} new, "
                f"{len(changes['modified'])} modified, "
                f"{len(changes['removed'])} removed"
            )
            
            return results, None
            
        except Exception as e:
            error_msg = f"Error in {self.scraper_id} scraper: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return None, error_msg

    @abstractmethod
    @with_retry()
    async def scrape(self) -> List[Dict[str, Any]]:
        """
        Override this method in each scraper implementation.
        Must return a list of property dictionaries with the following fields:
        - property_name: str
        - address: str
        - floor_suite: str
        - space_available: str
        - price: str
        - listing_url: str
        - updated_at: str (format: '%I:%M:%S%p %m/%d/%y')
        """
        raise NotImplementedError

    def get_current_results(self) -> List[Dict[str, Any]]:
        """Get current results with their status"""
        return self.storage.get_current_results(self.scraper_id)

    def export_to_csv(self) -> Optional[str]:
        """Export current results to CSV"""
        return self.storage.export_to_csv(self.scraper_id)