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

def clean_corrupted_field(value, field_name=""):
    """Clean corrupted fields that contain ActionResult metadata."""
    if not value or not isinstance(value, str):
        return value

    # Check if this is corrupted data (contains ActionResult, extracted_content, etc.)
    corruption_markers = [
        'ActionResult', 'extracted_content=', 'is_done=', 'all_model_outputs=',
        'include_in_memory=', 'metadata=None', 'JudgementResult', 'long_term_memory='
    ]

    is_corrupted = any(marker in value for marker in corruption_markers)

    if not is_corrupted:
        # Still check for overly long values that might be partially corrupted
        if len(value) > 200:
            # Try to extract just the first part before escaped newlines
            if '\\n' in value:
                value = value.split('\\n')[0].strip()
        return value

    # Try to extract clean value from corrupted data
    # Look for patterns like "SELLER_NAME: Mark\nPRODUCT_NAME:"
    if field_name == "seller_name":
        # Extract just the name before any \n or metadata
        match = re.match(r'^([^\\]+?)(?:\\n|$)', value)
        if match:
            extracted = match.group(1).strip()
            # Don't return if it still looks corrupted
            if len(extracted) < 50 and 'ActionResult' not in extracted:
                return extracted
        return None  # Reset corrupted field

    elif field_name == "product_name":
        # Try to find product name pattern
        match = re.search(r'PRODUCT_NAME:\s*([^\\]+?)(?:\\n|$)', value)
        if match:
            extracted = match.group(1).strip()
            if len(extracted) < 100 and 'ActionResult' not in extracted:
                return extracted
        # Otherwise try first part
        match = re.match(r'^([^\\]+?)(?:\\n|$)', value)
        if match:
            extracted = match.group(1).strip()
            if len(extracted) < 100 and 'ActionResult' not in extracted:
                return extracted
        return None

    elif field_name == "last_message":
        # Try to find the actual last message
        match = re.search(r'LAST_MESSAGE:\s*([^\\]+?)(?:\\n|$)', value)
        if match:
            extracted = match.group(1).strip()
            if len(extracted) < 200 and 'ActionResult' not in extracted:
                return extracted
        return None

    # Default: try to get first part before corruption
    if '\\n' in value:
        first_part = value.split('\\n')[0].strip()
        if len(first_part) < 100 and not any(m in first_part for m in corruption_markers):
            return first_part

    return None  # Reset if can't clean

def fix_messages_json():
    """Fix malformed URLs and corrupted fields in messages.json file."""
    try:
        # Load the existing messages.json file
        with open('messages.json', 'r') as f:
            data = json.load(f)

        # Track fixes
        url_fixed = 0
        fields_fixed = 0
        conversations_reset = 0

        # Process each conversation
        if 'conversations' in data:
            for i, conv in enumerate(data['conversations']):
                # Fix URL
                if 'conversation_url' in conv:
                    original_url = conv['conversation_url']
                    cleaned_url = clean_url(original_url)

                    if cleaned_url and cleaned_url != original_url:
                        data['conversations'][i]['conversation_url'] = cleaned_url
                        url_fixed += 1
                        print(f"Fixed URL: {original_url[:50]}... -> {cleaned_url}")

                # Fix corrupted seller_name
                if 'seller_name' in conv and conv['seller_name']:
                    original = conv['seller_name']
                    cleaned = clean_corrupted_field(original, 'seller_name')
                    if cleaned != original:
                        data['conversations'][i]['seller_name'] = cleaned
                        fields_fixed += 1
                        print(f"Fixed seller_name: '{original[:40]}...' -> '{cleaned}'")

                # Fix corrupted product_name
                if 'product_name' in conv and conv['product_name']:
                    original = conv['product_name']
                    cleaned = clean_corrupted_field(original, 'product_name')
                    if cleaned != original:
                        data['conversations'][i]['product_name'] = cleaned
                        fields_fixed += 1
                        print(f"Fixed product_name: '{original[:40]}...' -> '{cleaned}'")

                # Fix corrupted last_message
                if 'last_message' in conv and conv['last_message']:
                    original = conv['last_message']
                    cleaned = clean_corrupted_field(original, 'last_message')
                    if cleaned != original:
                        data['conversations'][i]['last_message'] = cleaned
                        fields_fixed += 1
                        print(f"Fixed last_message: '{original[:40]}...' -> '{cleaned}'")

                # Reset status to "awaiting_response" for conversations stuck at "new"
                # that have valid URLs (so they get re-processed)
                if conv.get('status') == 'new' and clean_url(conv.get('conversation_url')):
                    data['conversations'][i]['status'] = 'awaiting_response'
                    conversations_reset += 1

                # Check and fix suspicious offer_amounts
                # If offer_amount is too high (>350), it's likely the seller's counter, not our offer
                current_offer = conv.get('offer_amount')
                if current_offer and current_offer > 350:
                    print(f"Resetting suspicious offer_amount: ${current_offer} (too high, likely seller's counter)")
                    data['conversations'][i]['offer_amount'] = None
                    current_offer = None

                # If offer_amount is too low (<100), it's likely corrupted
                if current_offer and current_offer < 100:
                    print(f"Resetting suspicious offer_amount: ${current_offer} (too low, likely corrupted)")
                    data['conversations'][i]['offer_amount'] = None
                    current_offer = None

                # Populate offer_amount from message history if missing
                # Only use our specific offer pattern to avoid capturing wrong prices
                if not current_offer:
                    for msg in conv.get('message_history', []):
                        if msg.get('from') == 'us':
                            msg_text = msg.get('message', '')
                            # Only match "I can do $X" pattern - our standard offer format
                            offer_match = re.search(r'(?:I can do|can do)\s*\$(\d+)', msg_text, re.IGNORECASE)
                            if offer_match:
                                offer_price = int(offer_match.group(1))
                                # Sanity check - our offers should be between $100-$350
                                if 100 <= offer_price <= 350:
                                    data['conversations'][i]['offer_amount'] = offer_price
                                    print(f"Populated offer_amount from message history: ${offer_price}")
                                break

                # Fix corrupted message_ids (e.g., "1257391523080087\\nCONVERSATION_URL_")
                message_id = conv.get('message_id', '')
                if message_id and ('\\n' in message_id or '\n' in message_id or len(message_id) > 30):
                    # Extract just the numeric part
                    clean_id_match = re.match(r'^(\d+)', message_id)
                    if clean_id_match:
                        cleaned_id = clean_id_match.group(1)
                        data['conversations'][i]['message_id'] = cleaned_id
                        print(f"Fixed corrupted message_id: '{message_id[:30]}...' -> '{cleaned_id}'")

                # Mark conversations with closing phrases as "closed"
                closing_phrases = [
                    "Thanks for letting me know",
                    "If it falls through",
                    "let me know if anything changes",
                    "my offer will still stand",
                ]
                last_message = conv.get('last_message') or ''
                current_status = conv.get('status', '')
                if last_message and current_status not in ['closed', 'deal_completed', 'deal_pending']:
                    for phrase in closing_phrases:
                        if phrase.lower() in last_message.lower():
                            data['conversations'][i]['status'] = 'closed'
                            print(f"Marked conversation as closed (closing phrase detected): {last_message[:40]}...")
                            break

        # Update the last_updated timestamp
        data['last_updated'] = datetime.now().isoformat()

        # Save the cleaned data back to messages.json
        with open('messages.json', 'w') as f:
            json.dump(data, f, indent=2)

        print(f"\n✅ Cleanup complete:")
        print(f"   - Fixed {url_fixed} URLs")
        print(f"   - Fixed {fields_fixed} corrupted fields")
        print(f"   - Reset {conversations_reset} conversations from 'new' to 'awaiting_response'")
        print(f"   - Total conversations: {len(data.get('conversations', []))}")

    except Exception as e:
        print(f"Error fixing messages.json: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

if __name__ == "__main__":
    print("Starting URL cleanup in messages.json...")
    fix_messages_json()