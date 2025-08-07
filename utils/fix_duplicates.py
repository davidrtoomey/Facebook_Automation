#!/usr/bin/env python3
# @file purpose: Fixes duplicate URLs in listings.json

import json
import re
from datetime import datetime

def extract_item_id(url):
    """
    Extract the marketplace item ID from a Facebook Marketplace URL.
    
    Args:
        url (str): The full Facebook Marketplace URL
        
    Returns:
        str: The item ID if found, or the full URL if no ID is found
    """
    # Pattern to match /marketplace/item/ITEM_ID/ in the URL
    pattern = r'/marketplace/item/(\d+)'
    match = re.search(pattern, url)
    
    if match:
        return match.group(1)
    
    # Return the full URL if no item ID is found (for non-marketplace URLs)
    return url

def fix_duplicates(input_file='listings.json', output_file=None, auto_replace=False):
    """
    Deduplicates listings.json by marketplace item ID and ensures consistent messaged status.
    Also removes URLs that redirect to backmarket.com.
    
    Args:
        input_file (str): Path to input listings.json file
        output_file (str): Path to output file (if None and auto_replace is True, overwrites input_file)
        auto_replace (bool): If True, automatically replace the original file without prompting
    """
    print(f"Loading listings from {input_file}...")
    with open(input_file, 'r') as f:
        listings = json.load(f)
    
    print(f"Found {len(listings)} total listings")
    
    # Track item IDs to handle duplicates
    id_to_listing = {}
    backmarket_count = 0
    
    # First pass - find all unique item IDs and preserve the messaged=True status
    for item in listings:
        if not isinstance(item, dict):
            continue
            
        url = item.get('url', '')
        if not url:
            continue
        
        # Skip URLs that redirect to backmarket.com
        if 'backmarket.com' in url:
            backmarket_count += 1
            continue
        
        # Extract the item ID from the URL
        item_id = extract_item_id(url)
        
        # Skip if we couldn't extract an ID and it's not a valid URL
        if not item_id:
            continue
            
        # If this item ID already exists, keep the messaged=True status if either has it
        if item_id in id_to_listing:
            existing = id_to_listing[item_id]
            
            # If either existing or current item has messaged=True, keep it as True
            messaged = existing.get('messaged', False) or item.get('messaged', False)
            
            # Keep the earliest non-null messaged_at timestamp if available
            existing_time = existing.get('messaged_at')
            new_time = item.get('messaged_at')
            
            if existing_time and new_time:
                messaged_at = existing_time if existing_time < new_time else new_time
            else:
                messaged_at = existing_time or new_time
            
            # Keep all other fields from the item with the most information
            # This preserves conversation IDs and other important metadata
            if len(item) > len(existing) or ('message_id' in item and 'message_id' not in existing):
                # Copy all fields from newer item first (except status fields)
                for key, value in item.items():
                    if key not in ['messaged', 'messaged_at']:
                        existing[key] = value
            
            # Always update the status fields
            existing['messaged'] = messaged
            existing['messaged_at'] = messaged_at
            
            # Keep the original URL if it has the message_id
            if not existing.get('message_id') and item.get('message_id'):
                existing['url'] = url
            
        else:
            # This is a new item ID, add it to our dictionary
            id_to_listing[item_id] = {
                "url": url,
                "messaged": item.get('messaged', False),
                "messaged_at": item.get('messaged_at')
            }
            
            # Copy all other fields
            for key, value in item.items():
                if key not in ['url', 'messaged', 'messaged_at']:
                    id_to_listing[item_id][key] = value
    
    # Convert back to a list and assign sequential IDs
    deduplicated = list(id_to_listing.values())
    
    # Assign unique sequential IDs to each listing for easy tracking
    for i, listing in enumerate(deduplicated, start=1):
        listing['listing_id'] = i
    
    print(f"Reduced to {len(deduplicated)} unique listings")
    print(f"Removed {len(listings) - len(deduplicated) - backmarket_count} duplicates")
    print(f"Removed {backmarket_count} backmarket.com URLs")
    print(f"Assigned sequential IDs 1-{len(deduplicated)} to all listings")
    
    # Check for messaged listings
    messaged_count = sum(1 for item in deduplicated if item.get('messaged'))
    print(f"Found {messaged_count} listings with messaged=True")
    
    # If auto_replace is True or no output file specified, write directly to input file
    if auto_replace or output_file is None:
        with open(input_file, 'w') as f:
            json.dump(deduplicated, f, indent=4)
        print(f"Updated {input_file} with deduplicated listings")
    else:
        # Write to specified output file
        with open(output_file, 'w') as f:
            json.dump(deduplicated, f, indent=4)
        print(f"Deduplicated listings saved to {output_file}")
        
        # Interactive mode - ask user to replace original
        replace = input(f"Replace original {input_file} with deduplicated version? (y/n): ")
        if replace.lower() == 'y':
            with open(input_file, 'w') as f:
                json.dump(deduplicated, f, indent=4)
            print(f"Original {input_file} replaced with deduplicated version")
    
    return deduplicated

if __name__ == "__main__":
    fix_duplicates()
    print("Done!")