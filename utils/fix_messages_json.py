#!/usr/bin/env python3

import json
import re
from datetime import datetime

def clean_url(url):
    """Clean a Facebook message URL to ensure it's properly formatted."""
    if not url:
        return None
    
    # First remove any escaped newlines and text after them
    if '\\n' in url:
        url = url.split('\\n')[0]
    
    # Remove any actual newlines and text after them
    if '\n' in url:
        url = url.split('\n')[0]
    
    # Try to extract a valid Facebook message URL pattern
    url_match = re.search(r'(https?://(?:www\.)?facebook\.com/messages/t/[^/\s\n"\'<>]+/?)', url)
    if url_match:
        return url_match.group(1)
    return None

def fix_messages_json():
    """Fix malformed URLs in messages.json file."""
    try:
        # Load the existing messages.json file
        with open('messages.json', 'r') as f:
            data = json.load(f)
        
        # Track how many URLs were fixed
        fixed_count = 0
        
        # Process each conversation to clean URLs
        if 'conversations' in data:
            for i, conv in enumerate(data['conversations']):
                if 'conversation_url' in conv:
                    original_url = conv['conversation_url']
                    cleaned_url = clean_url(original_url)
                    
                    if cleaned_url and cleaned_url != original_url:
                        data['conversations'][i]['conversation_url'] = cleaned_url
                        fixed_count += 1
                        print(f"Fixed URL: {original_url[:50]}... -> {cleaned_url}")
        
        # Update the last_updated timestamp
        data['last_updated'] = datetime.now().isoformat()
        
        # Save the cleaned data back to messages.json
        with open('messages.json', 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n✅ Fixed {fixed_count} URLs in messages.json")
        print(f"Total conversations: {len(data.get('conversations', []))}")
        
    except Exception as e:
        print(f"Error fixing messages.json: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Starting URL cleanup in messages.json...")
    fix_messages_json()