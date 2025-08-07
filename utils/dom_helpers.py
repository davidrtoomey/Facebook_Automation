"""
DOM Helper utilities for Facebook Marketplace automation optimization
Provides fast, direct browser checks to reduce LLM dependency
"""

import asyncio
from typing import Optional, Dict, Any, List
from playwright.async_api import Page, TimeoutError

# Facebook Marketplace selector constants
SELECTORS = {
    'listing_title': '[data-testid="marketplace-listing-title"], h1[data-testid="fb-marketplace-listing-title"], h1.x1heor9g, .x1lliihq h1',
    'listing_description': '[data-testid="marketplace-listing-description"], .x11i5rnm.x1s85apg, .x1lliihq .x193iq5w, div[dir="auto"] span',
    'seller_name': '[data-testid="seller-name"], [aria-label*="seller"], .x1e558r4 .x193iq5w, a[role="link"] .x1lliihq .x6s0dn4',
    'price_info': '[data-testid="marketplace-price"], .x1lliihq .x6s0dn4, [data-testid="pdp-primary-price"]',
    'message_button': '[aria-label="Message"], [data-testid="message-button"], text="Message"',
    'message_again_button': 'text="Message Again", [aria-label="Message Again"]',
    'sold_indicator': 'text="Sold", text="No longer available", text="Removed", text="Deleted", [data-testid="sold-label"]',
    'listing_unavailable': 'text="This content isn\'t available right now", text="Content not found", text="Page not found"',
    'login_required': 'text="Log In", text="Sign Up", [data-testid="royal_login_form"]',
    'damage_keywords': 'text*="crack", text*="broken", text*="damage", text*="repair", text*="scratched"',
    'unlocked_keywords': 'text*="unlocked", text*="factory unlocked", text*="carrier unlocked"',
    'locked_keywords': 'text*="locked", text*="network locked", text*="carrier locked"'
}

class DOMChecker:
    """Fast DOM-based checks to replace LLM calls"""
    
    def __init__(self, page: Page):
        self.page = page
        self._cache = {}  # Cache results within session
    
    async def is_listing_available(self) -> bool:
        """Check if listing is available (not sold/removed)"""
        cache_key = f"available_{self.page.url}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            # Check for sold/unavailable indicators
            sold_element = await self.page.locator(SELECTORS['sold_indicator']).first.wait_for(timeout=2000)
            if sold_element:
                self._cache[cache_key] = False
                return False
        except TimeoutError:
            pass
            
        try:
            # Check for content unavailable messages
            unavailable_element = await self.page.locator(SELECTORS['listing_unavailable']).first.wait_for(timeout=2000)
            if unavailable_element:
                self._cache[cache_key] = False
                return False
        except TimeoutError:
            pass
        
        # If no negative indicators found, assume available
        self._cache[cache_key] = True
        return True
    
    async def is_already_messaged(self) -> bool:
        """Check if we've already messaged this seller"""
        try:
            # Look for "Message Again" button which indicates previous conversation
            message_again = await self.page.locator(SELECTORS['message_again_button']).first.wait_for(timeout=3000)
            return message_again is not None
        except TimeoutError:
            return False
    
    async def extract_listing_info(self) -> Dict[str, Any]:
        """Extract basic listing information using DOM selectors"""
        info = {
            'title': None,
            'description': None,
            'seller_name': None,
            'price': None,
            'condition_hints': []
        }
        
        # Extract title
        try:
            title_element = await self.page.locator(SELECTORS['listing_title']).first.wait_for(timeout=5000)
            if title_element:
                info['title'] = await title_element.inner_text()
        except TimeoutError:
            pass
        
        # Extract description
        try:
            description_element = await self.page.locator(SELECTORS['listing_description']).first.wait_for(timeout=3000)
            if description_element:
                info['description'] = await description_element.inner_text()
        except TimeoutError:
            # Fallback: try to extract from page content
            try:
                page_content = await self.page.content()
                # Look for description patterns in the HTML
                import re
                desc_match = re.search(r'<div[^>]*>([^<]+(?:unlocked|locked|GB|damaged|condition|model|excellent|good|fair)[^<]*)</div>', page_content, re.IGNORECASE)
                if desc_match:
                    info['description'] = desc_match.group(1).strip()
            except:
                pass
        
        # Extract seller name
        try:
            seller_element = await self.page.locator(SELECTORS['seller_name']).first.wait_for(timeout=3000)
            if seller_element:
                seller_text = await seller_element.inner_text()
                # Clean up seller name (remove "Seller:" prefix etc)
                info['seller_name'] = seller_text.replace('Seller:', '').strip()
        except TimeoutError:
            pass
        
        # Extract price
        try:
            price_element = await self.page.locator(SELECTORS['price_info']).first.wait_for(timeout=3000)
            if price_element:
                info['price'] = await price_element.inner_text()
        except TimeoutError:
            pass
        
        # Check for condition hints
        page_content = await self.page.content()
        page_text = page_content.lower()
        
        if any(keyword in page_text for keyword in ['crack', 'broken', 'damage', 'repair', 'scratched']):
            info['condition_hints'].append('damaged')
        
        if any(keyword in page_text for keyword in ['unlocked', 'factory unlocked', 'carrier unlocked']):
            info['condition_hints'].append('unlocked')
        elif any(keyword in page_text for keyword in ['locked', 'network locked', 'carrier locked']):
            info['condition_hints'].append('locked')
        
        return info
    
    async def identify_product_dynamically(self, listing_info: dict) -> dict:
        """Use Gemini LLM to intelligently identify any product and determine appropriate pricing"""
        try:
            title = listing_info.get('title') or ''
            description = listing_info.get('description') or ''
            price = listing_info.get('price') or ''
            condition_hints = listing_info.get('condition_hints', [])
            
            # If we have no meaningful data, fall back to basic analysis
            if not title and not description:
                print("⚠️ No title or description available for LLM analysis")
                return self._fallback_identification(condition_hints)
            
            # Import LLM (same as used in offer_agent.py)
            try:
                import sys
                import os
                sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from offer_agent import llm  # Use the existing LLM instance
            except ImportError:
                print("⚠️ Could not import LLM, using fallback identification")
                return self._fallback_identification(condition_hints)
            
            # Create comprehensive prompt for product identification only
            prompt = f"""Analyze this Facebook Marketplace listing and identify the specific product being sold:

TITLE: {title}
DESCRIPTION: {description}
PRICE: {price}
CONDITION HINTS: {', '.join(condition_hints)}

Respond with JSON in this exact format:
{{
    "product_name": "exact product name (e.g., 'iPhone 13 Pro Max', 'iPhone 14 Pro', 'Samsung Galaxy S24', 'MacBook Pro')",
    "category": "iphone|samsung|laptop|tablet|gaming|electronics|furniture|clothing|other",
    "model_details": "specific model info (e.g., '128GB Space Gray', '256GB Unlocked', '13-inch M2')",
    "condition": {{
        "unlocked": true/false,
        "damaged": true/false,
        "locked": true/false
    }},
    "reasoning": "brief explanation of identification"
}}

Focus on identifying:
- Exact product names (iPhone 13 Pro Max, iPhone 14 Pro, Samsung Galaxy S23, etc.)
- Network status (unlocked/locked for phones)
- Physical condition (damaged/working)
- Storage capacity and color if mentioned

Only respond with valid JSON, no other text."""

            # Get LLM response
            try:
                response = await llm.ainvoke(prompt)
                result_text = response.content if hasattr(response, 'content') else str(response)
                
                # Parse JSON response
                import json
                import re
                
                # Extract JSON from response
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    
                    # Return structured result with product identification (no pricing, no confidence)
                    return {
                        'product_name': result.get('product_name', 'Unknown Product'),
                        'category': result.get('category', 'other'),
                        'model_details': result.get('model_details'),
                        'condition': result.get('condition', {
                            'unlocked': 'unlocked' in condition_hints,
                            'damaged': 'damaged' in condition_hints,
                            'locked': 'locked' in condition_hints
                        }),
                        'reasoning': result.get('reasoning', 'LLM analysis'),
                        'detected_from': 'gemini_llm'
                    }
                else:
                    print(f"⚠️ Could not parse JSON from LLM response: {result_text[:200]}")
                    return self._fallback_identification(condition_hints)
                    
            except Exception as llm_error:
                print(f"⚠️ LLM call failed: {llm_error}")
                return self._fallback_identification(condition_hints)
            
        except Exception as e:
            print(f"Error in dynamic product identification: {e}")
            return self._fallback_identification(condition_hints)
    
    def _fallback_identification(self, condition_hints):
        """Fallback when LLM analysis fails"""
        return {
            'product_name': 'Unknown Product',
            'category': 'other',
            'model_details': None,
            'condition': {
                'unlocked': 'unlocked' in condition_hints,
                'damaged': 'damaged' in condition_hints,
                'locked': 'locked' in condition_hints
            },
            'reasoning': 'Fallback - insufficient data for analysis',
            'detected_from': 'fallback'
        }
    
    async def can_message_seller(self) -> bool:
        """Check if message button is present and clickable"""
        try:
            message_button = await self.page.locator(SELECTORS['message_button']).first.wait_for(timeout=5000)
            if message_button:
                is_visible = await message_button.is_visible()
                is_enabled = await message_button.is_enabled()
                return is_visible and is_enabled
            return False
        except TimeoutError:
            return False
    
    async def navigate_and_verify(self, url: str, max_retries: int = 3) -> bool:
        """Navigate to URL with retry logic and verify success"""
        for attempt in range(max_retries):
            try:
                # Navigate with increased timeout
                await self.page.goto(url, timeout=30000, wait_until='networkidle')
                
                # Check if navigation was successful
                if self.page.url == url or url in self.page.url:
                    # Check if we need to log in
                    try:
                        login_element = await self.page.locator(SELECTORS['login_required']).first.wait_for(timeout=2000)
                        if login_element:
                            print(f"Login required for {url}")
                            return False
                    except TimeoutError:
                        pass
                    
                    return True
                else:
                    print(f"Navigation failed, attempt {attempt + 1}: Expected {url}, got {self.page.url}")
                    
            except Exception as e:
                print(f"Navigation error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        return False
    
    def clear_cache(self):
        """Clear the internal cache"""
        self._cache.clear()

async def quick_listing_check(page: Page, url: str, target_products: List[str]) -> Dict[str, Any]:
    """
    Perform a quick, optimized check of a listing using DOM queries
    Returns comprehensive information to minimize LLM calls
    """
    checker = DOMChecker(page)
    
    # Navigate to the listing
    if not await checker.navigate_and_verify(url):
        return {
            'url': url,
            'available': False,
            'reason': 'navigation_failed',
            'skip': True
        }
    
    # Check availability first (fastest elimination)
    if not await checker.is_listing_available():
        return {
            'url': url,
            'available': False,
            'reason': 'listing_unavailable',
            'skip': True
        }
    
    # Check if already messaged (second fastest elimination)
    already_messaged = await checker.is_already_messaged()
    if already_messaged:
        return {
            'url': url,
            'available': True,
            'already_messaged': True,
            'reason': 'already_messaged',
            'skip': True
        }
    
    # Extract listing info and identify product using Gemini
    listing_info = await checker.extract_listing_info()
    identified_product = await checker.identify_product_dynamically(listing_info)
    
    # Check if identified product matches any target products
    matched_product = None
    for target_product in target_products:
        product_name = identified_product.get('product_name', '').lower()
        target_name = target_product.lower()
        
        # Check for exact or close matches
        if target_name in product_name or product_name in target_name:
            matched_product = target_product
            break
    
    if not matched_product:
        return {
            'url': url,
            'available': True,
            'already_messaged': False,
            'relevant': False,
            'reason': 'not_relevant',
            'skip': True
        }
    
    # Check messaging capability
    can_message = await checker.can_message_seller()
    
    return {
        'url': url,
        'available': True,
        'already_messaged': False,
        'relevant': True,
        'matched_product': matched_product,
        'can_message': can_message,
        'listing_info': listing_info,
        'skip': False,
        'reason': 'ready_for_processing'
    }