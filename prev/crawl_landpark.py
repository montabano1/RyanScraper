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
        headless=False,
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
    

    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        try:
            print("\nStarting property URL extraction...")
            
            session_id = "monte"
            current_url = 'https://properties.landparkco.com/'


            # Step 2: Extract URLs using BeautifulSoup
            print("Extracting property URLs...")
            all_property_urls = set()  # Using a set to avoid duplicates
            last_page_urls = set()
            
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
            print(f"Found {len(current_page_urls)} property URLs on page 1")
            
           
            # Save URLs to a JSON file
            timestamp = arrow.now().format('YYYYMMDD_HHmmss')
            
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
                wait_for="css:#iframe",
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
            url_mapping = {}  # Map iframe URLs to original URLs
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
            
            if not iframe_urls:
                print("No iframe URLs found")
                return []
            
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
                urls=iframe_urls,
                config=run_config,
                dispatcher=dispatcher
            )
            async for result in stream:
                if result.success and result.html:
                    soup = BeautifulSoup(result.html, 'html.parser')
                    original_url = url_mapping.get(result.url, result.url)  # Get original URL from mapping
                    print(f"\nProcessing {original_url}")
                    
                    try:
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
                                    "listing_url": original_url,  # Use the original URL here
                                    "floor_suite": unit_name,
                                    "space_available": space_available,
                                    "price": price,
                                    "updated_at": arrow.now().format('h:mm:ssA M/D/YY')
                                }
                                all_property_details.append(unit)
                            
                            print(f"Successfully extracted {len(availability_cards)} units")
                        else:
                            # Create a single entry with N/A for floor_suite if no availability cards found
                            unit = {
                                "property_name": property_name,
                                "address": address,
                                "listing_url": original_url,  # Use the original URL here
                                "floor_suite": "N/A",
                                "space_available": "Contact for Details",
                                "price": "Contact for pricing",
                                "updated_at": arrow.now().format('h:mm:ssA M/D/YY')
                            }
                            all_property_details.append(unit)
                            print("WARNING: No units extracted from this property")
                            
                    except Exception as e:
                        print(f"Error processing {result.url}: {str(e)}")
                else:
                    print(f"Failed to process {result.url}: {result.error_message if hasattr(result, 'error_message') else 'Unknown error'}")
            
            # Save all property details to a JSON file
            timestamp = arrow.now().format('YYYYMMDD_HHmmss')
            output_file = f"landpark_properties_{timestamp}.json"
            
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
