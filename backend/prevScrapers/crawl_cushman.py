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
    
    js_wait1 = """
        await new Promise(r => setTimeout(r, 1500));
        """
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        try:
            print("\nStarting property URL extraction...")
            
            session_id = "monte_cushmanwakefield"
            current_url = 'https://www.cushmanwakefield.com/en/united-states/properties/lease/lease-property-search#sort=%40propertylastupdateddate%20descending&f:PropertyType=[Office]&f:Country=[United%20States]'
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
                remove_overlay_elements=True,
                magic=True
            )
            result1 = await crawler.arun(
                url=current_url,
                config=config_first,
                session_id=session_id
            )
            
            soup = BeautifulSoup(result1.html, 'html.parser')
            property_links = soup.find_all('a', href=lambda x: x and 'properties/for-lease/office' in x)
            current_page_urls = {f'{link["href"]}' for link in property_links}
            all_property_urls.update(current_page_urls)
            print(f"Found {len(current_page_urls)} property URLs on page 1")
            
            page_num = 1
            while True:
                # Store the current page URLs to compare with next page
                last_page_urls = current_page_urls
                
                # Check for next button and if it's disabled
                next_li = soup.find('li', {'class': 'coveo-pager-next'})
                if not next_li or 'coveo-pager-list-item-disabled' in next_li.get('class', []):
                    print("Next button is disabled - reached end of pagination")
                    break
                
                config_next = CrawlerRunConfig(
                    # session_id=session_id,
                    js_code=js_wait1,
                    # js_only=True,      
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
                    url=f'https://www.cushmanwakefield.com/en/united-states/properties/lease/lease-property-search#first={page_num * 12}&sort=%40propertylastupdateddate%20ascending&f:PropertyType=[Office]&f:Country=[United%20States]',
                    config=config_next,
                    # session_id=session_id
                )
                
                soup = BeautifulSoup(result2.html, 'html.parser')
                property_links = soup.find_all('a', href=lambda x: x and 'properties/for-lease/office' in x)
                current_page_urls = {f'{link["href"]}' for link in property_links}
                
                all_property_urls.update(current_page_urls)
                print(f"Found {len(current_page_urls)} property URLs on page {page_num}")
                print(f"Total unique URLs so far: {len(all_property_urls)}")
                page_num += 1
            
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
                page_timeout=300000,
                stream=True  # Process results as they come in
            )
            
            # Set up the memory adaptive dispatcher with more conservative memory settings
            dispatcher = MemoryAdaptiveDispatcher(
                memory_threshold_percent=60.0,  # Lower threshold to be more conservative
                check_interval=0.5,  # Check more frequently
                max_session_permit=5,  # Reduce concurrent sessions
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
                try:
                    soup = BeautifulSoup(result.html, 'html.parser')
                    
                    # Extract property name and address
                    title_div = soup.find('div', {'class': 'updated-page-title'})
                    if title_div:
                        property_name = title_div.find('h1', {'class': 'updated-page-title-main'})
                        property_name = property_name.text.strip() if property_name else "N/A"
                        
                        address = title_div.find('h5', {'class': 'updated-page-title-sub'})
                        address = address.text.strip() if address else "N/A"
                    else:
                        property_name = "N/A"
                        address = "N/A"
                    
                    units = []
                    
                    # Look for multiple availability containers
                    availability_containers = soup.find_all('div', {'class': 'availabilities-container-parent'})
                    if availability_containers:
                        for container in availability_containers:
                            # Extract floor/suite info
                            title_div = container.find('div', {'class': 'blue-color-title-div'})
                            if title_div:
                                floor = title_div.find('b', {'class': 'font-bold'})
                                floor = floor.text.strip() if floor else ""
                                suite = title_div.find('span', string=lambda x: x and 'Suite' in x)
                                suite = suite.text.strip() if suite else ""
                                floor_suite = f"{floor} {suite}".strip()
                            else:
                                floor_suite = "N/A"
                            
                            # Extract space and price
                            desc_divs = container.find_all('div', {'class': 'availabilities-second-level-description'})
                            space_available = "Contact for Details"
                            price = "Contact for Details"
                            
                            for div in desc_divs:
                                label = div.find('p', {'class': 'm-1'})
                                if not label:
                                    continue
                                    
                                value = div.find('b', {'class': 'bold-font'})
                                if not value:
                                    continue
                                    
                                label_text = label.text.strip()
                                value_text = value.text.strip()
                                
                                if 'Available Space' in label_text:
                                    space_available = value_text
                                elif 'Rental Price' in label_text:
                                    price = value_text
                            
                            unit = {
                                "property_name": property_name,
                                "address": address,
                                "listing_url": result.url,
                                "floor_suite": floor_suite,
                                "space_available": space_available,
                                "price": price,
                                "updated_at": arrow.now().format('h:mm:ssA M/D/YY')
                            }
                            units.append(unit)
                    
                    # If no availability containers found, try single space info
                    if not units:
                        # Extract details like price and space
                        details_div = soup.find('div', {'class': 'mix_propertyStatistics'})
                        price = "Contact for Details"
                        space_min = "N/A"
                        space_max = "N/A"
                        available_space = None
                        
                        if details_div:
                            # Extract price and space
                            dt_elements = details_div.find_all('dt')
                            dd_elements = details_div.find_all('dd')
                            
                            for dt, dd in zip(dt_elements, dd_elements):
                                dt_text = dt.text.strip()
                                dd_text = dd.text.strip()
                                
                                if 'Rental Price' in dt_text:
                                    price = dd_text
                                elif 'Available Space' in dt_text:
                                    available_space = dd_text
                                elif 'Min Divisible' in dt_text:
                                    space_min = dd_text
                                elif 'Max Contiguous' in dt_text:
                                    space_max = dd_text
                        
                        # Create space available text - prefer range if available, otherwise use single value
                        if space_min != "N/A" and space_max != "N/A":
                            space_available = f"{space_min} - {space_max}"
                        elif available_space:
                            space_available = available_space
                        else:
                            space_available = "Contact for Details"
                        
                        unit = {
                            "property_name": property_name,
                            "address": address,
                            "listing_url": result.url,
                            "floor_suite": "N/A",
                            "space_available": space_available,
                            "price": price,
                            "updated_at": arrow.now().format('h:mm:ssA M/D/YY')
                        }
                        units.append(unit)
                    
                    all_property_details.extend(units)
                    print(f"Processed: {property_name} - Found {len(units)} units")
                    
                except Exception as e:
                    print(f"Error processing property: {str(e)}")
                    import traceback
                    print(traceback.format_exc())
            
            
            print(f"\nExtracted {len(all_property_details)} total units from {len(urls_to_process)} properties")            
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