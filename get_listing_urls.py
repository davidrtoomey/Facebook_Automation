from browser_use import Agent 
from browser_use.browser.browser import BrowserProfile, BrowserSession
from browser_use.llm import ChatGoogle
from dotenv import load_dotenv
import os
import asyncio
import re
import json
import time
from urllib.parse import quote_plus
from models import ListingModel, ListingsData
from utils.config_loader import get_gemini_api_key
# from offer_agent import main

load_dotenv()

api_key = get_gemini_api_key()

# Get search configuration from environment variables
search_product = os.getenv('SEARCH_PRODUCT', 'iPhone 13 Pro Max')
search_keywords = os.getenv('SEARCH_KEYWORDS', '').split(',') if os.getenv('SEARCH_KEYWORDS') else []

print(f"Starting search for product: {search_product}")
if search_keywords:
    print(f"Additional keywords: {', '.join(search_keywords)}")

llm = ChatGoogle(model="gemini-2.5-pro-preview-05-06", api_key=api_key)
# llm = ChatGoogle(model="gemini-2.5-flash-lite", api_key=api_key)

browser_profile = BrowserProfile(
	# NOTE: you need to close your chrome browser - so that this can open your browser in debug mode
	executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
	user_data_dir='~/.config/browseruse/profiles/agent',
	headless=True,
    keep_alive=True,
    # Security: Restrict to Facebook domains only - prevent clicking external links
    allowed_domains=['facebook.com', 'www.facebook.com', 'm.facebook.com'],
)

def load_existing_listings(output_path):
    """Load existing listings.json file if it exists."""
    try:
        listings_data = ListingsData.load(output_path)
        print(f"Loaded {len(listings_data)} existing listings from {output_path}")
        return list(listings_data)  # Convert to list for backward compatibility
    except Exception as e:
        print(f"Error loading listings with Pydantic model: {e}")
        # Fallback to traditional loading
        try:
            with open(output_path, "r", encoding="utf-8") as file:
                existing_listings = json.load(file)
            print(f"Loaded {len(existing_listings)} existing listings using fallback method")
            return existing_listings
        except FileNotFoundError:
            print(f"No existing listings file found at {output_path}")
            return []
        except json.JSONDecodeError as e:
            print(f"Error reading existing listings file: {e}")
            return []

def normalize_url(url):
    """Normalize URL by removing tracking parameters to enable proper deduplication."""
    if not url:
        return ""
    
    # For Facebook URLs, standardize to domain + path pattern
    if "facebook.com" in url or url.startswith("/marketplace"):
        # Extract the item ID
        match = re.search(r'(?:facebook\.com)?/marketplace/item/(\d+)', url)
        if match:
            item_id = match.group(1)
            return f"https://www.facebook.com/marketplace/item/{item_id}"
    
    # Default case - just strip query parameters
    base_url = url.split('?')[0]  # Remove all query parameters
    return base_url

def merge_listings(existing_listings, new_listings):
    """Merge new listings with existing ones, preserving messaging data."""
    print(f"Merging {len(new_listings)} new listings with {len(existing_listings)} existing listings")
    
    # Debug print of incoming new listings
    print("New listings to merge:")
    for i, listing in enumerate(new_listings[:5]):  # Show first 5 only
        print(f"  {i+1}. {listing}")
    if len(new_listings) > 5:
        print(f"  ...and {len(new_listings)-5} more")
    
    # Convert existing listings to uniform format (dicts)
    existing_dicts = []
    for listing in existing_listings:
        if isinstance(listing, ListingModel):
            # Convert Pydantic model to dict
            existing_dicts.append(listing.model_dump())
        elif isinstance(listing, dict):
            # Already a dict
            existing_dicts.append(listing)
        else:
            print(f"Skipping unsupported existing listing type: {type(listing)}")
            continue
    
    # Create a mapping of normalized URLs to existing listings
    existing_by_url = {}
    for listing in existing_dicts:
        url = listing.get('url', '')
        normalized_url = normalize_url(url)
        if normalized_url:
            existing_by_url[normalized_url] = listing
    
    # Process new listings
    merged_listings = []
    new_count = 0
    
    # First, add all existing listings
    merged_listings.extend(existing_dicts)
    
    # Then, add only truly new listings
    for new_listing in new_listings:
        if isinstance(new_listing, str):
            new_url = new_listing
            print(f"Processing string URL: {new_url}")
        elif isinstance(new_listing, dict):
            new_url = new_listing.get('url', '')
            print(f"Processing dict URL: {new_url}")
        elif isinstance(new_listing, ListingModel):
            new_url = new_listing.url
            print(f"Processing ListingModel URL: {new_url}")
        else:
            print(f"Skipping unsupported listing type: {type(new_listing)}")
            continue
            
        normalized_new_url = normalize_url(new_url)
        print(f"Normalized URL: {normalized_new_url}")
        
        # Check if this URL already exists
        if normalized_new_url and normalized_new_url not in existing_by_url:
            # This is a new listing
            listing_dict = {
                "url": new_url,
                "messaged": False,
                "messaged_at": None
            }
            merged_listings.append(listing_dict)
            new_count += 1
            print(f"Added new listing: {new_url}")
        else:
            print(f"Skipped duplicate listing: {new_url}")
    
    print(f"Merge complete: {new_count} new listings added, {len(existing_dicts)} existing listings preserved")
    return merged_listings

def extract_listings(raw_data):
    """Extract marketplace listings from raw_data by parsing text between triple backticks."""
    listings = []
    
    # Convert raw_data to string representation
    raw_str = str(raw_data)
    
    # First, try to directly extract marketplace URLs
    url_pattern = r'/marketplace/item/(\d+)/\?'
    marketplace_urls = re.findall(url_pattern, raw_str)
    if marketplace_urls:
        print(f"Found {len(marketplace_urls)} marketplace URLs directly")
        # Debug print of found IDs
        print(f"Found item IDs: {marketplace_urls[:10]}")
        
        # Deduplicate IDs before creating URLs
        unique_ids = list(set(marketplace_urls))
        print(f"After deduplication: {len(unique_ids)} unique IDs")
        
        for item_id in unique_ids:
            url = f"https://www.facebook.com/marketplace/item/{item_id}/"
            # Create listing object with product field
            listing_obj = {
                "url": url,
                "product": search_product,
                "messaged": False,
                "messaged_at": None
            }
            listings.append(listing_obj)
            print(f"Added direct URL: {url}")
        print(f"Total listings after direct extraction: {len(listings)}")
        return listings
    
    # If no direct URLs, try to find JSON content
    pattern = r"```json\s*(.*?)\s*```|```\s*(.*?)\s*```"
    matches = re.findall(pattern, raw_str, re.DOTALL)
    
    # Process each match
    for match in matches:
        json_content = match[0] if match[0] else match[1]  # Take the non-None group
        if json_content:
            # Clean the content: remove literal \\n escape sequences
            json_content_cleaned = json_content.replace('\\n', '').strip()
            
            print("Raw JSON content:", repr(json_content))
            print("Cleaned JSON content:", repr(json_content_cleaned))
            
            try:
                data = json.loads(json_content_cleaned)
                if isinstance(data, dict) and "listings" in data:
                    listings.extend(data["listings"])
                    print(f"Listings (inner try block of extract_listings function): {listings}")
                elif isinstance(data, list):
                    listings.extend(data)
                    print(f"Listings (inner try block of extract_listings function): {listings}")
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON: {e}")
                print("Problematic JSON content (raw):", repr(json_content))
                print("Problematic JSON content (cleaned):", repr(json_content_cleaned))
    
    output_dir="/Users/macbook/Documents/code/buse-test/"
    filename = f"listings.json"
    output_path = os.path.join(output_dir, filename)

    # Load existing listings and merge with new ones
    existing_listings = load_existing_listings(output_path)
    merged_listings = merge_listings(existing_listings, listings)

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(merged_listings, file, indent=4)
    print(f"Merged listings saved to {output_path}")

    return merged_listings

async def main():
    browser_session = BrowserSession(browser_profile=browser_profile)
    
    try:
        # Create agent to navigate to Facebook Marketplace
        agent = Agent(
            task='Navigate to https://www.facebook.com/marketplace',
            llm=llm,
            browser_session=browser_session,
            max_steps=1
        )
        
        # Step 1: Navigate to Facebook
        result = await agent.run()
        print("Step 1 agent result:", result)

        # Step 2: Search for product
        search_query = search_product
        if search_keywords:
            search_query += " " + " ".join(search_keywords)
        
        agent.add_new_task(f'''In the top left of the window under the Marketplace header, in the search input type "{search_query}". Then press enter.''')
        result = await agent.run()
        print("Step 2 agent result:", result)

        # Step 3: Set local pickup only
        agent.add_new_task(f'''Click the "Delivery method" dropdown in the left sidebar and make sure Local pickup is selected. We don't want any shipping listings.''')
        result = await agent.run()
        print("Step 3 agent result:", result)

        # Step 4: Set date filter to last 24 hours
        agent.add_new_task(f'''Click the "Date Listed" dropdown in the left sidebar and make sure Last 24 hours is selected.''')
        result = await agent.run()
        print("Step 4 agent result:", result)

        # Step 5: Scrape listings
        agent.add_new_task(f'''For the first twenty listings scrape the listing url. Do not use screenshots you need to get the listings urls from the webpage. You cannot get the urls from screenshots.''')
        result = await agent.run()

        print("Step 5 agent result:", result)
        print("Agent result type:", type(result))
        
        ####
        # Try to extract listings - handle different result formats
        if isinstance(result, list):
            # If result is already a list, use it directly
            print("\n\n==== USING LIST FORMAT ====")
            print("==== RESULT IS ALREADY A LIST ====\n\n")
            listings = result
        elif isinstance(result, dict):
            # If result is a dict, look for listings key
            print("\n\n==== USING DICTIONARY FORMAT ====")
            print("==== EXTRACTING 'listings' KEY FROM DICTIONARY ====\n\n")
            listings = result.get('listings', [])
        else:
            # If result is a string, try to parse it
            print("\n\n==== USING STRING FORMAT ====")
            print("==== CALLING extract_listings() FUNCTION ====\n\n")
            extract_results = extract_listings(result)
            listings = extract_results
        ####
        print(f"Final listings: {listings}")
        
        # Save to file with merge functionality
        if listings:
            output_path = "/Users/macbook/Documents/code/buse-test/listings.json"
            
            print(f"Found {len(listings)} listings to save")
            # Print a sample of the listings to debug
            for i, listing in enumerate(listings[:5]):
                print(f"Listing {i+1}: {listing}")
            
            # Load existing listings and merge with new ones
            existing_listings = load_existing_listings(output_path)
            
            # Double-check existing listings structure
            print("Existing listings structure check:")
            if existing_listings and len(existing_listings) > 0:
                print(f"First existing item type: {type(existing_listings[0])}")
                if isinstance(existing_listings[0], dict):
                    print(f"First existing item keys: {list(existing_listings[0].keys())}")
            
            # Convert listings to Pydantic models
            pydantic_listings = []
            
            # Check listings structure before merging
            print("New listings structure check:")
            if isinstance(listings, list) and len(listings) > 0:
                print(f"First new item type: {type(listings[0])}")
                # If listings are strings, convert them to ListingModel instances
                if all(isinstance(x, str) for x in listings):
                    print("Converting string listings to ListingModel format")
                    for url in listings:
                        listing_model = ListingModel(url=url, messaged=False, messaged_at=None, product=search_product)
                        listing_model.ensure_full_url()  # Make sure URL has full domain
                        pydantic_listings.append(listing_model)
                # If listings are dicts, convert to ListingModel
                elif all(isinstance(x, dict) for x in listings):
                    for listing_dict in listings:
                        # Ensure product field is set
                        if 'product' not in listing_dict:
                            listing_dict['product'] = search_product
                        listing_model = ListingModel(**listing_dict)
                        listing_model.ensure_full_url()
                        pydantic_listings.append(listing_model)
            
            # Create a new listings data model
            listings_data = ListingsData()
            
            # Add existing listings to model
            for existing in existing_listings:
                if isinstance(existing, dict):
                    listings_data.append(ListingModel(**existing))
                else:
                    listings_data.append(existing)
            
            # Now merge in new listings
            for new_listing in pydantic_listings:
                # Check if this is a duplicate by normalized URL
                normalized_new_url = new_listing.normalize_url()
                
                # Skip if URL already exists
                if any(existing.normalize_url() == normalized_new_url for existing in listings_data):
                    print(f"Skipped duplicate listing: {new_listing.url}")
                    continue
                    
                # This is a new listing, add it
                listings_data.append(new_listing)
                print(f"Added new listing: {new_listing.url}")
            
            # Save using the model's save method
            listings_data.save(output_path)
            print(f"Saved {len(listings_data)} total listings to {output_path}")
        else:
            print("No new listings found to merge")

        # offers_result = await main('listings.json')
        
    finally:
        # Always close the browser session
        print("Closing browser session...")
        await browser_session.close()
        print("Browser session closed.")


if __name__ == "__main__":
    asyncio.run(main())


