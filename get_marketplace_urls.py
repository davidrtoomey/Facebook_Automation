# from langchain_google_genai import GoogleGenerativeAI
from browser_use.llm import ChatGoogle
from browser_use import Agent
from browser_use.browser import BrowserProfile, BrowserSession
from dotenv import load_dotenv
import os
import asyncio
import re
import json
from datetime import datetime
from typing import List
from models import (
    ConversationModel,
    MessagesData,
    load_messages_json,
    save_messages_json,
    extract_message_id_from_url,
)
from utils.config_loader import get_gemini_api_key, get_config_value, load_full_config

load_dotenv()

api_key = get_gemini_api_key()

# Create LLM using the browser-use compatible approach - using faster model for URL extraction
llm = ChatGoogle(model="gemini-3-flash-preview", api_key=api_key)
# llm = ChatGoogle(model="gemini-2.5-pro", api_key=api_key)


browser_profile = BrowserProfile(
    executable_path="/usr/bin/chromium",
    user_data_dir="/home/david/.config/browseruse/profiles/agent",
    headless=os.getenv("HEADLESS_CONVERSATIONS", "false").lower() == "true",
    keep_alive=True,
    # Security: Restrict to Facebook domains only - prevent clicking external links
    allowed_domains=["facebook.com", "www.facebook.com", "m.facebook.com"],
)


# Functions are now imported from models.py


def add_urls_to_messages_json(urls: List[str]) -> MessagesData:
    """Add URLs to messages.json file."""
    # Load existing data
    messages_data = load_messages_json()

    # Get existing URLs to avoid duplicates
    existing_urls = {conv.conversation_url for conv in messages_data.conversations}

    # Add new URLs
    new_count = 0
    for url in urls:
        if url not in existing_urls:
            # Extract message ID from URL
            message_id = extract_message_id_from_url(url)

            # Create new conversation entry with expanded model
            # Only populate the essential fields, leaving others as None/default
            new_conv = ConversationModel(
                conversation_url=url,
                status="new",
                last_updated=datetime.now().isoformat(),
                message_id=message_id,  # Store message_id which is used by conversation_agent.py
            )
            messages_data.conversations.append(new_conv)
            existing_urls.add(url)
            new_count += 1

    print(f"✅ Added {new_count} new conversations to messages.json")

    # Save updated data
    return save_messages_json(messages_data)


async def get_marketplace_urls(agent):
    """Get marketplace URLs with very explicit instructions about using the browser address bar."""
    print("\n🔍 Getting marketplace URLs with explicit address bar instructions...")

    # First make sure we're in the marketplace filter using specific CSS selector information
    agent.add_new_task(
        """Use click_element_by_index with index 44 to click on Marketplace in the left sidebar. You are not trying to go to facebook.com/marketplace. You are trying to open Marketplaces messages in facebook.com/messages. click element 44 and don't do anything I don't explicity tell you to do."""
    )
    filter_result = await agent.run()
    filter_result_str = str(filter_result)

    # if "MARKETPLACE_FILTER_NOT_FOUND" in filter_result_str:
    #     print("⚠️ Marketplace filter could not be found. Trying alternative approach.")
    #     agent.add_new_task(
    #         """Use click_element_by_index with index 44 to click on Marketplace in the left sidebar."""
    #     )
    #     await agent.run()

    # Now get the message URLs with better instructions for identifying marketplace conversations
    agent.add_new_task(f"""Get browser address bar URLs for 10 Marketplace conversations:

1. IDENTIFYING MARKETPLACE CONVERSATIONS:
   - Marketplace conversations have a specific format: "[Seller Name] · [Product Name]"
   - They have a dot/bullet point (·) between seller name and product name
   - They often show product images or item thumbnails
   - Regular chats only show a person's name WITHOUT the dot separator

2. EXTRACTING URLS - FOLLOW THESE STEPS EXACTLY:
   a. Find the FIRST Marketplace conversation in the left sidebar (with the · separator)
   b. Click on it to open the conversation
   c. Look at the browser address bar at the TOP of the screen
   d. Copy the FULL URL from the address bar (should start with https://www.facebook.com/messages/t/)
   e. Report the URL in this EXACT format:
      CONVERSATION_URL_START 1
      URL: [paste the full URL from address bar]
      CONVERSATION_URL_END 1

3. REPEAT for up to 10 Marketplace conversations:
   - Go back to the conversation list if needed
   - Click the NEXT Marketplace conversation
   - Copy the URL from the address bar
   - Report as CONVERSATION_URL_START 2, etc.

IMPORTANT NOTES:
- ONLY extract URLs from the browser's address bar at the top of the screen
- Each URL should look like: https://www.facebook.com/messages/t/123456789
- If you can't find any Marketplace conversations, report "NO_MARKETPLACE_CONVERSATIONS_FOUND"
- Do NOT include any explanatory text, just the URL markers and URLs""")

    result = await agent.run()
    result_str = str(result)

    if "NO_MARKETPLACE_CONVERSATIONS_FOUND" in result_str:
        print("⚠️ No Marketplace conversations found! Trying alternative approach...")

        # Fallback approach: Look for conversations with specific marketplace indicators
        agent.add_new_task(f"""Try this alternative approach to find Marketplace conversations:

1. Look for conversations in the left sidebar that have ANY of these characteristics:
   - Contains a dot/bullet (·) between names
   - Has text like "iPhone", "selling", "buying", "price", "offer", "item", "product"
   - Shows a product image thumbnail
   - Has a price mentioned ($, USD, etc.)

2. For each potential Marketplace conversation:
   a. Click on it
   b. Copy the URL from the browser address bar
   c. Report using the same format:
      CONVERSATION_URL_START [number]
      URL: [paste URL]
      CONVERSATION_URL_END [number]

3. Try to find at least 5 conversations that might be Marketplace related
   
4. If you still can't find any, report "STILL_NO_MARKETPLACE_CONVERSATIONS_FOUND"
""")

        fallback_result = await agent.run()
        fallback_result_str = str(fallback_result)

        if "STILL_NO_MARKETPLACE_CONVERSATIONS_FOUND" in fallback_result_str:
            print("⚠️ Still no Marketplace conversations found after fallback attempt!")
            return []

        # Continue with URL extraction using the fallback result
        result_str = fallback_result_str

    urls = []

    # Extract URL blocks - only capture the actual URL part, not the markers
    # More precise pattern to extract only the URL between "URL:" and the end marker or newline
    url_pattern = r"CONVERSATION_URL_START\s+(\d+).*?URL:\s*(https?://(?:www\.)?facebook\.com/messages/t/[^/\s\n\"'<>]+/?)"
    matches = re.findall(url_pattern, result_str, re.DOTALL | re.IGNORECASE)

    print("DEBUG: Raw URL matches found:", len(matches))

    # If no matches found using the pattern, try a more lenient approach
    if not matches:
        print(
            "WARNING: No URLs found with standard pattern, trying alternative extraction..."
        )
        # Look for any Facebook message URLs in the text - more strict pattern
        alt_pattern = r'(https?://(?:www\.)?facebook\.com/messages/t/[^"\'\s\n<>/]+/?)'
        alt_matches = re.findall(alt_pattern, result_str)
        if alt_matches:
            print(f"Found {len(alt_matches)} URLs with alternative pattern")
            # Convert to the expected format
            matches = [(str(i + 1), url) for i, url in enumerate(alt_matches)]
        else:
            # Final fallback: Ask the agent to explicitly extract any URLs it can find
            print(
                "WARNING: No URLs found with alternative pattern, trying final extraction method..."
            )

            agent.add_new_task(f"""URGENT: I need you to extract ANY Facebook message URLs you can find:

1. Look at the browser address bar right now
2. Copy the FULL URL (should contain facebook.com/messages)
3. Report it as: DIRECT_URL: [paste URL here]

4. Then try to navigate to ANY conversation in the left sidebar
5. After clicking, copy the new URL from the address bar
6. Report it as: DIRECT_URL: [paste URL here]

7. Repeat for as many conversations as you can (at least 3)
8. ONLY report the URLs, nothing else
""")

            final_result = await agent.run()
            final_result_str = str(final_result)

            # Extract direct URLs with a more precise pattern
            direct_urls = re.findall(
                r"DIRECT_URL:\s*(https?://(?:www\.)?facebook\.com/messages/t/[^\"'\s\n<>/]+/?)",
                final_result_str,
            )

            if direct_urls:
                print(f"Found {len(direct_urls)} URLs with final extraction method")
                matches = [(str(i + 1), url) for i, url in enumerate(direct_urls)]
            else:
                # Last resort: extract any URL that looks like a Facebook message URL
                # More precise pattern to avoid capturing extra text
                last_resort_pattern = (
                    r'(https?://(?:www\.)?facebook\.com/messages/t/[^"\'\s\n<>/]+/?)'
                )
                last_resort_urls = re.findall(last_resort_pattern, final_result_str)

                if last_resort_urls:
                    print(
                        f"Found {len(last_resort_urls)} URLs with last resort pattern"
                    )
                    matches = [
                        (str(i + 1), url) for i, url in enumerate(last_resort_urls)
                    ]

    for index, url in matches:
        # Clean the URL and add to list - remove any trailing markers or newlines
        clean_url = url.strip()

        # Remove escaped newlines and anything after them FIRST
        clean_url = re.sub(r"\\n.*$", "", clean_url)
        clean_url = re.sub(r"\n.*$", "", clean_url)

        # Remove any embedded markers that might have been captured
        clean_url = re.sub(r"\s*CONVERSATION_URL_END.*$", "", clean_url)
        clean_url = re.sub(r"\s*CONVERSATION_URL_START.*$", "", clean_url)

        # Remove trailing slashes, quotes, brackets, etc.
        clean_url = re.sub(r"[/\"'<>\]\[\)\(]+$", "", clean_url)
        clean_url = clean_url.strip()

        print(
            f"DEBUG: Processing URL {index}: {clean_url[:50]}{'...' if len(clean_url) > 50 else ''}"
        )

        # Final validation - ensure URL has a valid numeric message ID
        # The message ID after /t/ should be numeric (or alphanumeric for some cases)
        valid_url_pattern = (
            r'^https?://(?:www\.)?facebook\.com/messages/t/(\d+)/?$'
        )

        match = re.match(valid_url_pattern, clean_url)
        if match:
            # URL is properly formatted with numeric ID
            print(f"DEBUG: Valid URL format: {clean_url}")
            urls.append(clean_url)
        else:
            # Try to extract just the numeric message ID and reconstruct URL
            id_extract = re.search(
                r'facebook\.com/messages/t/(\d+)',
                clean_url,
            )
            if id_extract:
                message_id = id_extract.group(1)
                reconstructed_url = f"https://www.facebook.com/messages/t/{message_id}"
                print(f"DEBUG: Reconstructed URL from ID {message_id}: {reconstructed_url}")
                urls.append(reconstructed_url)
            else:
                print(f"DEBUG: Invalid URL format, skipping: {clean_url}")

        # Check if the URL is a relative path
        if clean_url.startswith("/messages/t/"):
            # Convert relative URL to absolute URL
            absolute_url = f"https://www.facebook.com{clean_url}"
            print(f"DEBUG: Converted relative URL to: {absolute_url}")

            # Validate the converted URL
            if re.match(valid_url_pattern, absolute_url):
                urls.append(absolute_url)

    print(f"✅ Found {len(urls)} Marketplace conversation URLs")
    return urls


async def main():
    print("🚀 Starting Facebook Marketplace URL extractor...")
    print("⚡ Using fast model for quick URL extraction")
    print("🌐 Initializing browser session...")

    browser_session = BrowserSession(browser_profile=browser_profile)

    try:
        print("📱 Creating AI agent...")
        # Initialize agent
        agent = Agent(
            task="Go to facebook.com/messages", llm=llm, browser_session=browser_session
        )

        print("🔗 Navigating to Facebook Messages...")
        # Navigate to inbox
        result = await agent.run()
        if not result.is_successful:
            raise RuntimeError("Failed to open Facebook inbox")
        print("✅ Successfully opened Facebook Messages!")

        # Get marketplace URLs
        marketplace_urls = await get_marketplace_urls(agent)

        # Print results
        print("\n--- Results ---")
        for i, url in enumerate(marketplace_urls):
            print(f"{i + 1}. {url}")

        print(f"\nTotal URLs found: {len(marketplace_urls)}")

        # Save URLs to messages.json
        if marketplace_urls:
            print("\nSaving URLs to messages.json...")
            messages_data = add_urls_to_messages_json(marketplace_urls)
            print(
                f"Total conversations in messages.json: {messages_data.total_conversations}"
            )
        else:
            print("\nNo URLs to save to messages.json")

    finally:
        await browser_session.stop()


if __name__ == "__main__":
    asyncio.run(main())
