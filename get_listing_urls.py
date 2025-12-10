from browser_use import Agent
from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.llm import ChatGoogle
from dotenv import load_dotenv
import os
import asyncio
import re
from urllib.parse import quote

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
search_product = os.getenv("SEARCH_PRODUCT", "iPhone 13 Pro Max")
search_keywords = (
    os.getenv("SEARCH_KEYWORDS", "").split(",") if os.getenv("SEARCH_KEYWORDS") else []
)

llm = ChatGoogle(model="gemini-2.5-pro-preview-05-06", api_key=api_key)

browser_profile = BrowserProfile(
    executable_path="/usr/bin/chromium",
    user_data_dir="/home/david/.config/browseruse/profiles/agent",
    headless=os.getenv("HEADLESS_OFFERS", "true").lower() == "true",
    keep_alive=True,
    allowed_domains=["facebook.com", "www.facebook.com", "m.facebook.com"],
    chromium_sandbox=False,
    args=[
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-blink-features=AutomationControlled",
    ],
)


def build_marketplace_url(search_term):
    """Build Facebook Marketplace search URL with proper encoding."""
    encoded_term = quote(search_term)
    return f"https://www.facebook.com/marketplace/search?daysSinceListed=1&deliveryMethod=local_pick_up&query={encoded_term}&exact=false"


def extract_listing_id(url):
    """Extract numeric listing ID from Facebook Marketplace URL."""
    match = re.search(r"/marketplace/item/(\d+)", url)
    return int(match.group(1)) if match else None


def save_listings_to_db(listing_urls):
    """Save listings directly to SQLite database."""
    from utils.sqlite_manager import SQLiteStateManager

    manager = SQLiteStateManager()
    added = 0
    skipped = 0

    for url in listing_urls:
        listing_id = extract_listing_id(url)
        if not listing_id:
            continue

        try:
            # Try to add - will skip if already exists due to UNIQUE constraint
            manager.add_listing(
                url, listing_id=listing_id, messaged=False, product=search_product
            )
            added += 1
        except Exception:
            # Listing already exists
            skipped += 1

    print(f"✅ Added {added} new listings, skipped {skipped} existing")

    # Sync to JSON for GUI compatibility
    manager.export_to_json()

    return added


async def main():
    search_query = search_product + (
        " " + " ".join(search_keywords) if search_keywords else ""
    )
    marketplace_url = build_marketplace_url(search_query)

    print(f"🔍 Searching for: {search_query}")
    print(f"🌐 URL: {marketplace_url}")

    browser_session = BrowserSession(browser_profile=browser_profile)
    try:
        agent = Agent(
            task=f"""Navigate to {marketplace_url}.
            Goal: Extract URLs for "{search_product}" listings.
            
            Instructions:
            1. Scrape ALL listing URLs that match the search term "{search_product}" in the main results section.
            2. Scroll down gently to load more local results. Do this at least 3-4 times to ensure all local listings are visible.
            3. CRITICAL: STOP scraping immediately if you see headers like "Results from outside your search", "More picks for you", or "Suggested for you".
            4. Do NOT scrape listings from those "outside search" or "suggested" sections. They are irrelevant.
            5. It is okay if you only find a few listings (e.g. 1-5). Quality is more important than quantity.
            6. Return the list of relevant URLs found.""",
            llm=llm,
            browser_session=browser_session,
            max_steps=5,
        )
        result = await agent.run()

        url_pattern = r"/marketplace/item/(\d+)/\?"
        item_ids = set(re.findall(url_pattern, str(result)))
        listings = [
            f"https://www.facebook.com/marketplace/item/{item_id}/"
            for item_id in item_ids
        ]

        print(f"📋 Found {len(listings)} listings")

        if listings:
            save_listings_to_db(listings)
        else:
            print("⚠️ No listings found")

    finally:
        await browser_session.stop()


if __name__ == "__main__":
    asyncio.run(main())
