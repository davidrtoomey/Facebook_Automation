from browser_use.llm import ChatGoogle
from pydantic import SecretStr
from browser_use import Agent
from browser_use.browser.browser import BrowserProfile, BrowserSession
from dotenv import load_dotenv
import os
import asyncio
import json
import re
import time
from datetime import datetime
from utils.config_loader import get_gemini_api_key, get_config_value, load_full_config
from utils.pricing_manager import get_offer_price
load_dotenv()
api_key = get_gemini_api_key()

# Simplified config loading: Prioritize config.json, fallback to env
full_config = load_full_config() or {}
search_products = full_config.get('search_products', [])
if not search_products:
    search_product = os.getenv('SEARCH_PRODUCT', 'iPhone 13 Pro Max')
    search_products = [{"name": search_product}]

all_products_config = search_products
print(f"✅ Loaded {len(all_products_config)} configured products")

# Extract pricing from first product or defaults
first_product = all_products_config[0] if all_products_config else {}
base_offer_unlocked = first_product.get('base_offer_unlocked', int(os.getenv('BASE_OFFER_UNLOCKED', '300')))
base_offer_locked = first_product.get('base_offer_locked', int(os.getenv('BASE_OFFER_LOCKED', '250')))
base_offer_unlocked_damaged = first_product.get('base_offer_unlocked_damaged', int(os.getenv('BASE_OFFER_UNLOCKED_DAMAGED', '150')))
base_offer_locked_damaged = first_product.get('base_offer_locked_damaged', int(os.getenv('BASE_OFFER_LOCKED_DAMAGED', '100')))
price_flexibility = int(get_config_value('price_flexibility') or os.getenv('PRICE_FLEXIBILITY', '20'))

# Config summary (simplified)
print("=" * 60)
print("🔧 CONFIGURATION SUMMARY")
print("=" * 60)
print(f"🎯 Products: {', '.join(p.get('name', str(p)) for p in all_products_config)}")
print(f"💰 Default pricing - Unlocked: ${base_offer_unlocked}, Locked: ${base_offer_locked}")
print(f"🔧 Damaged pricing - Unlocked: ${base_offer_unlocked_damaged}, Locked: ${base_offer_locked_damaged}")
print(f"📊 Price flexibility: ${price_flexibility}")
print("✅ Configuration validation passed" if api_key else "❌ Missing API key")
print("=" * 60)

if not api_key:
    raise ValueError("Gemini API key required")

llm = ChatGoogle(model="gemini-2.5-pro", api_key=api_key)
# llm = ChatGoogle(model="gemini-2.5-flash-lite", api_key=api_key)
browser_profile = BrowserProfile(
    executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    user_data_dir='~/.config/browseruse/profiles/agent',
    headless=False,
    # headless=(get_config_value('browser_headless') or os.getenv('HEADLESS_OFFERS', 'true')).lower() == 'true',
    keep_alive=True,
    allowed_domains=['facebook.com', 'www.facebook.com', 'm.facebook.com', 'docs.google.com', 'sheets.googleapis.com'],
)

def get_sqlite_manager():
    from utils.sqlite_manager import SQLiteStateManager
    manager = SQLiteStateManager()
    # Migrate only if not done (add a migrated flag in DB)
    if not manager.is_migrated():
        manager.migrate_from_json('listings.json')
        manager.set_migrated()
    return manager

async def process_single_url(browser_session, listing_item, index):
    url = listing_item['url']
    listing_id = listing_item.get('listing_id')
    
    if listing_item.get('messaged'):
        return {"url": url, "status": "skipped", "message_sent": False}
    
    try:
        # Single agent does everything
        agent = Agent(
            task=f'''Navigate to {url}. 
If listing unavailable/sold/error → report "UNAVAILABLE"
If not iPhone → report "NOT_IPHONE" 
If already messaged → report "ALREADY_MESSAGED"
Otherwise extract: TITLE:[title] SELLER:[name] DESC:[description]''',
            initial_actions=[{'go_to_url': {'url': url, 'new_tab': False}}],
            llm=llm,
            browser_session=browser_session,
        )
        
        result = str(await agent.run()).lower()
        sqlite_manager = get_sqlite_manager()
        
        # Handle skip conditions
        if "unavailable" in result:
            sqlite_manager.update_listing(listing_id, {'unavailable': True})
            return {"url": url, "status": "skipped", "message_sent": False}
        if "not_iphone" in result:
            sqlite_manager.update_listing(listing_id, {'relevant': False})
            return {"url": url, "status": "skipped", "message_sent": False}
        if "already_messaged" in result:
            sqlite_manager.update_listing(listing_id, {'messaged': True})
            return {"url": url, "status": "skipped", "message_sent": False}
        
        # Extract data
        title = re.search(r'title:\s*(.+?)(?:\n|seller:|desc:|$)', result, re.IGNORECASE)
        title = title.group(1).strip() if title else "Unknown"
        
        desc = re.search(r'desc:\s*(.+?)(?:\n|$)', result, re.IGNORECASE)  
        desc = desc.group(1).strip() if desc else ""
        
        # Get offer
        offer = get_offer_price(title, desc)
        if not offer or not offer.get('offer_price'):
            return {"url": url, "status": "skipped", "message_sent": False}
        
        # Send message
        message = ("Hi, can you tell me more about the damage?" 
                  if offer['grade'] in ['grade_d', 'doa'] 
                  else f"Hi I can do ${offer['offer_price']} cash for it")
        
        agent.add_new_task(f'Click message button. Clear the existing text from the message input then type exactly "{message}". Send.')
        message_result = await agent.run()
        
        # Update database
        sent = "sent" in str(message_result).lower()
        updates = {'messaged': sent, 'title': title}
        
        seller = re.search(r'seller:\s*(.+?)(?:\n|desc:|$)', result, re.IGNORECASE)
        if seller:
            updates['seller_name'] = seller.group(1).strip()
        
        sqlite_manager.update_listing(listing_id, updates)
        return {"url": url, "status": "completed" if sent else "error", "message_sent": sent}
        
    except:
        return {"url": url, "status": "error", "message_sent": False}

async def main():
    print("Starting Facebook Marketplace messaging bot...")

    browser_session = BrowserSession(browser_profile=browser_profile)

    try:
        sqlite_manager = get_sqlite_manager()
        print("📊 Loading listings from SQLite database...")
        unmessaged_listings = sqlite_manager.get_unmessaged_listings(limit=50)
        print(f"Found {len(unmessaged_listings)} unmessaged listings")

        if not unmessaged_listings:
            print("🎉 No unmessaged listings found.")
            return

        results = []
        messages_sent_count = 0
        MAX_MESSAGES_PER_SESSION = 10
        delay = 10.0  # Start with 10s

        for i, listing_item in enumerate(unmessaged_listings):
            if messages_sent_count >= MAX_MESSAGES_PER_SESSION:
                break

            result = await process_single_url(browser_session, listing_item, i)
            results.append(result)

            if result.get('message_sent'):
                messages_sent_count += 1

            if i < len(unmessaged_listings) - 1:
                await asyncio.sleep(delay)
                delay = min(delay * 1.1, 20.0) if 'error' in result['status'] else delay  # Adaptive

        # Summary (simplified)
        successful = sum(1 for r in results if r.get('message_sent'))
        skipped = sum(1 for r in results if r['status'] == 'skipped')
        failed = len(results) - successful - skipped
        print(f"\n📊 Final Results: Successful: {successful}, Skipped: {skipped}, Failed: {failed}")

    finally:
        await browser_session.close()

if __name__ == "__main__":
    asyncio.run(main())
