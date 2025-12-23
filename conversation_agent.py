from browser_use.llm import ChatGoogle
from browser_use import Agent
from browser_use.browser import BrowserProfile, BrowserSession
from dotenv import load_dotenv
import os
import asyncio
import json
import re
from datetime import datetime
from typing import Optional, Dict, Any
from notification_system import notify_deal_closed, notify_agent_needs_help
from conversation_tracker import update_conversation_tracking, print_follow_up_summary
from models import (
    ConversationModel,
    MessagesData,
    load_messages_json,
    save_messages_json,
    extract_message_id_from_url,
    find_conversation_by_message_id,
)
from utils.fix_messages_json import fix_messages_json
from utils.config_loader import get_gemini_api_key
from utils.pricing_manager import get_offer_price

load_dotenv()

api_key = get_gemini_api_key()

# Get configuration from environment variables
search_product = os.getenv("SEARCH_PRODUCT", "iPhone 13 Pro Max")
notification_email = os.getenv("NOTIFICATION_EMAIL", "")
enable_negotiation = os.getenv("ENABLE_NEGOTIATION", "true").lower() == "true"
price_flexibility = int(os.getenv("PRICE_FLEXIBILITY", "20"))

print(f"Managing conversations for product: {search_product}")
print(f"Negotiation enabled: {enable_negotiation}")
print(f"Price flexibility: ${price_flexibility}")

# Use browser-use compatible LLM
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


# Load negotiation script
def load_negotiation_script(script_path="negotiation_script.md") -> Dict[str, Any]:
    """Load the negotiation script from the markdown file and parse it into a structured format."""
    script = {}

    try:
        with open(script_path, "r") as file:
            content = file.read()

        # Parse sections
        script["initial_offer"] = {}
        script["responses"] = {}
        script["scenarios"] = {}
        script["location"] = "Wawa at 1860 S Collegeville Rd, Collegeville"  # Default

        # Extract initial offer strategies (already handled by offer_agent.py)
        unlocked_match = re.search(r'\*\*Unlocked phones\*\*:\s*"([^"]+)"', content)
        if unlocked_match:
            script["initial_offer"]["unlocked"] = unlocked_match.group(1)

        locked_match = re.search(r'\*\*Network locked phones\*\*:\s*"([^"]+)"', content)
        if locked_match:
            script["initial_offer"]["locked"] = locked_match.group(1)

        damaged_match = re.search(r'\*\*Damaged items\*\*:\s*"([^"]+)"', content)
        if damaged_match:
            script["initial_offer"]["damaged"] = damaged_match.group(1)

        default_match = re.search(r'\*\*Default\*\*:\s*"([^"]+)"', content)
        if default_match:
            script["initial_offer"]["default"] = default_match.group(1)

        # Extract response handling scenarios
        accept_match = re.search(
            r'### If Seller Accepts Our Initial Offer\s*\*\*Response\*\*:\s*"([^"]+)"',
            content,
        )
        if accept_match:
            script["responses"]["accept"] = accept_match.group(1)

        decline_match = re.search(
            r'### If Seller Declines Initial Offer \(No Counter-Offer\)\s*\*\*Response\*\*:\s*"([^"]+)"',
            content,
        )
        if decline_match:
            script["responses"]["decline"] = decline_match.group(1)

        counter_match = re.search(
            r'### If Seller Makes Counter-Offer\s*\*\*Response\*\*:\s*"([^"]+)"',
            content,
        )
        if counter_match:
            script["responses"]["counter"] = counter_match.group(1)

        decline_counter_match = re.search(
            r'### If Seller Declines Our Counter-Offer\s*\*\*Response\*\*:\s*"([^"]+)"',
            content,
        )
        if decline_counter_match:
            script["responses"]["decline_counter"] = decline_counter_match.group(1)

        # Extract additional scenarios
        location_match = re.search(
            r'### If Seller Asks About Location/Where We\'re Located\s*\*\*Response\*\*:\s*"([^"]+)"',
            content,
        )
        if location_match:
            script["scenarios"]["ask_location"] = location_match.group(1)

        condition_match = re.search(
            r'### If Seller Asks Questions About Phone Condition\s*\*\*Response\*\*:\s*"([^"]+)"',
            content,
        )
        if condition_match:
            script["scenarios"]["ask_condition"] = condition_match.group(1)

        payment_match = re.search(
            r'### If Seller Asks About Payment Method\s*\*\*Response\*\*:\s*"([^"]+)"',
            content,
        )
        if payment_match:
            script["scenarios"]["ask_payment"] = payment_match.group(1)

        timing_match = re.search(
            r'### If Seller Asks About Timing/When to Meet\s*\*\*Response\*\*:\s*"([^"]+)"',
            content,
        )
        if timing_match:
            script["scenarios"]["ask_timing"] = timing_match.group(1)

        other_buyers_match = re.search(
            r'### If Seller Mentions Other Interested Buyers\s*\*\*Response\*\*:\s*"([^"]+)"',
            content,
        )
        if other_buyers_match:
            script["scenarios"]["other_buyers"] = other_buyers_match.group(1)

        item_sold_match = re.search(
            r'### If Seller Says Item is Sold\s*\*\*Response\*\*:\s*"([^"]+)"', content
        )
        if item_sold_match:
            script["scenarios"]["item_sold"] = item_sold_match.group(1)

        ask_about_us_match = re.search(
            r'### If Seller Asks for More Details About Us\s*\*\*Response\*\*:\s*"([^"]+)"',
            content,
        )
        if ask_about_us_match:
            script["scenarios"]["ask_about_us"] = ask_about_us_match.group(1)

        location_negotiation_match = re.search(
            r'### If Seller Wants to Negotiate Meeting Location\s*\*\*Response\*\*:\s*"([^"]+)"',
            content,
        )
        if location_negotiation_match:
            script["scenarios"]["location_negotiation"] = (
                location_negotiation_match.group(1)
            )

        # Extract meetup location
        location_match = re.search(
            r"\*\*Standard Location\*\*:\s*(.+)$", content, re.MULTILINE
        )
        if location_match:
            script["location"] = location_match.group(1).strip()

        # Rules
        max_counter_offer_match = re.search(
            r"Maximum counter-offer:\s*(.+)$", content, re.MULTILINE
        )
        if max_counter_offer_match:
            script["rules"] = {
                "max_counter_offer": max_counter_offer_match.group(1).strip()
            }

        print(
            f"✅ Loaded negotiation script with {len(script['responses'])} response types and {len(script['scenarios'])} scenarios"
        )
        return script

    except Exception as e:
        print(f"❌ Error loading negotiation script: {e}")
        # Return a minimal default script as fallback
        return {
            "responses": {
                "accept": "Great! Let's meet up. Where and when works for you?",
                "decline": "How much were you looking to get for it?",
                "counter": "I could meet you in the middle at ${middle_price}. That's my best offer.",
            },
            "location": "Wawa at 1860 S Collegeville Rd, Collegeville",
            "rules": {"max_counter_offer": "Initial offer + $20"},
        }


# Load the script at module level so it's available to all functions
NEGOTIATION_SCRIPT = load_negotiation_script()

# These functions are now imported from models.py


def create_new_conversation(
    listing_item, conversation_url, seller_info, item_info
) -> Optional[ConversationModel]:
    """Create a new conversation entry following the Pydantic model schema.
    Returns None if no valid offer price can be determined."""
    now = datetime.now().isoformat()

    # Clean URL by removing any trailing newlines
    clean_url = conversation_url.rstrip("\n\\n") if conversation_url else ""

    # Extract message ID from URL
    message_id = extract_message_id_from_url(clean_url)

    # Get offer price - NO DEFAULT, must have a valid price
    offer_price = listing_item.get("offer_price")
    product_name = item_info.get("title", listing_item.get("title", ""))

    # If no offer_price in listing_item, try to look it up from pricing manager
    if not offer_price and product_name:
        try:
            price_info = get_offer_price(product_name, "")
            if price_info and price_info.get("offer_price"):
                offer_price = int(price_info["offer_price"])
                print(f"📝 Looked up offer price from pricing manager: ${offer_price}")
        except Exception as e:
            print(f"⚠️ Could not look up price from pricing manager: {e}")

    # If still no price, we cannot create this conversation
    if not offer_price:
        print(f"⚠️⚠️ SKIPPING conversation creation - no offer price for: {product_name}")
        print(f"⚠️⚠️ URL: {clean_url}")
        return None

    # Create message history
    message_history = [
        {
            "timestamp": listing_item.get("messaged_at", now),
            "from": "us",
            "message": f"Hi I can do ${offer_price} cash for it",
        }
    ]

    # Create and return a ConversationModel instance
    return ConversationModel(
        conversation_url=clean_url,
        seller_name=seller_info.get("name", listing_item.get("seller_name", "Unknown")),
        product_name=product_name or search_product,
        status="awaiting_response",
        last_message=f"Hi I can do ${offer_price} cash for it",
        last_updated=now,
        message_history=message_history,
        offer_amount=offer_price,
        message_id=message_id,
    )


def update_conversation_history(
    conversation: ConversationModel,
    result_str: str,
    our_message: Optional[str] = None,
    seller_message: Optional[str] = None,
    status: Optional[str] = None,
) -> ConversationModel:
    """Update conversation with new status and messages."""
    now = datetime.now().isoformat()

    # Update conversation status if provided
    if status:
        old_status = conversation.status
        conversation.status = status
        print(f"✅ Updated conversation status: {old_status} → {status}")

    # Add our message to history if provided
    if our_message:
        # Add message to history
        conversation.message_history.append(
            {"timestamp": now, "from": "us", "message": our_message}
        )
        conversation.last_message = our_message

    # Add seller message to history if provided
    if seller_message:
        # Add message to history
        conversation.message_history.append(
            {"timestamp": now, "from": "seller", "message": seller_message}
        )
        conversation.last_message = seller_message

    # Update the last_updated timestamp whenever we modify the conversation
    conversation.last_updated = now

    # Make sure the conversation URL is clean (no trailing newlines)
    conversation.conversation_url = conversation.conversation_url.rstrip("\n\\n")

    return conversation


async def read_conversation(
    agent, conversation_url, messages_data, listings, result=None
):
    """Read and process a conversation at the given URL using the negotiation script."""
    # Find the conversation in messages_data
    message_id = extract_message_id_from_url(conversation_url)
    if not message_id:
        print(f"⚠️ Could not extract message ID from URL: {conversation_url}")
        return None

    conversation = find_conversation_by_message_id(messages_data, message_id)

    if not conversation:
        print(f"⚠️ Conversation not found for URL: {conversation_url}")
        return None

    # Extract result from agent's output - use final_result() for clean text
    if result is None:
        result_str = ""
    elif hasattr(result, 'final_result') and callable(result.final_result):
        result_text = result.final_result()
        result_str = result_text if result_text else ""
    else:
        result_str = str(result)

    result_str_lower = result_str.lower() if isinstance(result_str, str) else str(result_str).lower()
    print(f"🔍 Processing agent result for {conversation_url}")
    print(f"📝 Result preview: {result_str_lower[:200]}...")
    print(f"📊 Current conversation status: {conversation.status}")

    # Extract conversation data using the structured format
    import re

    seller_name_match = re.search(r"SELLER_NAME:\s*([^\n]+)", result_str, re.IGNORECASE)
    if seller_name_match and not conversation.seller_name:
        extracted_seller_name = seller_name_match.group(1).strip()
        if (
            extracted_seller_name
            and extracted_seller_name != "[name from conversation header/title]"
        ):
            conversation.seller_name = extracted_seller_name
            print(f"✅ Extracted seller name: {extracted_seller_name}")

    product_name_match = re.search(
        r"PRODUCT_NAME:\s*([^\n]+)", result_str, re.IGNORECASE
    )
    if product_name_match and not conversation.product_name:
        extracted_product_name = product_name_match.group(1).strip()
        if (
            extracted_product_name
            and extracted_product_name
            != "[product name from conversation header/title]"
        ):
            conversation.product_name = extracted_product_name
            print(f"✅ Extracted product name: {extracted_product_name}")

    # Extract OUR initial offer from the agent's reading of the conversation
    # This is CRITICAL for proper negotiation logic
    our_initial_offer_match = re.search(
        r"OUR_INITIAL_OFFER:\s*\$?(\d+)", result_str, re.IGNORECASE
    )
    if our_initial_offer_match:
        extracted_initial_offer = int(our_initial_offer_match.group(1))
        # Only update if we don't already have an offer_amount or if the extracted one is more reasonable
        if not conversation.offer_amount or conversation.offer_amount != extracted_initial_offer:
            print(f"✅ Extracted OUR initial offer from conversation: ${extracted_initial_offer}")
            conversation.offer_amount = extracted_initial_offer
            # Save immediately to ensure we don't lose this critical data
            save_conversation(conversation)

    last_message_match = re.search(
        r"LAST_MESSAGE:\s*([^\n]+)", result_str, re.IGNORECASE
    )
    last_message_from_match = re.search(
        r"LAST_MESSAGE_FROM:\s*([^\n]+)", result_str, re.IGNORECASE
    )
    if last_message_match:
        extracted_last_message = last_message_match.group(1).strip()
        extracted_from = (
            last_message_from_match.group(1).strip()
            if last_message_from_match
            else "unknown"
        )
        if (
            extracted_last_message
            and extracted_last_message != "[most recent message in the conversation]"
        ):
            conversation.last_message = extracted_last_message
            print(
                f"✅ Extracted last message from {extracted_from}: {extracted_last_message[:50]}..."
            )

    # Process based on response patterns
    seller_message = None
    our_message = None
    status_update = None

    # Check if no response from seller (explicitly check for this pattern)
    if (
        "no_response" in result_str_lower
        or "no response" in result_str_lower
        or "no new messages" in result_str_lower
        or "hasn't responded" in result_str_lower
    ):
        print(f"📭 No response yet from seller in conversation: {conversation_url}")
        # Only update timestamp but don't change status
        conversation.last_updated = datetime.now().isoformat()
        return conversation

    # Use responses from negotiation script
    if "seller_accepted" in result_str_lower:
        # Handle acceptance
        seller_message = "I'll take your offer"
        our_message = NEGOTIATION_SCRIPT["responses"].get(
            "accept",
            "Okay great, I'm located in Collegeville. Can we meet at this Wawa: 1860 S Collegeville Rd",
        )
        status_update = "deal_pending"
        notify_deal_closed(
            conversation,
            conversation.offer_amount,
            conversation.seller_name,
            email_address=notification_email,
        )
        print(f"🎉 Seller accepted our offer! Using script response: '{our_message}'")

    elif "counter_offer" in result_str_lower:
        # Extract counter offer amount - stricter regex to avoid capturing random numbers
        counter_match = re.search(r"counter_offer:\s*\$?(\d+)", result_str_lower)
        if counter_match:
            counter_amount = int(counter_match.group(1))
            conversation.counter_offer = counter_amount
            print(f"💰 Detected counter offer: ${counter_amount}")

            # Decision logic based on counter offer
            # IMPORTANT: We must find OUR initial offer, NOT the seller's counter!
            # Priority: 1) stored offer_amount, 2) pricing manager (most reliable), 3) message history, 4) default
            initial_offer = conversation.offer_amount

            # First, try to look up price from pricing manager using product name
            # This is the most reliable source since it's based on our configured pricing
            if not initial_offer and conversation.product_name:
                try:
                    price_info = get_offer_price(conversation.product_name, "")
                    if price_info and price_info.get("offer_price"):
                        initial_offer = int(price_info["offer_price"])
                        print(f"📝 Looked up offer from pricing manager: ${initial_offer}")
                        conversation.offer_amount = initial_offer
                except Exception as e:
                    print(f"⚠️ Could not look up price from pricing manager: {e}")

            # If no pricing manager match, try to extract from our FIRST message in history
            # Only look for messages that contain our offer pattern "I can do $X"
            if not initial_offer and conversation.message_history:
                for msg in conversation.message_history:
                    if msg.get("from") == "us":
                        msg_text = msg.get("message", "")
                        # Only match our specific offer format to avoid grabbing wrong prices
                        offer_match = re.search(r"(?:I can do|can do|offer)\s*\$(\d+)", msg_text, re.IGNORECASE)
                        if offer_match:
                            initial_offer = int(offer_match.group(1))
                            print(f"📝 Extracted initial offer from message history: ${initial_offer}")
                            conversation.offer_amount = initial_offer
                            break

            # If no initial offer found, we cannot safely negotiate - skip this conversation
            if not initial_offer:
                print(f"⚠️⚠️ SKIPPING: No initial offer found for product: {conversation.product_name}")
                print(f"⚠️⚠️ Cannot negotiate without knowing our starting price. Marking as needs_help.")
                conversation.status = "needs_help"
                save_conversation(conversation)
                return  # Skip this conversation entirely

            # SAFETY CHECK: If our "initial_offer" is suspiciously close to the counter_amount,
            # it might be the seller's price that was incorrectly captured. Skip to be safe.
            if initial_offer >= counter_amount:
                print(f"⚠️⚠️ SKIPPING: initial_offer (${initial_offer}) >= counter (${counter_amount}), likely wrong!")
                print(f"⚠️⚠️ Cannot safely negotiate - our offer seems incorrect. Marking as needs_help.")
                conversation.status = "needs_help"
                save_conversation(conversation)
                return  # Skip this conversation entirely

            # Get the max counter offer rule from the script
            max_counter_rule = NEGOTIATION_SCRIPT.get("rules", {}).get(
                "max_counter_offer", "Initial offer + $20"
            )
            max_counter_amount = 20  # Default to $20 if we can't parse the rule
            if "+" in max_counter_rule:
                try:
                    # Extract just the number from something like "Initial offer + $20"
                    max_match = re.search(r"\$?(\d+)", max_counter_rule)
                    if max_match:
                        max_counter_amount = int(max_match.group(1))
                except (AttributeError, ValueError):
                    pass

            print(
                f"Max allowed counter amount: initial (${initial_offer}) + ${max_counter_amount}"
            )

            if counter_amount <= initial_offer + max_counter_amount:
                # Accept if within the allowed counter offer limit
                print(
                    f"✅ Counter offer ${counter_amount} is within acceptable range (max: ${initial_offer + max_counter_amount}), accepting!"
                )
                our_message = f"I can do ${counter_amount}. When and where can we meet?"
                status_update = "deal_pending"
            else:
                # Counter with initial_offer + $20 per negotiation script
                our_counter = initial_offer + max_counter_amount
                print(
                    f"🔄 Counter offer ${counter_amount} too high (max acceptable: ${initial_offer + max_counter_amount})"
                )
                print(
                    f"💬 Countering with: ${our_counter} (initial ${initial_offer} + ${max_counter_amount})"
                )

                # Use the counter response from the script, replace placeholders
                counter_response = NEGOTIATION_SCRIPT["responses"].get(
                    "counter",
                    "Hmm ${their_counter_offer} would be tough for me. I could do ${our_counter_offer} though",
                )

                # Replace placeholders in the template
                # ${their_counter_offer} = seller's counter (e.g., $450)
                # ${our_initial_offer + $10-20} = our counter (initial + $20, e.g., $320)
                # ${our_counter_offer} = same as above (for backwards compatibility)
                our_message = counter_response.replace(
                    "${their_counter_offer}", str(counter_amount)
                )
                our_message = our_message.replace(
                    "${our_initial_offer + $10-20}",
                    str(our_counter),
                )
                our_message = our_message.replace(
                    "${our_counter_offer}", str(our_counter)
                )
                our_message = our_message.replace("${middle_price}", str(our_counter))

                status_update = "negotiating"

        else:
            # Couldn't parse counter offer amount
            print("⚠️ Counter offer mentioned but couldn't extract amount")
            seller_message = "Would you do a bit more?"
            our_message = NEGOTIATION_SCRIPT["responses"].get(
                "decline", "How much were you looking to get for it?"
            )
            status_update = "negotiating"

    elif "seller_declined" in result_str_lower:
        # Seller declined without giving a counter price - ask what they want
        print("📝 Seller declined without counter offer, asking what they want")
        seller_message = "No"
        our_message = NEGOTIATION_SCRIPT["responses"].get(
            "decline", "How much were you looking to get for it?"
        )
        status_update = "negotiating"

    elif "seller_questions:" in result_str_lower:
        # Extract the specific question type from the structured response
        question_type_match = re.search(r"seller_questions:\s*(\w+)", result_str_lower)
        if question_type_match:
            question_type = question_type_match.group(1).strip()
            print(f"📝 Detected specific question type: {question_type}")

            # Map the question type to the appropriate script response
            if question_type == "location":
                our_message = NEGOTIATION_SCRIPT["scenarios"].get("ask_location")
            elif question_type == "condition":
                our_message = NEGOTIATION_SCRIPT["scenarios"].get("ask_condition")
            elif question_type == "payment":
                our_message = NEGOTIATION_SCRIPT["scenarios"].get("ask_payment")
            elif question_type == "timing":
                our_message = NEGOTIATION_SCRIPT["scenarios"].get("ask_timing")
            elif question_type == "other_buyers":
                our_message = NEGOTIATION_SCRIPT["scenarios"].get("other_buyers")
                status_update = "closed"  # Other buyer likely got it, close this conversation
            elif question_type == "sold":
                our_message = NEGOTIATION_SCRIPT["scenarios"].get("item_sold")
                status_update = "closed"  # Item is sold, close this conversation
            elif question_type == "about_us":
                our_message = NEGOTIATION_SCRIPT["scenarios"].get("ask_about_us")
            elif question_type == "meeting_place":
                our_message = NEGOTIATION_SCRIPT["scenarios"].get(
                    "location_negotiation"
                )

        # If no specific type found or no message set, use generic fallback
        if not our_message:
            print("⚠️ Using generic question response (no specific match found)")
            seller_message = "I have some questions"
            our_message = "Sure, what would you like to know?"

        # Only set to answering_questions if not already set to a terminal status
        if not status_update:
            status_update = "answering_questions"

    elif "needs_human_help" in result_str_lower:
        # Complex situation requiring human intervention
        print("🚨 Complex situation detected, requesting human help")

        # Extract the last seller message for context
        last_seller_message = ""
        if conversation.message_history:
            for msg in reversed(conversation.message_history):
                if msg.get("from") == "seller" and msg.get("message"):
                    last_seller_message = msg["message"]
                    break

        # Call with all required parameters
        notify_agent_needs_help(
            conversation,
            "Complex negotiation situation detected",
            last_seller_message or "No recent seller message found",
            conversation.seller_name or "Unknown Seller",
            notification_email,
        )
        seller_message = "[Complex situation]"
        status_update = "needs_help"

    # Update conversation with results
    if seller_message or our_message or status_update:
        print(f"📢 Updating conversation with response: '{our_message}'")
        print(f"🔄 Setting status to: {status_update}")

        # Actually send the message in the browser if one was generated
        if our_message:
            print(f"🚀 Sending message in browser: {our_message}")
            agent.add_new_task(f"""
            ACTION REQUIRED: Send the reply.
            1. Click on the chat input box.
            2. Type exactly: "{our_message}"
            3. Press Enter to send.
            4. Verify the message appears in the chat history.
            """)
            await agent.run()

        conversation = update_conversation_history(
            conversation,
            result_str,
            our_message=our_message,
            seller_message=seller_message,
            status=status_update,
        )

        # Track conversation updates for reporting
        # update_conversation_tracking(conversation.conversation_url, result_str, conversation.status, {})
    else:
        print("⚠️ No specific response condition matched")

        # Fallback: If conversation is still "new" and we have any result, set to "awaiting_response"
        if conversation.status == "new" and result_str:
            print("🔄 Setting new conversation to awaiting_response status")
            status_update = "awaiting_response"
            conversation = update_conversation_history(
                conversation,
                result_str,
                status=status_update,
            )
            # update_conversation_tracking(conversation.conversation_url, result_str, conversation.status, {})

    return conversation


async def main():
    print("Starting Facebook Marketplace manager...")

    # First, clean up any malformed URLs in messages.json
    print("Cleaning up message URLs...")
    fix_messages_json()

    # Load data using Pydantic model
    messages_data = load_messages_json()
    print(f"Loaded {len(messages_data.conversations)} conversations")

    with open("listings.json", "r") as file:
        listings = json.load(file)

    # Set limits
    MAX_CONVERSATIONS = 10
    processed_count = 0
    browser_session = BrowserSession(browser_profile=browser_profile)

    try:
        # Initialize agent
        agent = Agent(
            task="Go to facebook.com/messages", llm=llm, browser_session=browser_session
        )

        # Navigate to inbox
        result = await agent.run()
        if not result.is_successful:
            raise RuntimeError("Failed to open Facebook inbox")

        # Process URLs from messages.json (no need to extract URLs anymore)
        new_count = 0
        # Track processed message IDs to avoid duplicates in the same session
        processed_message_ids = set()

        # Process existing conversations
        print(
            f"🔄 Processing {len(messages_data.conversations)} total conversations..."
        )

        for idx, conv in enumerate(messages_data.conversations):
            if processed_count >= MAX_CONVERSATIONS:
                break

            print(
                f"📋 Conversation {idx + 1}: URL={conv.conversation_url[:50]}... Status={conv.status}"
            )

            # Skip conversations that are terminal/dead states
            skip_statuses = [
                "closed",           # Explicitly closed
                "deal_completed",   # Deal done
                "item_sold",        # Item sold to someone else
                "no_response_final", # No response after multiple attempts
                "rejected",         # Seller rejected our offer
                "needs_help",       # Needs human intervention, don't auto-process
            ]
            if conv.status in skip_statuses:
                print(f"⏭️ Skipping terminal conversation: {conv.status}")
                continue

            # Also skip if the last message from us was a "closing" response
            closing_phrases = [
                "Thanks for letting me know",
                "If it falls through",
                "let me know if anything changes",
                "my offer will still stand",
            ]
            should_skip = False
            if conv.last_message:
                for phrase in closing_phrases:
                    if phrase.lower() in conv.last_message.lower():
                        print(f"⏭️ Skipping conversation with closing message: {conv.last_message[:50]}...")
                        # Mark as closed for future runs
                        conv.status = "closed"
                        should_skip = True
                        break
            if should_skip:
                continue

            conversation_url = conv.conversation_url
            if not conversation_url:
                print(f"⚠️ Skipping conversation with no URL")
                continue

            # Extract message ID to check if we've already processed it in this session
            message_id = extract_message_id_from_url(conversation_url)
            if message_id in processed_message_ids:
                print(
                    f"⏭️ Skipping already processed conversation in this session: {conversation_url}"
                )
                continue

            # Add to processed set to avoid duplicate processing
            if message_id:
                processed_message_ids.add(message_id)

            # Process with direct URL and provide more detailed instructions based on negotiation script
            agent.add_new_task(f"""Check conversation at {conversation_url}

1. Go to the URL
2. Read all messages in the conversation carefully
3. Report the following information in this EXACT format:

SELLER_NAME: [name from conversation header/title]
PRODUCT_NAME: [product name from conversation header/title]
OUR_INITIAL_OFFER: $[the dollar amount from OUR first message that says "I can do $X cash"]
LAST_MESSAGE: [most recent message in the conversation - text only]
LAST_MESSAGE_FROM: [either "us" or "seller"]

4. Then analyze THE SELLER'S DIRECT MESSAGES (NOT Facebook system notifications) and report ONE of the following:

   IMPORTANT: Ignore Facebook system messages like "X reduced the price to $Y" or "X changed the listing" - these are NOT counter offers!
   A counter-offer is ONLY when the seller DIRECTLY writes a message with a price like "I want $400" or "How about $350" or just a number like "300"

   - If seller ACCEPTED our offer (said yes, ok, deal, agreed, etc): Reply "SELLER_ACCEPTED"
   - If seller made a DIRECT counter-offer (their own message with a different price): Reply "COUNTER_OFFER: $[their price]"
   - If seller simply said "no" or declined WITHOUT mentioning a price: Reply "SELLER_DECLINED"
   - If they asked about location/meeting place: Reply "SELLER_QUESTIONS: location"
   - If they asked about payment method: Reply "SELLER_QUESTIONS: payment"
   - If they asked about timing/when to meet: Reply "SELLER_QUESTIONS: timing"
   - If they asked about phone condition requirements: Reply "SELLER_QUESTIONS: condition"
   - If they mentioned other buyers: Reply "SELLER_QUESTIONS: other_buyers"
   - If they said item is sold: Reply "SELLER_QUESTIONS: sold"
   - If they asked for more details about us: Reply "SELLER_QUESTIONS: about_us"
   - If they want a different meeting place: Reply "SELLER_QUESTIONS: meeting_place"
   - If their message is unclear or very complex: Reply "NEEDS_HUMAN_HELP"
   - If no response from seller yet: Reply "NO_RESPONSE"
5. Wait for my instructions on how to respond""")

            result = await agent.run()

            # Properly extract the text content from the agent result
            # Using final_result() instead of str() to avoid capturing metadata
            if hasattr(result, 'final_result') and callable(result.final_result):
                result_text = result.final_result()
                if result_text is None:
                    result_text = ""
            else:
                result_text = str(result)

            result_str = result_text.lower() if isinstance(result_text, str) else str(result_text).lower()
            print(f"📄 Extracted result text: {result_str[:300]}...")

            # Update conversation with the result
            updated_conversation = await read_conversation(
                agent, conversation_url, messages_data, listings, result
            )

            if updated_conversation:
                # Update the conversation in the messages_data
                for i, existing_conv in enumerate(messages_data.conversations):
                    if existing_conv.conversation_url == conversation_url:
                        print(f"💾 Updating conversation {i + 1} in messages.json")
                        print(f"📊 New status: {updated_conversation.status}")
                        messages_data.conversations[i] = updated_conversation
                        break

                save_messages_json(messages_data)
                processed_count += 1
                print(
                    f"✅ Processed conversation {processed_count}/{MAX_CONVERSATIONS}"
                )
            else:
                print(f"⚠️ No conversation update returned for {conversation_url}")

            if processed_count < MAX_CONVERSATIONS:
                await asyncio.sleep(2)

        # Update stats
        messages_data.active_conversations = len(
            [
                c
                for c in messages_data.conversations
                if c.status not in ["closed", "deal_completed"]
            ]
        )
        messages_data.closed_conversations = len(
            [
                c
                for c in messages_data.conversations
                if c.status in ["closed", "deal_completed"]
            ]
        )
        messages_data.deals_closed = len(
            [c for c in messages_data.conversations if c.status == "deal_closed"]
        )
        save_messages_json(messages_data)

        # Summary
        print(f"\n--- Summary ---")
        print(f"Total: {messages_data.total_conversations}")
        print(f"Active: {messages_data.active_conversations}")
        print(f"Closed: {messages_data.closed_conversations}")
        print(f"Deals: {messages_data.deals_closed}")
        print(f"New: {new_count}")
        print(f"Processed: {processed_count}")

    finally:
        await browser_session.stop()


if __name__ == "__main__":
    asyncio.run(main())
