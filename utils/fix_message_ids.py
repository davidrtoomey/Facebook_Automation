#!/usr/bin/env python3
"""
Fix malformed message IDs in messages.json

This script cleans up message IDs that have embedded "CONVERSATION_URL_END" markers
and other malformed data, ensuring they contain only the actual Facebook message thread ID.

@file purpose: Clean up malformed message IDs in messages.json
"""

import json
import re
import sys
import os

# Add parent directory to path to import models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import MessagesData, load_messages_json, save_messages_json, extract_message_id_from_url

def fix_malformed_message_ids():
    """Fix all malformed message IDs in messages.json"""
    print("🔧 Loading messages.json...")
    
    # Load existing data
    messages_data = load_messages_json()
    print(f"📊 Found {len(messages_data.conversations)} conversations")
    
    fixed_count = 0
    
    for i, conv in enumerate(messages_data.conversations):
        # Fix null status values
        if conv.status is None:
            conv.status = "new"
            print(f"🔄 Fixed null status for conversation {i+1}")
            fixed_count += 1
            
        if conv.message_id:
            # Extract clean message ID from the stored message_id
            clean_message_id = extract_message_id_from_url(conv.message_id)
            
            if clean_message_id != conv.message_id:
                print(f"🔄 Fixing conversation {i+1}:")
                print(f"   Old: {conv.message_id}")
                print(f"   New: {clean_message_id}")
                
                conv.message_id = clean_message_id
                fixed_count += 1
        else:
            # If no message_id, extract from URL
            if conv.conversation_url:
                clean_message_id = extract_message_id_from_url(conv.conversation_url)
                if clean_message_id:
                    print(f"🆕 Adding missing message ID for conversation {i+1}: {clean_message_id}")
                    conv.message_id = clean_message_id
                    fixed_count += 1
    
    if fixed_count > 0:
        print(f"💾 Saving {fixed_count} fixes to messages.json...")
        save_messages_json(messages_data)
        print("✅ Fixed malformed message IDs!")
    else:
        print("✅ No malformed message IDs found!")
    
    return fixed_count

if __name__ == "__main__":
    print("🚀 Starting message ID cleanup...")
    fixed_count = fix_malformed_message_ids()
    print(f"🎉 Complete! Fixed {fixed_count} message IDs.")