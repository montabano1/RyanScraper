# backend/scrapers/jll.py
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

class JLLScraper(BaseScraper):
    """Scraper for JLL commercial properties."""
    
    def __init__(self):
        super().__init__('jll')
        self.start_url = (
            'https://property.jll.com/search'
            '?tenureType=rent'
            '&propertyTypes=office'
            '&orderBy=desc'
            '&sortBy=dateModified'
        )

    async def scrape(self) -> List[Dict[str, Any]]:
        """Main scraping method for JLL properties."""
        browser_config = BrowserConfig(
            headless=True,
            verbose=True,
            viewport_height=1080,
            viewport_width=1920,
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
                self.logger.info("Starting JLL property extraction")
                
                # Extract property URLs
                property_urls = await self._extract_property_urls(crawler)
                if not property_urls:
                    self.logger.warning("No property URLs found")
                    return []
                    
                self.logger.info(f"Found {len(property_urls)} properties to process")
                
                # Extract details from each property
                return await self._extract_property_details(crawler, property_urls)
                
        except Exception as e:
            self.logger.error(f"Error in JLL scraper: {str(e)}", exc_info=True)
            raise

    async def _extract_property_urls(self, crawler) -> List[str]:
        """Extract property URLs from JLL listing pages.
        
        Args:
            crawler: AsyncWebCrawler instance to use for requests
            
        Returns:
            List of property URLs
        """
        js_wait = """
        await new Promise(r => setTimeout(r, 5000));
        """
        
        js_next_page = """
        const lastLi = document.querySelector('nav[role="navigation"] ul li:last-child');
        const svg = lastLi ? lastLi.querySelector('svg.h-6.text-jllRed') : null;
        if (svg && svg.querySelector('path[d*="8.22"]')) {
            console.log('Found next page button');
            lastLi.querySelector('button').click();
            return true;
        }
        console.log('No next page button found');
        return false;
        """

        self.logger.info("Starting property URL extraction")
        
        session_id = "jll_session"
        all_property_urls = set()
        
        try:
            # Configure first page load
            config_first = CrawlerRunConfig(
                session_id=session_id,
                js_code=js_wait,
                css_selector='div.grid',
                cache_mode=CacheMode.BYPASS,
                page_timeout=60000,
                simulate_user=True,
                override_navigator=True,
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
            property_links = soup.find_all('a', href=lambda x: x and 'listings/' in x)
            current_page_urls = {f'https://property.jll.com{link["href"]}' for link in property_links}
            all_property_urls.update(current_page_urls)
            
            self.logger.info(f"Found {len(current_page_urls)} property URLs on page 1")
            
            # Configure pagination
            page_num = 2
            max_pages = 20  # Limit to prevent infinite loops
            
            while page_num <= max_pages:
                # Configure next page request
                config_next = CrawlerRunConfig(
                    session_id=session_id,
                    js_code=js_next_page,
                    js_only=True,      
                    wait_for="""js:() => {
                        return document.querySelectorAll('div[data-cy="property-card"].relative').length > 1;
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
                    self.logger.error(f"Failed to load page {page_num}: {result.error_message}")
                    break
                
                # Extract URLs from current page
                soup = BeautifulSoup(result.html, 'html.parser')
                property_links = soup.find_all('a', href=lambda x: x and 'listings/' in x)
                current_page_urls = {f'https://property.jll.com{link["href"]}' for link in property_links}
                
                # Check if we've reached the end (no new URLs or no next button)
                last_li = soup.select_one('nav[role="navigation"] ul li:last-child')
                next_button = last_li and last_li.find('svg', class_='h-6 text-jllRed')
                if not current_page_urls or not (next_button and next_button.find('path', {'d': lambda x: x and '8.22' in x})):
                    self.logger.info(f"No new URLs found on page {page_num} or reached end of pagination")
                    break
                
                all_property_urls.update(current_page_urls)
                self.logger.info(f"Found {len(current_page_urls)} property URLs on page {page_num}")
                
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
            page_timeout=60000,
            js_code="""await new Promise(r => setTimeout(r, 500));""",
            stream=True
        )
        
        # Set up dispatcher for parallel processing
        dispatcher = MemoryAdaptiveDispatcher(
            memory_threshold_percent=60.0,
            check_interval=0.5,
            max_session_permit=10,
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
                            all_property_details.extend(details if isinstance(details, list) else [details])
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
            
            # Extract property name
            header_div = soup.select_one('div.mb-6.flex.flex-col')
            name_elem = header_div.select_one('h1.MuiTypography-root.jss6') if header_div else None
            if not name_elem:
                self.logger.warning(f"No property name found for {url}")
                return None
            
            property_name = name_elem.text.strip()
            
            # Extract price
            price = "Contact for pricing"
            price_elem = header_div.select_one('div.flex.items-center.justify-end.text-bronze p.text-lg') if header_div else None
            if price_elem:
                price = price_elem.text.strip()
            
            # Extract address components
            address_div = soup.select_one('div.flex-col.text-doveGrey')
            street_address = ""
            city_state = ""
            
            if address_div:
                address_parts = [p.text.strip() for p in address_div.find_all('p', class_='text-lg')]
                if len(address_parts) >= 1:
                    street_address = address_parts[0]
                if len(address_parts) >= 2:
                    city_state = address_parts[1]
            
            # Extract available spaces
            spaces = []
            space_divs = soup.select('div.space-details')
            
            for space in space_divs:
                floor = space.select_one('.space-floor')
                size = space.select_one('.space-size')
                rate = space.select_one('.space-rate')
                
                spaces.append({
                    "property_name": property_name,
                    "address": f"{street_address}, {city_state}".strip(", "),
                    "floor_suite": floor.text.strip() if floor else "",
                    "space_available": size.text.strip() if size else "",
                    "price": rate.text.strip() if rate else price,  # Use header price if no specific rate
                    "listing_url": url,
                    "updated_at": datetime.now().strftime('%I:%M:%S%p %m/%d/%y')
                })
            
            return spaces if spaces else [{
                "property_name": property_name,
                "address": f"{street_address}, {city_state}".strip(", "),
                "floor_suite": "",
                "space_available": "",
                "price": price,
                "listing_url": url,
                "updated_at": datetime.now().strftime('%I:%M:%S%p %m/%d/%y')
            }]
            
        except Exception as e:
            self.logger.error(f"Error parsing property page {url}: {str(e)}", exc_info=True)
            return None


if __name__ == "__main__":
    scraper = JLLScraper()
    asyncio.run(scraper.run())
        
        address = f"{street_address}, {city_state}" if street_address else city_state
        
        # First get the top-level space info
        space_text = None
        space_li = soup.select_one('ul.flex.flex-wrap li span.text-lg.text-neutral-700 span')
        if space_li:
            space_text = space_li.text.strip()

        units = []
        availability_div = soup.find('div', id='availability')
        if availability_div:
            # Try to find rows through multiple paths
            rows = []
            
            # Find all action arrow cells with the specific SVG pattern
            action_cells = availability_div.find_all('div', {'class': 'action-arrow'})
            if action_cells:
                for cell in action_cells:
                    # Check for SVG with specific path pattern
                    svg = cell.find('svg', {'class': 'MuiSvgIcon-root MuiSvgIcon-colorPrimary'})
                    if svg:
                        # Look for the path with the specific coordinates
                        paths = svg.find_all('path')
                        for path in paths:
                            d_attr = path.get('d', '')
                            if any(coord in d_attr for coord in ['14.9848 6.84933', 'M14.9848 6.84933']):
                                parent_row = cell.find_parent('div', {'role': 'row', 'class': lambda x: x and 'MuiDataGrid-row' in x})
                                if parent_row and parent_row not in rows:
                                    rows.append(parent_row)
            
            if rows:
                for row in rows:
                    # Find floor cell - try both class and data-field attributes
                    floor_cell = row.find('div', {'class': 'floor-name'}) or row.find('div', {'data-field': 'floorName'})
                    floor_text = None
                    if floor_cell:
                        # First try the span inside group div
                        span = floor_cell.select_one('div.max-w-full.overflow-hidden span')
                        if span:
                            floor_text = span.text.strip()
                        else:
                            # Fallback to any text content in the cell
                            floor_text = floor_cell.get_text(strip=True)
                    
                    # Find space cell using data-field="size"
                    space_cell = row.find('div', {'data-field': 'size'})
                    row_space_text = space_cell.get_text(strip=True) if space_cell else None
                    
                    if floor_text and row_space_text:
                        unit = {
                            "property_name": property_name,
                            "address": address,
                            "listing_url": url,
                            "floor_suite": floor_text,
                            "space_available": row_space_text,
                            "price": price,
                            "updated_at": datetime.now().strftime('%I:%M:%S%p %m/%d/%y')
                        }
                        units.append(unit)
            else:
                # Create a single entry with N/A for floor_suite
                unit = {
                    "property_name": property_name,
                    "address": address,
                    "listing_url": url,
                    "floor_suite": "N/A",
                    "space_available": space_text or "Contact for Details",
                    "price": price,
                    "updated_at": datetime.now().strftime('%I:%M:%S%p %m/%d/%y')
                }
                units.append(unit)
        else:
            # Create a single entry with N/A for floor_suite
            unit = {
                "property_name": property_name,
                "address": address,
                "listing_url": url,
                "floor_suite": "N/A",
                "space_available": space_text or "Contact for Details",
                "price": price,
                "updated_at": datetime.now().strftime('%I:%M:%S%p %m/%d/%y')
            }
            units.append(unit)
        
        return units

async def run_scraper():
    scraper = JLLScraper()
    results = await scraper.scrape()
    print(f"Scraped {len(results)} properties")

if __name__ == "__main__":
    asyncio.run(run_scraper())
