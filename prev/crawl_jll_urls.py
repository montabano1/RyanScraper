import asyncio
import json
import arrow
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, MemoryAdaptiveDispatcher, CrawlerMonitor, DisplayMode

async def extract_property_urls():
    start_time = arrow.now()
    
    def log_time(step_name):
        elapsed = arrow.now() - start_time
        print(f"\n[{step_name}] Time elapsed: {elapsed}")
    
    browser_config = BrowserConfig(
        headless=True,
        verbose=True,
        viewport_height=1080,
        viewport_width=1920,
        ignore_https_errors=True,  # Handle HTTPS errors
        extra_args=['--disable-web-security'],  # Disable CORS checks
        headers={
            'sec-fetch-site': 'same-origin',  # Only allow same-origin requests
            'sec-fetch-mode': 'navigate',
            'sec-fetch-dest': 'document'
        }
    )
    
    js_wait = """
        await new Promise(r => setTimeout(r, 5000));
        """
    
    js_wait1 = """
        await new Promise(r => setTimeout(r, 500));
        """
    
    js_next_page = """
        const lastLi = document.querySelector('nav[role="navigation"] ul li:last-child');
        const svg = lastLi ? lastLi.querySelector('svg.h-6.text-jllRed') : null;
        if (svg && svg.querySelector('path[d*="8.22"]')) {
            console.log('found next button')
            lastLi.querySelector('button').click()
            return true;
        }
        console.log('next button not found')
        return false;
    """
    

    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        try:
            print("\nStarting property URL extraction...")
            
            session_id = "monte"
            current_url = 'https://property.jll.com/search?tenureType=rent&propertyTypes=office&orderBy=desc&sortBy=dateModified'
            # Step 2: Extract URLs using BeautifulSoup
            print("Extracting property URLs...")
            all_property_urls = set()  # Using a set to avoid duplicates
            last_page_urls = set()
            
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
            result1 = await crawler.arun(
                url=current_url,
                config=config_first,
                session_id=session_id
            )
            
            soup = BeautifulSoup(result1.html, 'html.parser')
            property_links = soup.find_all('a', href=lambda x: x and 'listings/' in x)
            current_page_urls = {f'https://property.jll.com{link["href"]}' for link in property_links}
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
                    wait_for="""js:() => {
                        return document.querySelectorAll('div[data-cy="property-card"].relative').length > 1;
                    }""",
                    cache_mode=CacheMode.BYPASS,
                    page_timeout=60000,
                    simulate_user=True,
                    override_navigator=True,
                    magic=True
                )
                result2 = await crawler.arun(
                    url=current_url,
                    config=config_next,
                    session_id=session_id
                )
                
                soup = BeautifulSoup(result2.html, 'html.parser')
                property_links = soup.find_all('a', href=lambda x: x and 'listings/' in x)
                current_page_urls = {f'https://property.jll.com{link["href"]}' for link in property_links}
                
                # Check if the next button exists - it should be the last li with an SVG inside
                
                
                all_property_urls.update(current_page_urls)
                print(f"Found {len(current_page_urls)} property URLs on page {page_num}")
                print(f"Total unique URLs so far: {len(all_property_urls)}")
                page_num += 1
                last_li = soup.select_one('nav[role="navigation"] ul li:last-child')
                next_button = last_li and last_li.find('svg', class_='h-6 text-jllRed')
                if not (next_button and next_button.find('path', {'d': lambda x: x and '8.22' in x})):
                    print("Next button not found - reached end of pagination")
                    break
            
            # Save URLs to a JSON file
            timestamp = arrow.now().format('YYYYMMDD_HHmmss')
                        
            # Process all URLs using arun_many with memory adaptive dispatcher
            all_property_details = []
            urls_to_process = list(all_property_urls)
            
            log_time("URL Collection Complete")
            for link in all_property_urls:
                print(link)
            
            # Create a run config for property details extraction with streaming enabled
            run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                page_timeout=60000,
                js_code=js_wait1,
                stream=True  # Process results as they come in
            )
            
            print("\nStarting streaming processing of URLs...")
            print(f"Processing {len(all_property_urls)} URLs...")
            
            # Set up the memory adaptive dispatcher with more conservative memory settings
            dispatcher = MemoryAdaptiveDispatcher(
                memory_threshold_percent=60.0,  # Lower threshold to be more conservative
                check_interval=0.5,  # Check more frequently
                max_session_permit=10,  # Reduce concurrent sessions
                monitor=CrawlerMonitor(
                    display_mode=DisplayMode.DETAILED
                )
            )
            
            # Process results as they stream in
            stream = await crawler.arun_many(
                urls=all_property_urls,
                config=run_config,
                dispatcher=dispatcher
            )
            async for result in stream:
                if result.success and result.html:
                    soup = BeautifulSoup(result.html, 'html.parser')
                    print(f"\nProcessing {result.url}")
                    
                    try:
                        # Extract property name and price from header
                        header_div = soup.select_one('div.mb-6.flex.flex-col')
                        
                        name_elem = header_div.select_one('h1.MuiTypography-root.jss6') if header_div else None
                        property_name = name_elem.text.strip() if name_elem else ""
                        
                        # Extract price from header (more reliable location)
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
                        
                        address = f"{street_address}, {city_state}" if street_address else city_state
                        
                        # First get the top-level space info
                        space_text = None
                        space_li = soup.select_one('ul.flex.flex-wrap li span.text-lg.text-neutral-700 span')
                        if space_li:
                            space_text = space_li.text.strip()

                        units = []  # Initialize units list at the top
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
                                                if parent_row:
                                                    if parent_row not in rows:
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
                                            "listing_url": result.url,
                                            "floor_suite": floor_text,
                                            "space_available": row_space_text,
                                            "price": price,
                                            "updated_at": arrow.now().format('h:mm:ssA M/D/YY')
                                        }
                                        units.append(unit)
                            else:
                                # Create a single entry with N/A for floor_suite
                                unit = {
                                    "property_name": property_name,
                                    "address": address,
                                    "listing_url": result.url,
                                    "floor_suite": "N/A",
                                    "space_available": space_text or "Contact for Details",
                                    "price": price,
                                    "updated_at": arrow.now().format('h:mm:ssA M/D/YY')
                                }
                                units.append(unit)
                        else:
                            # Create a single entry with N/A for floor_suite
                            unit = {
                                "property_name": property_name,
                                "address": address,
                                "listing_url": result.url,
                                "floor_suite": "N/A",
                                "space_available": space_text or "Contact for Details",
                                "price": price,
                                "updated_at": arrow.now().format('h:mm:ssA M/D/YY')
                            }
                            units.append(unit)
                        
                        # Add all extracted units to the main list
                        if units:
                            print(f"Successfully extracted {len(units)} units")
                            all_property_details.extend(units)
                        else:
                            print("WARNING: No units extracted from this property")
                    except Exception as e:
                        print(f"Error processing property: {str(e)}")
                        import traceback
                        print(traceback.format_exc())
                else:
                    print(f"Failed to process {result.url}: {result.error_message if hasattr(result, 'error_message') else 'Unknown error'}")
            
            # Save all property details to a JSON file
            timestamp = arrow.now().format('YYYYMMDD_HHmmss')
            output_file = f"jll_properties_{timestamp}.json"
            
            with open(output_file, 'w') as f:
                json.dump(all_property_details, f, indent=2)
            
            print(f"\nExtracted {len(all_property_details)} total units from {len(urls_to_process)} properties")
            print(f"Results saved to {output_file}")
            
            total_time = arrow.now() - start_time
            print(f"\n=== Final Statistics ===")
            print(f"Total Properties Found: {len(urls_to_process)}")
            print(f"Total Units Extracted: {len(all_property_details)}")
            print(f"Total Time: {total_time}")
            print(f"Average Time per Property: {total_time / len(urls_to_process) if urls_to_process else 0}")
            
            return all_property_details
            
                
        except Exception as e:
            print(f"Error during extraction: {e}")

if __name__ == "__main__":
    # Run the full extraction
    asyncio.run(extract_property_urls())
