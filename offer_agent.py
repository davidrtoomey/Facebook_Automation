from browser_use.llm import ChatGoogle
from pydantic import SecretStr
from browser_use import Agent
from browser_use.browser import BrowserProfile, BrowserSession
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
search_products = full_config.get("search_products", [])
if not search_products:
    search_product = os.getenv("SEARCH_PRODUCT", "iPhone 13 Pro Max")
    search_products = [{"name": search_product}]

all_products_config = search_products
print(f"✅ Loaded {len(all_products_config)} configured products")


if not api_key:
    raise ValueError("Gemini API key required")

llm = ChatGoogle(model="gemini-3-flash-preview", api_key=api_key)
# llm = ChatGoogle(model="gemini-2.5-pro", api_key=api_key)
browser_profile = BrowserProfile(
    executable_path="/usr/bin/chromium",
    user_data_dir="/home/david/.config/browseruse/profiles/agent",
    headless=False,
    # headless=(get_config_value('browser_headless') or os.getenv('HEADLESS_OFFERS', 'true')).lower() == 'true',
    keep_alive=True,
    allowed_domains=[
        "facebook.com",
        "www.facebook.com",
        "m.facebook.com",
        "docs.google.com",
        "sheets.googleapis.com",
    ],
)


def get_sqlite_manager():
    from utils.sqlite_manager import SQLiteStateManager

    return SQLiteStateManager()


async def process_single_url(browser_session, listing_item, index):
    url = listing_item["url"]
    listing_id = listing_item.get("listing_id")

    if listing_item.get("messaged"):
        print(f"  ⏭️ Already messaged, skipping")
        return {"url": url, "status": "skipped", "message_sent": False}

    try:
        print(f"  🤖 Creating agent for listing...")
        # Navigate to the URL first
        await browser_session.navigate_to(url)

        # Then create agent to analyze the page
        agent = Agent(
            task=f"""You are on a Facebook Marketplace listing page.
1. Check if listing is unavailable/sold/error. If so, return exactly "STATUS: UNAVAILABLE"
2. Check if item is NOT an iPhone (e.g. case, box, Android). If so, return exactly "STATUS: NOT_IPHONE" 
3. Check if we already messaged (view message button). If so, return exactly "STATUS: ALREADY_MESSAGED"

4. If none of the above, extract details in this format:
   TITLE: [title]
   SELLER: [name]
   DESC: [description]
""",
            llm=llm,
            browser_session=browser_session,
        )

        print(f"  🚀 Running agent to check listing...")
        result = str(
            await agent.run()
        )  # Don't lower() yet to preserve casing for parsing if needed, but we can lower() for checks
        result_lower = result.lower()
        print(f"  📝 Agent result received")
        sqlite_manager = get_sqlite_manager()

        # Handle skip conditions using stricter checks
        if "status: unavailable" in result_lower:
            print("  ⚠️ Detected unavailable status")
            sqlite_manager.update_listing(listing_id, {"unavailable": True})
            sqlite_manager.export_to_json()
            return {"url": url, "status": "skipped", "message_sent": False}

        if "status: not_iphone" in result_lower:
            print("  ⚠️ Detected not_iphone status")
            sqlite_manager.update_listing(listing_id, {"relevant": False})
            sqlite_manager.export_to_json()
            return {"url": url, "status": "skipped", "message_sent": False}

        if "status: already_messaged" in result_lower:
            print("  ⚠️ Detected already_messaged status")
            sqlite_manager.update_listing(listing_id, {"messaged": True})
            sqlite_manager.export_to_json()
            return {"url": url, "status": "skipped", "message_sent": False}

        # Extract data
        title = re.search(
            r"title:\s*(.+?)(?:\n|seller:|desc:|$)", result, re.IGNORECASE
        )
        title = title.group(1).strip() if title else "Unknown"

        desc = re.search(r"desc:\s*(.+?)(?:\n|$)", result, re.IGNORECASE)
        desc = desc.group(1).strip() if desc else ""

        # Determine pricing strategy
        offer = None

        # 1. Try Product-Specific Configuration (from GUI)
        product_name = listing_item.get("product") or listing_item.get(
            "matched_product"
        )
        product_config = None

        # Reload config to ensure we have latest settings
        current_config = load_full_config() or {}
        search_products_config = current_config.get("search_products", [])

        if product_name:
            product_name_lower = str(product_name).lower().strip()
            # Find matching product config (case-insensitive)
            for p in search_products_config:
                if (
                    isinstance(p, dict)
                    and str(p.get("name", "")).lower().strip() == product_name_lower
                ):
                    product_config = p
                    print(
                        f"  ✅ Found specific config for product: {product_config.get('name')}"
                    )
                    break

        # If no specific product match, but we have a single configured product, use that as fallback
        if (
            not product_config
            and len(search_products_config) == 1
            and isinstance(search_products_config[0], dict)
        ):
            product_config = search_products_config[0]
            print(
                f"  ℹ️  Using single configured product as fallback: {product_config.get('name')}"
            )

        if product_config:
            # Safely extract prices with defaults
            try:
                base_offer_unlocked = float(
                    product_config.get("base_offer_unlocked") or 300
                )
                base_offer_locked = float(
                    product_config.get("base_offer_locked") or 250
                )
                base_offer_unlocked_damaged = float(
                    product_config.get("base_offer_unlocked_damaged") or 150
                )
                base_offer_locked_damaged = float(
                    product_config.get("base_offer_locked_damaged") or 100
                )

                print(
                    f"  💰 Pricing loaded: Unlocked=${base_offer_unlocked}, Locked=${base_offer_locked}"
                )
            except (ValueError, TypeError) as e:
                print(f"  ⚠️ Error parsing pricing config: {e}. Using defaults.")
                base_offer_unlocked = 300.0
                base_offer_locked = 250.0
                base_offer_unlocked_damaged = 150.0
                base_offer_locked_damaged = 100.0

            # Logic to determine price based on keywords
            text = (title + " " + desc).lower()

            # Improved lock detection
            is_locked = (
                any(
                    x in text
                    for x in [
                        "locked",
                        "verizon",
                        "att",
                        "t-mobile",
                        "sprint",
                        "carrier lock",
                        "sim lock",
                    ]
                )
                and "unlocked" not in text
            )

            # Improved damage detection with negation handling
            damage_keywords = [
                "crack",
                "damaged",
                "broken",
                "parts",
                "bad lcd",
                "screen issue",
                "scratch",
            ]

            # Check for negation phrases that indicate good condition
            negation_patterns = [
                "no scratch",
                "no crack",
                "no damage",
                "no dent",
                "no ding",
                "not damaged",
                "not broken",
                "without scratch",
                "without crack",
                "without damage",
                "never been replaced",
                "excellent condition",
                "good condition",
                "great condition",
                "mint condition",
                "like new",
            ]

            # If negation patterns are found, likely NOT damaged
            has_negation = any(neg in text for neg in negation_patterns)

            # Check for damage keywords
            has_damage_keywords = any(kw in text for kw in damage_keywords)

            # Only flag as damaged if damage keywords found WITHOUT strong negation
            is_damaged = has_damage_keywords and not has_negation

            if is_locked:
                price = base_offer_locked_damaged if is_damaged else base_offer_locked
                print(
                    f"  🔒 Detected LOCKED status (Damaged: {is_damaged}) -> Offer: ${price}"
                )
            else:
                price = (
                    base_offer_unlocked_damaged if is_damaged else base_offer_unlocked
                )
                print(
                    f"  🔓 Detected UNLOCKED status (Damaged: {is_damaged}) -> Offer: ${price}"
                )

            offer = {
                "offer_price": int(price),
                "grade": "grade_d" if is_damaged else "grade_b",
                "is_unlocked": not is_locked,
            }

        # 2. Fallback to Environment Variables (Legacy/Docker)
        elif os.getenv("BASE_OFFER_UNLOCKED"):
            print("  💰 Using environment variable configuration for pricing")
            try:
                base_offer_unlocked_str = os.getenv("BASE_OFFER_UNLOCKED")
                base_offer_unlocked = float(base_offer_unlocked_str or "300")
                base_offer_locked = float(os.getenv("BASE_OFFER_LOCKED") or "250")
                base_offer_unlocked_damaged = float(
                    os.getenv("BASE_OFFER_UNLOCKED_DAMAGED") or "150"
                )
                base_offer_locked_damaged = float(
                    os.getenv("BASE_OFFER_LOCKED_DAMAGED") or "100"
                )
            except (ValueError, TypeError) as e:
                print(f"  ⚠️ Error parsing env var pricing: {e}. Using defaults.")
                base_offer_unlocked = 300.0
                base_offer_locked = 250.0
                base_offer_unlocked_damaged = 150.0
                base_offer_locked_damaged = 100.0

            # Logic to determine price based on keywords
            text = (title + " " + desc).lower()
            is_locked = (
                any(
                    x in text
                    for x in ["locked", "verizon", "att", "t-mobile", "sprint"]
                )
                and "unlocked" not in text
            )

            # Damage detection with negation handling
            damage_keywords = ["crack", "damaged", "broken", "parts", "bad lcd", "scratch"]
            negation_patterns = [
                "no scratch", "no crack", "no damage", "no dent", "no ding",
                "not damaged", "not broken", "without scratch", "without crack",
                "without damage", "excellent condition", "good condition",
                "great condition", "mint condition", "like new"
            ]
            has_negation = any(neg in text for neg in negation_patterns)
            has_damage_keywords = any(kw in text for kw in damage_keywords)
            is_damaged = has_damage_keywords and not has_negation

            if is_locked:
                price = base_offer_locked_damaged if is_damaged else base_offer_locked
            else:
                price = (
                    base_offer_unlocked_damaged if is_damaged else base_offer_unlocked
                )

            offer = {
                "offer_price": int(price),
                "grade": "grade_d" if is_damaged else "grade_b",
                "is_unlocked": not is_locked,
            }
        else:
            # Only use the complex matcher if no user config is present
            offer = get_offer_price(title, desc)

        if not offer or not offer.get("offer_price"):
            print("  ⚠️ No valid price found (check configuration)")
            return {"url": url, "status": "skipped", "message_sent": False}

        # Send message
        message = (
            "Hi, can you tell me more about the damage?"
            if offer["grade"] in ["grade_d", "doa"]
            else f"Hi I can do ${offer['offer_price']} cash for it"
        )

        agent.add_new_task(
            f"""
            1. Click the "Message" button on the listing page to open the message dialog.
            2. Wait for the message dialog/popup to appear with a text input field.
            3. Find the message textarea/input field and use the input action with index and clear=True to replace any existing text.
            4. Input exactly: "{message}"
            5. CRITICAL: To send the message, press the Enter key. Do NOT click any buttons - just press Enter while focused on the text input.
            6. WARNING: Do NOT click on coordinates below y=700 - that area contains the location/address button which will open a "Change location" modal. The Send action should be done with Enter key only.
            7. Verify the message was sent (look for the message appearing in a chat thread or the dialog content changing).
            8. If successful, report "SENT: {message}".
            """
        )
        message_result = await agent.run()

        # Update database
        sent = "sent" in str(message_result).lower()
        updates = {"messaged": sent, "title": title}

        seller = re.search(r"seller:\s*(.+?)(?:\n|desc:|$)", result, re.IGNORECASE)
        if seller:
            updates["seller_name"] = seller.group(1).strip()

        sqlite_manager.update_listing(listing_id, updates)

        # Sync to JSON for GUI compatibility
        if sent:
            sqlite_manager.export_to_json()

        return {
            "url": url,
            "status": "completed" if sent else "error",
            "message_sent": sent,
        }

    except Exception as e:
        print(f"  ❌ Error processing listing: {e}")
        import traceback

        traceback.print_exc()
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

        # Start browser session
        print("🌐 Starting browser session...")
        await browser_session.start()
        print("✅ Browser session started")

        results = []
        messages_sent_count = 0
        MAX_MESSAGES_PER_SESSION = 10
        delay = 10.0  # Start with 10s

        for i, listing_item in enumerate(unmessaged_listings):
            if messages_sent_count >= MAX_MESSAGES_PER_SESSION:
                print(f"⚠️ Reached max messages limit ({MAX_MESSAGES_PER_SESSION})")
                break

            print(
                f"\n[{i + 1}/{len(unmessaged_listings)}] Processing: {listing_item.get('url', 'unknown')}"
            )
            result = await process_single_url(browser_session, listing_item, i)
            results.append(result)
            print(f"Result: {result['status']}")

            if result.get("message_sent"):
                messages_sent_count += 1

            if i < len(unmessaged_listings) - 1:
                await asyncio.sleep(delay)
                delay = (
                    min(delay * 1.1, 20.0) if "error" in result["status"] else delay
                )  # Adaptive

        # Summary (simplified)
        successful = sum(1 for r in results if r.get("message_sent"))
        skipped = sum(1 for r in results if r["status"] == "skipped")
        failed = len(results) - successful - skipped
        print(
            f"\n📊 Final Results: Successful: {successful}, Skipped: {skipped}, Failed: {failed}"
        )

    finally:
        await browser_session.stop()


if __name__ == "__main__":
    asyncio.run(main())
