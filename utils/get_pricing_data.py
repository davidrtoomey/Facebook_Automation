from browser_use import Agent 
from browser_use.browser.browser import BrowserProfile, BrowserSession
from browser_use.llm import ChatGoogle
from dotenv import load_dotenv
import os
import asyncio
import json
from config_loader import get_gemini_api_key, get_config_value, load_full_config
from pricing_manager import update_pricing_data

load_dotenv()

api_key = get_gemini_api_key()

print("Starting Google Sheets pricing scraper...")

# Use faster model for scraping
llm = ChatGoogle(model="gemini-2.5-flash-lite", api_key=api_key)

browser_profile = BrowserProfile(
    executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    user_data_dir='~/.config/browseruse/profiles/agent',
    headless=False,  # Changed to False to avoid bot detection
    keep_alive=True,
    chrome_args=[
        '--disable-blink-features=AutomationControlled',
        '--disable-web-security',
        '--disable-features=VizDisplayCompositor',
        '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
)

def check_pricing_cache():
    """Check if we have valid cached pricing data from the last 12 hours"""
    cache_path = os.path.expanduser("~/.marketplace-bot/pricing_cache.json")
    
    try:
        if not os.path.exists(cache_path):
            return False
            
        with open(cache_path, 'r') as f:
            cache_data = json.load(f)
        
        # Check if cache is within last 12 hours
        from datetime import datetime
        cache_time = datetime.fromisoformat(cache_data.get('timestamp', ''))
        now = datetime.now()
        hours_diff = (now - cache_time).total_seconds() / 3600
        
        if hours_diff <= 12:
            print(f"📦 Found valid pricing cache from {hours_diff:.1f} hours ago")
            print("✅ Skipping price fetch - using cached data")
            return True
        else:
            print(f"⏰ Cache is {hours_diff:.1f} hours old, fetching fresh data")
            return False
            
    except Exception as e:
        print(f"⚠️ Error checking cache: {e}")
        return False

async def main():
    print("🚀 Starting pricing data extraction...")
    
    # Check if we have recent cached data
    if check_pricing_cache():
        print("🎉 Pricing data is already up to date!")
        return
    
    # Google Sheets URL
    sheet_url = "https://docs.google.com/spreadsheets/d/1pu4Adxq4MGB6Qour0k__4gBdgnggWRoSVYnJUKgxzEw/edit?gid=0#gid=0"
    
    browser_session = BrowserSession(browser_profile=browser_profile)
    
    try:
        # Initialize main agent
        agent = Agent(
            task=f"Navigate to Google Sheets and extract iPhone pricing data", 
            llm=llm, 
            browser_session=browser_session
        )
        
        print("🌐 Navigating to Google Sheets...")
        
        # Navigate and scrape pricing data
        agent.add_new_task(f"""Navigate to this Google Sheets URL and extract ALL iPhone pricing data: {sheet_url}

IMPORTANT STEPS:
1. Wait 5 seconds before starting
2. Go to the URL: {sheet_url}
3. Wait 10 seconds for the sheet to load completely
4. If you get a 403 error, wait 15 seconds and try again
5. Look for and click on the "iPhone Used" tab at the bottom if it exists
6. Wait 5 seconds after clicking the tab
7. Scroll down to see ALL rows in the sheet
8. Extract ALL iPhone pricing data from the visible table

EXTRACTION REQUIREMENTS:
- Extract EVERY SINGLE ROW that contains an iPhone model - don't stop after one
- Look for iPhone 16, iPhone 15, iPhone 14, iPhone 13, iPhone 12, iPhone 11, iPhone XS, iPhone XR, iPhone X models
- For each iPhone model, get ALL the pricing columns (SWAP, Grade A, Grade B, Grade C, Grade D, DOA)
- Include the exact model name as it appears (including storage size like 128GB, 256GB, 512GB, 1TB)
- Include all price values even if they're $0 or empty
- DO NOT STOP after finding one iPhone - continue extracting until you've found ALL models

CRITICAL INSTRUCTIONS:
- You MUST extract EVERY SINGLE iPhone model in the entire spreadsheet - DO NOT STOP until you've found them all
- Scroll through the ENTIRE sheet from top to bottom to ensure you don't miss any rows
- Extract ALL storage sizes: 128GB, 256GB, 512GB, 1TB, etc.
- Extract ALL iPhone generations: 16, 15, 14, 13, 12, 11, XS, XR, X, etc.
- Extract ALL variants: regular, Plus, Pro, Pro Max, Mini, etc.
- DO NOT set any limit - extract EVERY iPhone you can find

OUTPUT FORMAT:
Return a complete JSON array with EVERY SINGLE iPhone model from the spreadsheet:

[
  {{
    "model": "iPhone 16 Pro Max 256GB Unlocked",
    "swap": "830",
    "grade_a": "820", 
    "grade_b": "800",  
    "grade_c": "620",
    "grade_d": "340",
    "doa": "200"
  }},
  {{
    "model": "iPhone 16 Pro 256GB Unlocked", 
    "swap": "750",
    "grade_a": "740",
    "grade_b": "720",
    "grade_c": "540", 
    "grade_d": "290",
    "doa": "150"
  }},
  ... (continue for EVERY SINGLE iPhone model in the spreadsheet - do not stop until you've extracted them all)
]

VERIFICATION: Before responding, scroll through the entire spreadsheet and count ALL iPhone models. Extract every single one you can find. There should be dozens of different iPhone models with various storage sizes and generations. Do not stop extracting until you've reached the bottom of the spreadsheet.
""")
        
        print("📊 Running pricing extraction...")
        result = await agent.run()
        
        if result.is_successful:
            print("✅ Pricing extraction completed!")
            
            # Extract JSON data from the agent's final message
            final_message = result.final_result() if hasattr(result, 'final_result') else str(result)
            print(f"Agent response: {final_message}")
            
            # Try to extract JSON from the response
            try:
                # Look for JSON array in the response
                import re
                json_match = re.search(r'\[.*\]', final_message, re.DOTALL)
                if json_match:
                    json_data = json_match.group(0)
                    
                    # Clean dollar signs from the JSON data before parsing
                    json_data = json_data.replace('"$', '"').replace('$', '')
                    # Additional cleaning for various dollar sign formats
                    json_data = re.sub(r'"\$(\d+)"', r'"\1"', json_data)  # "$123" -> "123"
                    json_data = re.sub(r':\s*"\$(\d+)"', r': "\1"', json_data)  # : "$123" -> : "123"
                    
                    # Validate and parse the JSON
                    parsed_data = json.loads(json_data)
                    
                    # Save raw data to project directory for reference
                    output_path = "/Users/macbook/Documents/code/buse-test/pricing_data_raw.json"
                    with open(output_path, 'w') as f:
                        json.dump(parsed_data, f, indent=2)
                    
                    print(f"✅ Successfully saved {len(parsed_data)} iPhone models to {output_path}")
                    
                    # Update marketplace-bot config with pricing data and margins
                    print("📊 Updating marketplace-bot configuration...")
                    success = update_pricing_data(parsed_data, margin_percent=20.0)
                    if success:
                        print("✅ Marketplace-bot configuration updated with 20% margin")
                    else:
                        print("❌ Failed to update marketplace-bot configuration")
                else:
                    print("⚠️ No JSON array found in agent response")
                    print("Raw response:", final_message)
                    
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse JSON: {e}")
                print("Raw response:", final_message)
            except Exception as e:
                print(f"❌ Error processing response: {e}")
                print("Raw response:", final_message)
        else:
            print("❌ Pricing extraction failed")
            print(f"Result: {result}")
            
    except Exception as e:
        print(f"❌ Error during extraction: {e}")
    
    finally:
        await browser_session.close()

if __name__ == "__main__":
    asyncio.run(main())
