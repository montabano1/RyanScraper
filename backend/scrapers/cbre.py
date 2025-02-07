# backend/scrapers/cbre.py
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
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

js_wait1 = """
        await new Promise(r => setTimeout(r, 500));
        """

class CbreScraper(BaseScraper):
    """Scraper for CBRE commercial properties."""
    
    def __init__(self):
        super().__init__('cbre')
        self.start_url = (
            'https://www.cbre.com/properties/properties-for-lease/commercial-space'
            '?sort=lastupdated%2Bdescending'
            '&propertytype=Office'
            '&transactiontype=isLetting'
            '&initialpolygon=%5B%5B67.12117833969766%2C-28.993985994685787%5D%2C'
            '%5B-26.464978515643416%2C-141.84554849468577%5D%5D'
        )

    async def scrape(self) -> List[Dict[str, Any]]:
        """Main scraping method for CBRE properties."""
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
                self.logger.info("Starting CBRE property extraction")
                
                # Extract property URLs
                property_urls = await self._extract_property_urls(crawler)
                if not property_urls:
                    self.logger.warning("No property URLs found")
                    return []
                
                self.logger.info(f"Found {len(property_urls)} properties to process")
                
                # Extract details from each property
                return await self._extract_property_details(crawler, property_urls)
                
        except Exception as e:
            self.logger.error(f"Error in CBRE scraper: {str(e)}", exc_info=True)
            raise

    async def _extract_property_urls(self, crawler) -> List[str]:
        """Extract property URLs from CBRE listing pages.
        
        Args:
            crawler: AsyncWebCrawler instance to use for requests
            
        Returns:
            List of property URLs
        """
        js_wait = """
        await new Promise(r => setTimeout(r, 5000));
        """
        
        js_next_page = """
        const selector = 'li.cbre-c-pl-pager__next';
        const button = document.querySelector(selector);
        if (button) {
            console.log('Found next page button');
            button.click();
            
        } else {
            console.log('No next page button found');
            return false;
        }
        await new Promise(r => setTimeout(r, 3500));
        """

        self.logger.info("Starting property URL extraction")
        
        session_id = "monte_cbre"
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
            property_links = soup.find_all('a', href=lambda x: x and 'US-SMPL' in x)
            current_page_urls = {f'https://www.cbre.com{link["href"]}' for link in property_links}
            all_property_urls.update(current_page_urls)
            
            self.logger.info(f"Found {len(current_page_urls)} property URLs on page 1")
            
            # Configure pagination
            page_num = 2
            
            while page_num < 220:
                
                # Configure next page request
                config_next = CrawlerRunConfig(
                    session_id=session_id,
                    js_code=js_next_page,
                    js_only=True,
                    wait_for="""js:() => {
                        return document.querySelectorAll('div.CoveoResult').length > 1;
                    }""",
                    cache_mode=CacheMode.BYPASS,
                    simulate_user=True,
                    override_navigator=True,
                    magic=True
                )
                
                # Try to go to next page
                result = await crawler.arun(
                    url=self.start_url, 
                    config=config_next,
                    session_id=session_id
                )
                
                if not result.success:
                    self.logger.error(f"Failed to load page {page_num}: {result.error_message}")
                    break
                
                # Extract URLs from current page
                soup = BeautifulSoup(result.html, 'html.parser')
                property_links = soup.find_all('a', href=lambda x: x and 'US-SMPL' in x)
                current_page_urls = {f'https://www.cbre.com{link["href"]}' for link in property_links}    
                
                all_property_urls.update(current_page_urls)
                self.logger.info(f"Found {len(current_page_urls)} property URLs on page {page_num}")
                print(f"Total unique URLs so far: {len(all_property_urls)}")
                page_num += 1
                next_button = soup.select_one('li.cbre-c-pl-pager__next')
                if next_button and 'cbre-c-pl-pager__disabled' in next_button.get('class', []):
                    print("Next button is disabled - reached end of pagination")
                    break
                                
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
            js_code=js_wait1, 
            override_navigator=True,
        )
        
        # Set up the memory adaptive dispatcher with conservative memory settings
        dispatcher = MemoryAdaptiveDispatcher(
            memory_threshold_percent=80.0, 
            check_interval=0.5,  
            max_session_permit=5,  
            monitor=CrawlerMonitor(
                display_mode=DisplayMode.DETAILED
            )
        )
        
        self.logger.info(f"Starting property detail extraction for {len(urls)} properties")
        all_property_details = []
        
        try:
            # Process results as they stream in
            stream = await crawler.arun_many(
                urls=urls,
                config=run_config,
                dispatcher=dispatcher
            )
            
            try:
                for result in stream:
                    if result.success and result.html:
                        units = self._parse_property_page(result.html, result.url)
                        if units:
                            all_property_details.extend(units)
                    else:
                        self.logger.error(f"Failed to process {result.url}: {result.error_message if hasattr(result, 'error_message') else 'Unknown error'}")
            except Exception as e:
                self.logger.error(f"Error processing stream: {str(e)}", exc_info=True)
            
            self.logger.info(f"Extracted {len(all_property_details)} total units from {len(urls)} properties")
            return all_property_details
        except Exception as e:
            self.logger.error(f"Error extracting property details: {str(e)}", exc_info=True)
            return []

    def _parse_property_page(self, html, url):
        """
        Parse a single property page HTML
        """
        soup = BeautifulSoup(html, 'html.parser')
        units = []
        
        # Extract property name and address
        name_elem = soup.select_one('.cbre-c-pd-header-address-heading')
        if name_elem:
            full_name = name_elem.text.strip()
            # Split on newline if present
            name_parts = full_name.split('\n')
            if len(name_parts) > 1:
                property_name = name_parts[0].strip()
                # Use the part after newline as part of address if present
                street_address = name_parts[1].strip()
            else:
                property_name = full_name
                street_address = ""
        else:
            property_name = ""
            street_address = ""
        
        # Extract city/state/zip
        addr_elem = soup.select_one('.cbre-c-pd-header-address-subheading')
        city_state = addr_elem.text.strip() if addr_elem else ""
        
        # Combine street address with city/state if we have both
        address = f"{street_address}, {city_state}" if street_address else city_state
        
        # Try the standard layout first
        rows = soup.select('.cbre-c-pd-spacesAvailable__mainContent')
        if rows:
            for row in rows:
                name_elem = row.select_one('.cbre-c-pd-spacesAvailable__name')
                area_items = row.select('.cbre-c-pd-spacesAvailable__areaTypeItem')
                
                if name_elem and area_items:
                    space_available = area_items[0].text.strip() if len(area_items) > 0 else ""
                    space_type = area_items[1].text.strip() if len(area_items) > 1 else ""
                    
                    # Extract price
                    price_elem = row.select_one('.cbre-c-pd-spacesAvailable__price')
                    price = price_elem.text.strip() if price_elem else ""
                    
                    unit = {
                        "property_name": property_name,
                        "address": address,
                        "listing_url": url,
                        "floor_suite": name_elem.text.strip(),
                        "space_available": space_available,
                        "price": price,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                    units.append(unit)
        
        # If no standard layout found, try alternative layout
        if not units:
            # Extract space information
            size_section = soup.select_one('.cbre-c-pd-sizeSection__content')
            if size_section:
                space_info_sections = size_section.select('.cbre-c-pd-sizeSection__spaceInfo')
                space_available = ""
                for section in space_info_sections:
                    heading = section.select_one('.cbre-c-pd-sizeSection__spaceInfoHeading')
                    if heading and "Total Space Available" in heading.text:
                        space_text = section.select_one('.cbre-c-pd-sizeSection__spaceInfoText')
                        if space_text:
                            space_available = space_text.text.strip()
                            break
            
            # Extract price information
            price = ""
            # Look specifically for the lease rate section within pricing information content
            pricing_content = soup.select_one('.cbre-c-pd-pricingInformation__content')
            if pricing_content:
                price_sections = pricing_content.select('.cbre-c-pd-pricingInformation__priceInfo')
                for section in price_sections:
                    heading = section.select_one('.cbre-c-pd-pricingInformation__priceInfoHeading')
                    if heading and heading.text.strip() == "Lease Rate":
                        price_text = section.select_one('.cbre-c-pd-pricingInformation__priceInfoText')
                        if price_text:
                            price = price_text.text.strip()
            
            unit = {
                "property_name": property_name,
                "address": address,
                "listing_url": url,
                "floor_suite": "",  # No floor/suite info in alternative layout
                "space_available": space_available,
                "price": price,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            units.append(unit)
        
        return units

def run_scraper():
    """Run the CBRE scraper."""
    scraper = CbreScraper()
    asyncio.run(scraper.scrape())

if __name__ == "__main__":
    run_scraper()