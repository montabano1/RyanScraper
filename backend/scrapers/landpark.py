# backend/scrapers/landpark.py
from .base import BaseScraper
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, MemoryAdaptiveDispatcher, CrawlerMonitor, DisplayMode
from bs4 import BeautifulSoup
import asyncio
from datetime import datetime

class LandParkScraper(BaseScraper):
    def __init__(self):
        super().__init__('landpark')
        self.start_url = 'https://properties.landparkco.com/'

    async def scrape(self):
        browser_config = BrowserConfig(
            headless=True,  # Changed from False to True for production
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

        async with AsyncWebCrawler(config=browser_config) as crawler:
            # Extract property URLs and their iframes
            property_urls, iframe_urls, url_mapping = await self._extract_property_urls(crawler)
            
            # Extract details from each property's iframe
            all_property_details = await self._extract_property_details(crawler, iframe_urls, url_mapping)
            
            # Return results (base class will handle saving)
            return all_property_details

    async def _extract_property_urls(self, crawler):
        select_office = """
        await new Promise(r => setTimeout(r, 3000));
        const select = document.querySelector('select[name="property-type"]');
        if (select) {
            for (let i = 0; i < select.options.length; i++) {
                if (select.options[i].value === "55") {
                    select.options[i].selected = true;
                    const event = new Event('change', { bubbles: true });
                    select.dispatchEvent(event);
                    console.log("Office type selected");
                    break;
                }
            }
        }
        const select2 = document.querySelector('select[name="offering-type"]');
        if (select2) {
            for (let i = 0; i < select2.options.length; i++) {
                if (select2.options[i].value === "54") {
                    select2.options[i].selected = true;
                    const event = new Event('change', { bubbles: true });
                    select2.dispatchEvent(event);
                    console.log("Lease type selected");
                    break;
                }
            }
        }
        await new Promise(r => setTimeout(r, 3500));
        """

        print("\nStarting property URL extraction...")
        
        session_id = "monte"
        current_url = self.start_url

        print("Extracting property URLs...")
        all_property_urls = set()
        
        config_first = CrawlerRunConfig(
            session_id=session_id,
            js_code=select_office,
            css_selector='div.grid',
            cache_mode=CacheMode.BYPASS,
            page_timeout=60000,
            simulate_user=True,
            override_navigator=True,
            magic=True
        )
        result1 = await crawler.arun(
            url=current_url,
            config=config_first,
            session_id=session_id
        )
        
        soup = BeautifulSoup(result1.html, 'html.parser')
        property_links = soup.find_all('a', href=lambda x: x and '/properties/' in x)
        current_page_urls = {f'{link["href"]}' for link in property_links}
        all_property_urls.update(current_page_urls)
        print(f"Found {len(current_page_urls)} property URLs")
        
        urls_to_process = list(all_property_urls)
        
        # Get all iframe URLs
        print("\nGetting iframe URLs...")
        iframe_urls = []
        url_mapping = {}  # Map iframe URLs to original URLs
        
        # Configure for iframe extraction
        iframe_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            wait_for="css:#iframe",
            stream=True
        )
        
        # Set up dispatcher for iframe extraction
        iframe_dispatcher = MemoryAdaptiveDispatcher(
            memory_threshold_percent=60.0,
            check_interval=0.5,
            max_session_permit=10,
            monitor=CrawlerMonitor(
                display_mode=DisplayMode.DETAILED
            )
        )
        
        print("\nStarting streaming processing of URLs for iframe extraction...")
        print(f"Processing {len(urls_to_process)} URLs...")
        
        # Get iframes using streaming
        iframe_stream = await crawler.arun_many(
            urls=urls_to_process,
            config=iframe_config,
            dispatcher=iframe_dispatcher
        )
        
        # Process iframe results as they come in
        iframe_urls = []
        async for result in iframe_stream:
            if result.success and result.html:
                soup = BeautifulSoup(result.html, 'html.parser')
                iframe = soup.select_one('#iframe')
                if iframe and iframe.get('src'):
                    iframe_url = iframe['src']
                    iframe_urls.append(iframe_url)
                    url_mapping[iframe_url] = result.url  # Store the mapping
                    print(f"Found iframe URL from {result.url}")
            else:
                print(f"Failed to get iframe from {result.url}: {result.error_message if hasattr(result, 'error_message') else 'Unknown error'}")
        
        print(f"\nFound {len(iframe_urls)} iframe URLs out of {len(urls_to_process)} properties")
        
        return urls_to_process, iframe_urls, url_mapping

    async def _extract_property_details(self, crawler, iframe_urls, url_mapping):
        all_property_details = []
        
        if not iframe_urls:
            print("No iframe URLs found")
            return []
        
        # Create a run config for property details extraction
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            page_timeout=60000,
            js_code="""await new Promise(r => setTimeout(r, 500));""",
            stream=True
        )
        
        # Set up the memory adaptive dispatcher
        dispatcher = MemoryAdaptiveDispatcher(
            memory_threshold_percent=60.0,
            check_interval=0.5,
            max_session_permit=10,
            monitor=CrawlerMonitor(
                display_mode=DisplayMode.DETAILED
            )
        )
        
        print("\nStarting streaming processing of iframe URLs...")
        print(f"Processing {len(iframe_urls)} URLs...")
        
        # Process results as they stream in
        stream = await crawler.arun_many(
            urls=iframe_urls,
            config=run_config,
            dispatcher=dispatcher
        )
        
        async for result in stream:
            if result.success and result.html:
                try:
                    original_url = url_mapping.get(result.url, result.url)
                    units = self._parse_property_page(result.html, original_url)
                    if units:
                        print(f"Successfully extracted {len(units)} units")
                        all_property_details.extend(units)
                    else:
                        print("WARNING: No units extracted from this property")
                except Exception as e:
                    print(f"Error processing {result.url}: {str(e)}")
            else:
                print(f"Failed to process {result.url}: {result.error_message if hasattr(result, 'error_message') else 'Unknown error'}")
        
        print(f"\nExtracted {len(all_property_details)} total units")
        return all_property_details

    def _parse_property_page(self, html, url):
        """
        Parse a single property page HTML
        """
        soup = BeautifulSoup(html, 'html.parser')
        units = []
        
        # Extract property name and address from hero__text
        hero_div = soup.select_one('div.hero__text')
        
        name_elem = hero_div.select_one('h1.hero__title') if hero_div else None
        property_name = name_elem.text.strip() if name_elem else ""
        
        address_elem = hero_div.select_one('h2.hero__sub-title') if hero_div else None
        address = address_elem.text.strip() if address_elem else ""
        
        # If no property name is found, use the address as the name
        if not property_name and address:
            property_name = address

        # Find all availability cards
        availability_cards = soup.select('div.availability-card-v2')
        
        if availability_cards:
            for card in availability_cards:
                unit_name_elem = card.select_one('div.availability-card-name h3')
                unit_name = unit_name_elem.text.strip() if unit_name_elem else "N/A"
                
                rent_elem = card.select_one('div.availability-card-rent h3')
                price = rent_elem.text.strip() if rent_elem else "Contact for pricing"
                
                # Find space size
                space_elem = card.select_one('div.availability-card-info-item:has(span:contains("Total Size")) p.availability-card-info-item-value')
                space_available = space_elem.text.strip() if space_elem else "Contact for Details"
                
                unit = {
                    "property_name": property_name,
                    "address": address,
                    "listing_url": url,
                    "floor_suite": unit_name,
                    "space_available": space_available,
                    "price": price,
                    "updated_at": datetime.now().strftime('%I:%M:%S%p %m/%d/%y')
                }
                units.append(unit)
        else:
            # Create a single entry with N/A for floor_suite if no availability cards found
            unit = {
                "property_name": property_name,
                "address": address,
                "listing_url": url,
                "floor_suite": "N/A",
                "space_available": "Contact for Details",
                "price": "Contact for pricing",
                "updated_at": datetime.now().strftime('%I:%M:%S%p %m/%d/%y')
            }
            units.append(unit)
        
        return units

async def run_scraper():
    scraper = LandParkScraper()
    results = await scraper.scrape()
    print(f"Scraped {len(results)} properties")

if __name__ == "__main__":
    asyncio.run(run_scraper())
