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

llm = ChatGoogle(model="gemini-3-flash-preview", api_key=api_key)
# llm = ChatGoogle(model="gemini-2.5-pro", api_key=api_key)

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


def is_relevant_listing(title, search_term):
    """Check if a listing title is relevant to the search term."""
    if not title:
        return False

    title_lower = title.lower()
    search_lower = search_term.lower()

    # Extract key parts of the search term (e.g., "iPhone 13 Pro Max" -> ["iphone", "13", "pro", "max"])
    search_parts = search_lower.split()

    # For iPhone searches, check for the model number at minimum
    if "iphone" in search_lower:
        # Must contain "iphone" and the model number (e.g., "13", "14", "15")
        if "iphone" not in title_lower:
            return False

        # Check for model number
        model_numbers = [p for p in search_parts if p.isdigit() or p in ["se", "xr", "xs", "x"]]
        if model_numbers:
            if not any(num in title_lower for num in model_numbers):
                return False

        # If searching for "Pro Max", "Pro", or "Plus", check for those too
        if "pro max" in search_lower and "pro max" not in title_lower:
            return False
        elif "pro" in search_lower and "max" not in search_lower and "pro" not in title_lower:
            return False
        elif "plus" in search_lower and "plus" not in title_lower:
            return False
    else:
        # For non-iPhone searches, require at least 2 key words to match
        matches = sum(1 for part in search_parts if part in title_lower and len(part) > 2)
        if matches < 2:
            return False

    return True


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
            Goal: Find listings for "{search_product}" ONLY.

            Instructions:
            1. Look at the listings on the page
            2. Scroll down 2-3 times to load more results
            3. For EACH listing, check if the title contains "{search_product}"
            4. ONLY report listings that ACTUALLY match "{search_product}"

            IMPORTANT - Be VERY selective:
            - ONLY include listings where the title clearly mentions "{search_product}"
            - DO NOT include random phones, accessories, or unrelated items
            - DO NOT include listings from "Results from outside your search" section
            - DO NOT include listings from "Suggested for you" section

            Return format - For each matching listing, report:
            LISTING: [exact title] | URL: [full URL]

            Example:
            LISTING: iPhone 13 Pro Max 256GB Unlocked | URL: https://facebook.com/marketplace/item/123456/

            If NO listings match "{search_product}", just say "NO_MATCHING_LISTINGS" and stop.""",
            llm=llm,
            browser_session=browser_session,
            max_steps=10,
        )
        result = await agent.run()

        result_str = str(result)
        print(f"📄 Agent output preview: {result_str[:500]}...")

        # Extract listings with titles from structured format
        listing_pattern = r"LISTING:\s*([^|]+)\s*\|\s*URL:\s*(https?://[^\s]+)"
        structured_matches = re.findall(listing_pattern, result_str, re.IGNORECASE)

        # Also try to extract any marketplace URLs as fallback
        url_pattern = r"/marketplace/item/(\d+)"
        all_item_ids = set(re.findall(url_pattern, result_str))

        listings = []

        # First, use structured matches (title + URL) with relevance check
        for title, url in structured_matches:
            title = title.strip()
            if is_relevant_listing(title, search_product):
                item_id = extract_listing_id(url)
                if item_id:
                    clean_url = f"https://www.facebook.com/marketplace/item/{item_id}/"
                    if clean_url not in listings:
                        listings.append(clean_url)
                        print(f"✅ Relevant: {title[:50]}...")
            else:
                print(f"❌ Filtered out (not relevant): {title[:50]}...")

        # If no structured matches, fall back to URL extraction but be cautious
        if not listings and all_item_ids:
            print(f"⚠️ No structured matches, found {len(all_item_ids)} raw URLs - skipping unverified URLs")
            # Don't blindly add unverified URLs - they're likely irrelevant

        print(f"📋 Found {len(listings)} relevant listings for '{search_product}'")

        if listings:
            save_listings_to_db(listings)
        else:
            print(f"⚠️ No relevant listings found for '{search_product}'")

    finally:
        await browser_session.stop()


if __name__ == "__main__":
    asyncio.run(main())
