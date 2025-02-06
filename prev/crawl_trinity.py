import asyncio
import json
import arrow
from datetime import datetime
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, MemoryAdaptiveDispatcher, CrawlerMonitor, DisplayMode

async def get_iframe_url(url=None):
    """Get the iframe URL from Lee Associates property page."""
    if url is None:
        url = "https://www.trinity-partners.com/listings"
    
    browser_cfg = BrowserConfig(headless=True, verbose=True)
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        js_code=
        """
        async function waitForContent() {
            console.log('Initial wait starting...');
            console.log('Initial wait complete');
            return true;
        }
        return await waitForContent();
        """,
        wait_for="css:#buildout iframe"
    )

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        print(f"Getting iframe URL from {url}...")
        result = await crawler.arun(url=url, config=run_config)
        
        if result.success and result.html:
            soup = BeautifulSoup(result.html, 'html.parser')
            iframe = soup.select_one('#buildout iframe')
            
            if iframe and iframe.get('src'):
                return iframe['src']
    
    return None

async def extract_property_urls():
    start_time = datetime.now()
    
    def log_time(step_name):
        elapsed = datetime.now() - start_time
        print(f"\n[{step_name}] Time elapsed: {elapsed}")
    
    browser_config = BrowserConfig(
        headless=True,
        verbose=True
    )
    
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
        await new Promise(r => setTimeout(r, 1500));
        const select3 = document.getElementById("sortFilter");
        if (select3) {
            // First, deselect the currently selected option
            const selectedOption = select3.querySelector('option[selected="selected"]');
            if (selectedOption) {
                selectedOption.removeAttribute('selected');
            }

            // Then select the Date Updated option
            for (let i = 0; i < select3.options.length; i++) {
                if (select3.options[i].value === "") {
                    select3.options[i].selected = true;
                    select3.options[i].setAttribute('selected', 'selected');
                    const event = new Event('change', { bubbles: true });
                    select3.dispatchEvent(event);
                    console.log("Date Updated selected");
                    break;
                }
            }
        }
        await new Promise(r => setTimeout(r, 5000));
    """
    
    js_next_page = """
        const activeButton = document.querySelector('.js-paginate-btn.active');
        if (activeButton) {
            const nextButton = activeButton.nextElementSibling;
            if (nextButton && nextButton.classList.contains('js-paginate-btn')) {
                nextButton.click();
                console.log("Clicked next page button");
            }
        } else {
            print("No active button found")
        }
        await new Promise(r => setTimeout(r, 1500));
        """
    

    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        try:
            print("\nStarting property URL extraction...")
            
            # Get the iframe URL first
            iframe_url = await get_iframe_url()
            if not iframe_url:
                print("Failed to get iframe URL")
                return
            
            print(f"Got iframe URL: {iframe_url}")
            
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
            last_page_urls = set()
            
            # Get URLs from first page
            soup = BeautifulSoup(result1.html, 'html.parser')
            property_links = soup.find_all('a', href=lambda x: x and 'propertyId' in x)
            current_page_urls = {link['href'] for link in property_links}  # No need to add base URL, it's already there
            all_property_urls.update(current_page_urls)
            print(f"Found {len(current_page_urls)} property URLs on page 1")
            
            page_num = 2
            while True:
                # Store the current page URLs to compare with next page
                last_page_urls = current_page_urls
                
                config_next = CrawlerRunConfig(
                    session_id=session_id,
                    js_code=js_next_page,
                    js_only=True,      
                    cache_mode=CacheMode.BYPASS,
                    wait_for="""js:() => {
                        return document.querySelectorAll('div.result-list-item').length > 1;
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
                paginate_buttons = soup.select('.js-paginate-btn')
                if paginate_buttons:
                    last_button = paginate_buttons[-1]
                    if 'active' in last_button.get('class', []):
                        print("Last page button is active - reached end of pagination")
                        break
            
            # Save URLs to a JSON file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Now extract iframes from each URL
            print("\nExtracting iframes from each property URL...")
            
            # Process all URLs using arun_many with memory adaptive dispatcher
            all_property_details = []
            urls_to_process = list(all_property_urls)
            
            log_time("URL Collection Complete")
            
            # Get all iframe URLs in batches
            print("\nGetting iframe URLs...")
            iframe_urls = []
            
            # Configure for iframe extraction
            iframe_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                wait_for="css:#buildout iframe",
                stream=True  # Process results as they come in
            )
            
            # Set up dispatcher for iframe extraction with more conservative settings
            iframe_dispatcher = MemoryAdaptiveDispatcher(
                memory_threshold_percent=60.0,  # Lower threshold
                check_interval=0.5,  # Check more frequently
                max_session_permit=10,  # Reduce concurrent sessions
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
                        iframe_url = iframe['src'] + '&tab=spaces'
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
                stream=True  # Process results as they come in
            )
            
            # Set up the memory adaptive dispatcher with conservative settings
            dispatcher = MemoryAdaptiveDispatcher(
                memory_threshold_percent=60.0,  # Lower threshold
                check_interval=0.5,  # Check more frequently
                max_session_permit=10,  # Reduce concurrent sessions
                monitor=CrawlerMonitor(
                    display_mode=DisplayMode.DETAILED
                )
            )
            
            print("\nStarting streaming processing of iframe URLs...")
            print(f"Processing {len(iframe_urls)} URLs...")
            
            log_time("Iframe Collection Complete")
            
            # Process results as they stream in
            all_property_details = []
            stream = await crawler.arun_many(
                urls=iframe_urls,
                config=run_config,
                dispatcher=dispatcher
            )
            
            async for result in stream:
                if result.success and result.html:
                    soup = BeautifulSoup(result.html, 'html.parser')
                    print(f"\nProcessing {result.url}")
                    
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
                    units = []
                    for row in soup.select('.js-lease-space-row-toggle.spaces'):
                        cells = row.find_all(['th', 'td'])
                        if len(cells) >= 5:
                            unit = {
                                "property_name": property_name,
                                "address": address,
                                "location": location,
                                "listing_url": f"https://www.lpc.com/properties/properties-search/?propertyId={result.url.split('propertyId=')[1].split('&')[0]}&tab=spaces",
                                "floor_suite": cells[0].text.strip(),
                                "space_available": cells[2].text.strip(),
                                "price": cells[3].text.strip(),
                                "updated_at": arrow.now().format('h:mm:ssA M/D/YY')
                            }
                            units.append(unit)
                    
                    all_property_details.extend(units)
                else:
                    print(f"Failed to process {result.url}: {result.error_message if hasattr(result, 'error_message') else 'Unknown error'}")
            
            # Save all property details to a JSON file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"trinity_properties_{timestamp}.json"
            
            with open(output_file, 'w') as f:
                json.dump(all_property_details, f, indent=2)
            
            print(f"\nExtracted {len(all_property_details)} total units from {len(urls_to_process)} properties")
            print(f"Results saved to {output_file}")
            
            total_time = datetime.now() - start_time
            print(f"\n=== Final Statistics ===")
            print(f"Total Properties Found: {len(urls_to_process)}")
            print(f"Total Iframe URLs: {len(iframe_urls)}")
            print(f"Total Units Extracted: {len(all_property_details)}")
            print(f"Total Time: {total_time}")
            print(f"Average Time per Property: {total_time / len(urls_to_process) if urls_to_process else 0}")
            
            return all_property_details
            
                
        except Exception as e:
            print(f"Error during extraction: {e}")

if __name__ == "__main__":
    # Run the full extraction
    asyncio.run(extract_property_urls())
