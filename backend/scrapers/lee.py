# backend/scrapers/lee.py
from .base import BaseScraper
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, MemoryAdaptiveDispatcher, CrawlerMonitor, DisplayMode
from bs4 import BeautifulSoup
import asyncio
from datetime import datetime

class LeeScraper(BaseScraper):
    def __init__(self):
        super().__init__('lee')
        self.start_url = "https://www.lee-associates.com/properties/"

    async def scrape(self):
        browser_config = BrowserConfig(
            headless=True,
            verbose=True
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            # Get the iframe URL first
            iframe_url = await self._get_iframe_url(crawler)
            if not iframe_url:
                print("Failed to get iframe URL")
                return []

            # Extract property URLs from the iframe
            property_urls = await self._extract_property_urls(crawler, iframe_url)
            
            # Extract details from each property
            all_property_details = await self._extract_property_details(crawler, property_urls)
            
            # Save results
            self.save_results(all_property_details)
            
            return all_property_details

    async def _get_iframe_url(self, crawler):
        """Get the iframe URL from Lee Associates property page."""
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            js_code="""
            async function waitForContent() {
                console.log('Initial wait starting...');
                console.log('Initial wait complete');
                return true;
            }
            return await waitForContent();
            """,
            wait_for="css:#buildout iframe"
        )

        print(f"Getting iframe URL from {self.start_url}...")
        result = await crawler.arun(url=self.start_url, config=run_config)
        
        if result.success and result.html:
            soup = BeautifulSoup(result.html, 'html.parser')
            iframe = soup.select_one('#buildout iframe')
            
            if iframe and iframe.get('src'):
                return iframe['src']
        
        return None

    async def _extract_property_urls(self, crawler, iframe_url):
        # Wait for select element and property cards
        base_wait = """js:() => {
            const select = document.getElementById("q_type_use_offset_eq_any");
            const cards = document.querySelectorAll('.property-card');
            return select !== null || cards.length > 0;
        }"""
        
        # Step 1: Select office type
        select_office = """
            await new Promise(r => setTimeout(r, 3000));
            const select = document.getElementById("q_type_use_offset_eq_any");
            if (select) {
                for (let i = 0; i < select.options.length; i++) {
                    if (select.options[i].value === "1") {
                        select.options[i].selected = true;
                        const event = new Event('change', { bubbles: true });
                        select.dispatchEvent(event);
                        console.log("Office type selected");
                        break;
                    }
                }
            }
            const select2 = document.getElementById("q_sale_or_lease_eq");
            if (select2) {
                for (let i = 0; i < select2.options.length; i++) {
                    if (select2.options[i].value === "lease") {
                        select2.options[i].selected = true;
                        const event = new Event('change', { bubbles: true });
                        select2.dispatchEvent(event);
                        console.log("Lease type selected");
                        break;
                    }
                }
            }
            await new Promise(r => setTimeout(r, 5000));
        """
        
        js_next_page = """
            const selector = 'span.js-next';
            const button = document.querySelector(selector);
            if (button) {
                button.click()
            } else {
                return False    
            };
            await new Promise(r => setTimeout(r, 1500));
        """

        print("\nStarting property URL extraction...")
        session_id = "monte"
        
        # Step 1: Initial load and office selection
        print("Loading page and selecting office type...")
        config1 = CrawlerRunConfig(
            wait_for=base_wait,
            js_code=select_office,
            session_id=session_id,
            cache_mode=CacheMode.BYPASS
        )
        
        result1 = await crawler.arun(
            url=iframe_url,
            config=config1,
            session_id=session_id
        )
        
        # Step 2: Extract URLs using BeautifulSoup
        print("Extracting property URLs...")
        all_property_urls = set()  # Using a set to avoid duplicates
        
        # Get URLs from first page
        soup = BeautifulSoup(result1.html, 'html.parser')
        property_links = soup.find_all('a', href=lambda x: x and 'propertyId' in x)
        current_page_urls = {link['href'] for link in property_links}
        all_property_urls.update(current_page_urls)
        print(f"Found {len(current_page_urls)} property URLs on page 1")
        
        page_num = 2
        while True:
            config_next = CrawlerRunConfig(
                session_id=session_id,
                js_code=js_next_page,
                js_only=True,      
                cache_mode=CacheMode.BYPASS,
                wait_for="""js:() => {
                    return document.querySelectorAll('div.grid-index-card').length > 1;
                }""",
            )
            result2 = await crawler.arun(
                url=iframe_url,
                config=config_next,
                session_id=session_id
            )
            
            soup = BeautifulSoup(result2.html, 'html.parser')
            property_links = soup.find_all('a', href=lambda x: x and 'propertyId' in x)
            current_page_urls = {link['href'] for link in property_links}
            
            all_property_urls.update(current_page_urls)
            print(f"Found {len(current_page_urls)} property URLs on page {page_num}")
            print(f"Total unique URLs so far: {len(all_property_urls)}")
            page_num += 1
            
            # Check if the next button is hidden (display: none)
            next_button = soup.select_one('span.js-next')
            if next_button and next_button.get('style') and 'display: none' in next_button.get('style'):
                print("Next button is hidden - reached end of pagination")
                break

        return list(all_property_urls)

    async def _extract_property_details(self, crawler, urls_to_process):
        # Configure for iframe extraction
        iframe_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            wait_for="css:#buildout iframe",
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
                iframe = soup.select_one('#buildout iframe')
                if iframe and iframe.get('src'):
                    iframe_url = iframe['src']
                    iframe_urls.append(iframe_url)
                    print(f"Found iframe URL from {result.url}")
            else:
                print(f"Failed to get iframe from {result.url}: {result.error_message if hasattr(result, 'error_message') else 'Unknown error'}")
        
        print(f"\nFound {len(iframe_urls)} iframe URLs out of {len(urls_to_process)} properties")
        
        if not iframe_urls:
            print("No iframe URLs found")
            return []
        
        # Create a run config for property details extraction
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            wait_for="css:.pdt-header1, .pdt-header2, .js-lease-space-row-toggle",
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
        all_property_details = []
        stream = await crawler.arun_many(
            urls=iframe_urls,
            config=run_config,
            dispatcher=dispatcher
        )
        
        async for result in stream:
            if result.success and result.html:
                try:
                    units = self._parse_property_page(result.html, result.url)
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
        """Parse a single property page HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        units = []
        
        # Extract property name
        name_elem = soup.select_one('.pdt-header1 h1')
        property_name = name_elem.text.strip() if name_elem else ""
        
        # Extract address and location
        addr_elem = soup.select_one('.pdt-header2 h2')
        if addr_elem:
            addr_text = addr_elem.text.strip()
            if '|' in addr_text:
                # Case 1: Property has a name, address contains street and city
                addr_parts = addr_text.split('|')
                address = addr_parts[0].strip()
                location = addr_parts[1].strip()
            else:
                # Case 2: Property name is the address, and h2 contains city/state
                address = property_name
                location = addr_text
        else:
            address = property_name
            location = ""
        
        # Extract unit details from table
        for row in soup.select('.js-lease-space-row-toggle.spaces'):
            cells = row.find_all(['th', 'td'])
            if len(cells) >= 5:
                # Extract propertyId, address, and officeId from the URL
                url_parts = url.split('?')[1].split('&')
                params = {}
                for part in url_parts:
                    if '=' in part:
                        key, value = part.split('=')
                        params[key] = value
                
                # Construct the new URL format
                new_url = f"https://www.lee-associates.com/properties/?propertyId={params.get('propertyId', '')}&address={params.get('address', '')}&officeId={params.get('officeId', '')}&tab=spaces"
                
                unit = {
                    "property_name": property_name,
                    "address": address,
                    "location": location,
                    "listing_url": new_url,
                    "floor_suite": cells[0].text.strip(),
                    "space_available": cells[2].text.strip(),
                    "price": cells[3].text.strip(),
                    "updated_at": datetime.now().strftime('%I:%M:%S%p %m/%d/%y')
                }
                units.append(unit)
        
        return units

async def run_scraper():
    scraper = LeeScraper()
    results = await scraper.scrape()
    print(f"Scraped {len(results)} properties")

if __name__ == "__main__":
    asyncio.run(run_scraper())
