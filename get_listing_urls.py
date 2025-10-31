from browser_use import Agent
from browser_use.browser.browser import BrowserProfile, BrowserSession
from browser_use.llm import ChatGoogle
from dotenv import load_dotenv
import os
import asyncio
import re
import json

load_dotenv()

api_key = os.getenv('GEMINI_API_KEY')
search_product = os.getenv('SEARCH_PRODUCT', 'iPhone 13 Pro Max')
search_keywords = os.getenv('SEARCH_KEYWORDS', '').split(',') if os.getenv('SEARCH_KEYWORDS') else []

llm = ChatGoogle(model="gemini-2.5-pro-preview-05-06", api_key=api_key)

browser_profile = BrowserProfile(
    executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    user_data_dir='~/.config/browseruse/profiles/agent',
    headless=True,
    keep_alive=True,
    allowed_domains=['facebook.com', 'www.facebook.com', 'm.facebook.com'],
)

def merge_listings(existing, new):
    existing_by_url = {url.split('?')[0].replace('www.', ''): listing for listing in existing if (url := listing.get('url'))}
    merged = existing[:]
    for new_url in new:
        clean_url = new_url.split('?')[0].replace('www.', '')
        if clean_url not in existing_by_url:
            merged.append({"url": new_url, "messaged": False, "messaged_at": None})
    return merged

async def main():
    browser_session = BrowserSession(browser_profile=browser_profile)
    try:
        agent = Agent(task='Navigate to https://www.facebook.com/marketplace', llm=llm, browser_session=browser_session, max_steps=1)
        await agent.run()

        search_query = search_product + (" " + " ".join(search_keywords) if search_keywords else "")
        agent.add_new_task(f'In the top left under Marketplace header, type "{search_query}" in search input and press enter.')
        await agent.run()

        agent.add_new_task('Click "Delivery method" dropdown in left sidebar and select Local pickup.')
        await agent.run()

        agent.add_new_task('Click "Date Listed" dropdown in left sidebar and select Last 24 hours.')
        await agent.run()

        agent.add_new_task('Scrape URLs for first twenty listings from webpage.')
        result = await agent.run()

        url_pattern = r'/marketplace/item/(\d+)/\?'
        item_ids = set(re.findall(url_pattern, str(result)))
        listings = [f"https://www.facebook.com/marketplace/item/{item_id}/" for item_id in item_ids]

        output_path = "/Users/macbook/Documents/code/buse-test/listings.json"
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            existing = []

        merged = merge_listings(existing, listings)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=4)
    finally:
        await browser_session.close()

if __name__ == "__main__":
    asyncio.run(main())
