# backend/scrapers/cushman.py
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from bs4 import BeautifulSoup
from crawl4ai import (
    AsyncWebCrawler, 
    BrowserConfig, 
    CrawlerRunConfig, 
    CacheMode, 
    MemoryAdaptiveDispatcher, 
    CrawlerMonitor, 
    DisplayMode
)

from .base import BaseScraper

class CushmanScraper(BaseScraper):
    """Scraper for Cushman & Wakefield commercial properties."""
    
    def __init__(self):
        super().__init__('cushman')
        self.start_url = (
            'https://www.cushmanwakefield.com/en/united-states/properties/lease/'
            'lease-property-search#sort=%40propertylastupdateddate%20descending'
            '&f:PropertyType=[Office]&f:Country=[United%20States]'
        )

    async def scrape(self) -> List[Dict[str, Any]]:
        """Main scraping method for Cushman & Wakefield properties."""
        browser_config = BrowserConfig(
            headless=True,
            verbose=True,
            ignore_https_errors=True,
            extra_args=['--disable-web-security'],
            headers={
                'sec-fetch-site': 'same-origin',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-dest': 'document'
            }
        )

        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                self.logger.info("Starting Cushman & Wakefield property extraction")
                
                # Extract property URLs
                property_urls = await self._extract_property_urls(crawler)
                if not property_urls:
                    self.logger.warning("No property URLs found")
                    return []
                    
                self.logger.info(f"Found {len(property_urls)} properties to process")
                
                # Extract details from each property
                return await self._extract_property_details(crawler, property_urls)
                
        except Exception as e:
            self.logger.error(f"Error in Cushman & Wakefield scraper: {str(e)}", exc_info=True)
            raise

    async def _extract_property_urls(self, crawler) -> List[str]:
        """Extract property URLs from Cushman & Wakefield listing pages.
        
        Args:
            crawler: AsyncWebCrawler instance to use for requests
            
        Returns:
            List of property URLs
        """
        js_wait = """
        await new Promise(r => setTimeout(r, 5000));
        """
        
        js_wait1 = """
        await new Promise(r => setTimeout(r, 500));
        """
        
        js_next_page = """
        const selector = 'span.coveo-accessible-button';
        const button = document.querySelector(selector);
        if (button) {
            console.log('Found next page button');
            button.click();
            return true;
        } else {
            console.log('No next page button found');
            return false;
        }
        await new Promise(r => setTimeout(r, 3000));
        """

        self.logger.info("Starting property URL extraction")
        
        session_id = "cushman_session"
        all_property_urls = set()  # Using a set to avoid duplicates
        last_page_urls = set()
        
        try:
            # Configure first page load
            config_first = CrawlerRunConfig(
                session_id=session_id,
                js_code=js_wait,
                css_selector='div.coveo-result-list-container',
                cache_mode=CacheMode.BYPASS,
                page_timeout=60000,
                simulate_user=True,
                override_navigator=True,
                remove_overlay_elements=True,
                magic=True
            )
            
            # Load first page
            result = await crawler.arun(
                url=self.start_url,
                config=config_first,
                session_id=session_id
            )
            
            if not result.success:
                self.logger.error(f"Failed to load first page: {result.error_message}")
                return list(all_property_urls)
            
            # Extract URLs from first page
            soup = BeautifulSoup(result.html, 'html.parser')
            property_links = soup.find_all('a', href=lambda x: x and 'properties/for-lease/office' in x)
            current_page_urls = {f'{link["href"]}' for link in property_links}
            all_property_urls.update(current_page_urls)
            
            self.logger.info(f"Found {len(current_page_urls)} property URLs on page 1")
            
            # Configure pagination
            page_num = 1
            max_pages = 20  # Limit to prevent infinite loops
            
            while page_num <= max_pages:
                # Store current page URLs for comparison
                last_page_urls = current_page_urls
                
                # Check for next button and if it's disabled
                next_li = soup.find('li', {'class': 'coveo-pager-next'})
                if not next_li or 'coveo-pager-list-item-disabled' in next_li.get('class', []):
                    self.logger.info("Next button is disabled - reached end of pagination")
                    break
                
                # Configure next page request
                config_next = CrawlerRunConfig(
                    session_id=session_id,
                    js_code=js_next_page,
                    js_only=True,
                    wait_for="""js:() => {
                        return document.querySelectorAll('div.CoveoResult').length > 1;
                    }""",
                    cache_mode=CacheMode.BYPASS,
                    page_timeout=60000,
                    simulate_user=True,
                    override_navigator=True,
                    magic=True
                )
                
                # Try to go to next page
                result = await crawler.arun(
                    url=self.start_url,  # URL doesn't matter for js_only
                    config=config_next,
                    session_id=session_id
                )
                
                if not result.success:
                    self.logger.error(f"Failed to load page {page_num + 1}: {result.error_message}")
                    break
                
                # Extract URLs from current page
                soup = BeautifulSoup(result.html, 'html.parser')
                property_links = soup.find_all('a', href=lambda x: x and 'properties/for-lease/office' in x)
                current_page_urls = {f'{link["href"]}' for link in property_links}
                
                # Check if we've reached the end (no new URLs)
                if not current_page_urls or current_page_urls == last_page_urls:
                    self.logger.info(f"No new URLs found on page {page_num + 1}, stopping pagination")
                    break
                
                all_property_urls.update(current_page_urls)
                self.logger.info(f"Found {len(current_page_urls)} property URLs on page {page_num + 1}")
                
                page_num += 1
                
                # Add delay between pages
                await asyncio.sleep(2)
                
        except Exception as e:
            self.logger.error(f"Error extracting property URLs: {str(e)}", exc_info=True)
        
        self.logger.info(f"Total unique properties found: {len(all_property_urls)}")
        return list(all_property_urls)

    async def _extract_property_details(self, crawler: AsyncWebCrawler, urls: List[str]) -> List[Dict[str, Any]]:
        """Extract details from property pages.
        
        Args:
            crawler: AsyncWebCrawler instance to use for requests
            urls: List of property URLs to process
            
        Returns:
            List of property dictionaries with extracted details
        """
        # Configure for property detail extraction
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            stream=True  # Process results as they come in
        )
        
        # Set up dispatcher for parallel processing
        dispatcher = MemoryAdaptiveDispatcher(
            memory_threshold_percent=60.0,  # Lower threshold to be more conservative
            check_interval=0.5,  # Check more frequently
            max_session_permit=25,  # Reduce concurrent sessions
            monitor=CrawlerMonitor(
                display_mode=DisplayMode.DETAILED
            )
        )
        
        self.logger.info(f"Starting property detail extraction for {len(urls)} properties")
        
        # Process property pages
        all_property_details = []
        
        try:
            stream = await crawler.arun_many(
                urls=urls,
                config=run_config,
                dispatcher=dispatcher
            )
            
            async for result in stream:
                if result.success and result.html:
                    try:
                        details = self._parse_property_page(result.html, result.url)
                        if details:
                            all_property_details.extend(details)
                            self.logger.debug(f"Successfully extracted details from {result.url}")
                        else:
                            self.logger.warning(f"No details extracted from {result.url}")
                    except Exception as e:
                        self.logger.error(
                            f"Error parsing property page {result.url}: {str(e)}", 
                            exc_info=True
                        )
                else:
                    self.logger.warning(
                        f"Failed to process {result.url}: "
                        f"{result.error_message if hasattr(result, 'error_message') else 'Unknown error'}"
                    )
                    
        except Exception as e:
            self.logger.error(f"Error in property detail extraction: {str(e)}", exc_info=True)
            
        self.logger.info(f"Successfully extracted details for {len(all_property_details)} properties")
        return all_property_details

    def _parse_property_page(self, html: str, url: str) -> Optional[List[Dict[str, Any]]]:
        """Parse a single property page HTML.
        
        Args:
            html: HTML content of the property page
            url: URL of the property page
            
        Returns:
            List of dictionaries containing property details or None if parsing fails
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            units = []
            
            # Extract property name and address
            title_div = soup.find('div', {'class': 'updated-page-title'})
            if not title_div:
                self.logger.warning(f"No title div found for {url}")
                return None
                
            property_name = title_div.find('h1', {'class': 'updated-page-title-main'})
            property_name = property_name.text.strip() if property_name else "N/A"
            
            address = title_div.find('h5', {'class': 'updated-page-title-sub'})
            address = address.text.strip() if address else "N/A"
            
            # Look for multiple availability containers
            availability_containers = soup.find_all('div', {'class': 'availabilities-container-parent'})
            if not availability_containers:
                # If no availability containers, create a single unit with basic info
                return [{
                    "property_name": property_name,
                    "address": address,
                    "floor_suite": "N/A",
                    "space_available": "Contact for Details",
                    "price": "Contact for Details",
                    "listing_url": url,
                    "updated_at": datetime.now().strftime('%I:%M:%S%p %m/%d/%y')
                }]
            
            # Process each availability container
            for container in availability_containers:
                # Extract floor/suite info
                title_div = container.find('div', {'class': 'blue-color-title-div'})
                floor_suite = "N/A"
                
                if title_div:
                    floor = title_div.find('b', {'class': 'font-bold'})
                    suite = title_div.find('span', string=lambda x: x and 'Suite' in x)
                    floor_suite = f"{floor.text.strip() if floor else ''} {suite.text.strip() if suite else ''}".strip()
                
                # Extract space and price
                space_available = "Contact for Details"
                price = "Contact for Details"
                
                desc_divs = container.find_all('div', {'class': 'availabilities-second-level-description'})
                
                for div in desc_divs:
                    try:
                        label = div.find('p', {'class': 'm-1'})
                        if not label:
                            continue
                            
                        label_text = label.text.strip().lower()
                        value = div.find('p', {'class': 'font-bold'})
                        if not value:
                            continue
                            
                        value_text = value.text.strip()
                        
                        if 'space available' in label_text:
                            space_available = value_text
                        elif 'rental rate' in label_text:
                            price = value_text
                    except Exception as e:
                        self.logger.warning(f"Error parsing description div: {str(e)}")
                        continue
                
                # Create unit dictionary with extracted data
                unit = {
                    "property_name": property_name,
                    "address": address,
                    "floor_suite": floor_suite,
                    "space_available": space_available,
                    "price": price,
                    "listing_url": url,
                    "updated_at": datetime.now().strftime('%I:%M:%S%p %m/%d/%y')
                }
                
                units.append(unit)
            
            return units
            
        except Exception as e:
            self.logger.error(f"Error parsing property page {url}: {str(e)}", exc_info=True)
            return None

async def run_scraper():
    """Run the Cushman & Wakefield scraper."""
    scraper = CushmanScraper()
    results = await scraper.scrape()
    print(f"Scraped {len(results)} properties")
    return results

if __name__ == "__main__":
    asyncio.run(run_scraper())
