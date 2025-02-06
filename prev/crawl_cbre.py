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
    
    js_next_page = """
        const selector = 'li.cbre-c-pl-pager__next';
        const button = document.querySelector(selector);
        if (button) {
            console.log('found button')
            button.click()
        } else {
            console.log('no button')
            return False    
        };
        """
    

    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        try:
            print("\nStarting property URL extraction...")
            
            session_id = "monte"
            current_url = 'https://www.cbre.com/properties/properties-for-lease/commercial-space?sort=lastupdated%2Bdescending&propertytype=Office&transactiontype=isLetting&initialpolygon=%5B%5B67.12117833969766%2C-28.993985994685787%5D%2C%5B-26.464978515643416%2C-141.84554849468577%5D%5D'

            # Step 2: Extract URLs using BeautifulSoup
            print("Extracting property URLs...")
            all_property_urls = set()  # Using a set to avoid duplicates
            last_page_urls = set()
            
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
            result1 = await crawler.arun(
                url=current_url,
                config=config_first,
                session_id=session_id
            )
            
            soup = BeautifulSoup(result1.html, 'html.parser')
            property_links = soup.find_all('a', href=lambda x: x and 'US-SMPL' in x)
            current_page_urls = {f'https://www.cbre.com{link["href"]}' for link in property_links}
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
                        return document.querySelectorAll('div.CoveoResult').length > 1;
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
                property_links = soup.find_all('a', href=lambda x: x and 'US-SMPL' in x)
                current_page_urls = {f'https://www.cbre.com{link["href"]}' for link in property_links}
                
                all_property_urls.update(current_page_urls)
                print(f"Found {len(current_page_urls)} property URLs on page {page_num}")
                print(f"Total unique URLs so far: {len(all_property_urls)}")
                page_num += 1
                # Check if the next button is disabled
                next_button = soup.select_one('li.cbre-c-pl-pager__next')
                if next_button and 'cbre-c-pl-pager__disabled' in next_button.get('class', []):
                    print("Next button is disabled - reached end of pagination")
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
                stream=True  # Process results as they come in
            )
            
            # Set up the memory adaptive dispatcher with more conservative memory settings
            dispatcher = MemoryAdaptiveDispatcher(
                memory_threshold_percent=60.0,  # Lower threshold to be more conservative
                check_interval=0.5,  # Check more frequently
                max_session_permit=25,  # Reduce concurrent sessions
                monitor=CrawlerMonitor(
                    display_mode=DisplayMode.DETAILED
                )
            )
            
            print("\nStarting streaming processing of URLs...")
            
            log_time("URL Collection Complete")
            
            # Process results as they stream in
            stream = await crawler.arun_many(
                urls=all_property_urls,
                config=run_config,
                dispatcher=dispatcher
            )
            async for result in stream:
                if result.success and result.html:
                    soup = BeautifulSoup(result.html, 'html.parser')
                    
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
                    
                    # Extract unit details
                    units = []
                    
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
                                    "listing_url": result.url,
                                    "floor_suite": name_elem.text.strip(),
                                    "space_available": space_available,
                                    "price": price,
                                    "updated_at": arrow.now().format('h:mm:ssA M/D/YY')
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
                            "listing_url": result.url,
                            "floor_suite": "",  # No floor/suite info in alternative layout
                            "space_available": space_available,
                            "price": price,
                            "updated_at": arrow.now().format('h:mm:ssA M/D/YY')
                        }
                        units.append(unit)
                    
                    all_property_details.extend(units)
                else:
                    print(f"Failed to process {result.url}: {result.error_message if hasattr(result, 'error_message') else 'Unknown error'}")
            
            # Save all property details to a JSON file
            timestamp = arrow.now().format('YYYYMMDD_HHmmss')
            output_file = f"cbre_properties_{timestamp}.json"
            
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
