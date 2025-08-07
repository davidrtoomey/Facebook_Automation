#!/usr/bin/env python3
"""
Pricing manager utility for updating marketplace bot pricing data
Handles raw pricing data storage and margin calculations
Grading System (dynamic, but default iPhone-focused):
- GRADE_B: Used devices in good condition, not cracked/damaged
- GRADE_C: Cracked front glass with good/working LCD (no broken LCD)
- GRADE_D: Bad LCD with lines running through screen or LCD ink spots
- DOA: Dead on arrival - device has no power and won't turn on
- SWAP: Trade-in value for working phones in excellent condition
- GRADE_A: Like new condition phones
Added: Locked adjustment (e.g., 30% reduction if locked detected)
"""
import os
import json
import re
from typing import List, Dict, Optional
from datetime import datetime
from utils.config_loader import load_full_config
from utils.sqlite_manager import SQLiteStateManager  # For caching consistency with main

def round_to_nice_price(price: float, round_up: bool = False) -> int:
    """
    Round price to a professional round number ending in 0.
    Default: round down. Optional: round up.
    """
    if price <= 0:
        return int(price)
    base = int(price // 10) * 10
    return base + 10 if round_up and price % 10 > 0 else base

def update_pricing_data(raw_pricing_data: List[Dict], margin_percent: float = 20.0) -> bool:
    """
    Update config.json with new pricing data and calculate offer prices with margin.
    Also sync to SQLite for consistency.
    Note: Feed raw_pricing_data from your Google Doc scraper output.
    """
    try:
        config_file = os.path.expanduser("~/.marketplace-bot/config.json")
        os.makedirs(os.path.dirname(config_file), exist_ok=True)

        config = load_full_config() or {}

        current_margin = config.get("margin_percent", margin_percent)

        # Clean dollar signs
        cleaned_base_prices = []
        for item in raw_pricing_data:
            cleaned_item = item.copy()
            for price_field in ["swap", "grade_a", "grade_b", "grade_c", "grade_d", "doa"]:
                if price_field in cleaned_item and cleaned_item[price_field]:
                    try:
                        price_str = str(cleaned_item[price_field]).replace('$', '').strip()
                        cleaned_item[price_field] = float(price_str)
                    except ValueError:
                        pass
            cleaned_base_prices.append(cleaned_item)

        # Calculate offers
        offer_prices = []
        for item in cleaned_base_prices:
            offer_item = item.copy()
            for price_field in ["swap", "grade_a", "grade_b", "grade_c", "grade_d", "doa"]:
                if price_field in offer_item and isinstance(offer_item[price_field], (int, float)):
                    original_price = float(offer_item[price_field])
                    discounted_price = original_price * (1 - current_margin / 100)
                    rounded_price = round_to_nice_price(discounted_price)
                    offer_item[price_field] = str(rounded_price)
            offer_prices.append(offer_item)

        config.update({
            "margin_percent": current_margin,
            "base_prices": cleaned_base_prices,
            "offer_prices": offer_prices,
            "last_updated": datetime.now().isoformat(),
            "pricing_count": len(cleaned_base_prices)
        })

        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)

        # Sync to SQLite
        sqlite_manager = SQLiteStateManager()
        sqlite_manager.store_pricing_data(offer_prices)  # Assume new method in SQLiteManager: def store_pricing_data(self, data): self.conn.execute("INSERT OR REPLACE INTO pricing ...")

        print(f"✅ Updated pricing data with {len(raw_pricing_data)} models")
        return True

    except Exception as e:
        print(f"❌ Error updating pricing data: {e}")
        return False

def recalculate_offer_prices(new_margin_percent: float) -> bool:
    config = load_full_config() or {}
    base_prices = config.get("base_prices", [])
    if not base_prices:
        print("❌ No base pricing data")
        return False
    return update_pricing_data(base_prices, new_margin_percent)

def get_offer_price(listing_title: str, listing_description: str = "") -> Optional[Dict]:
    """Match listing to price using simple string matching."""
    try:
        # Check cache
        sqlite_manager = SQLiteStateManager()
        cache_key = f"{listing_title.lower()}|{listing_description.lower()}"
        cached = sqlite_manager.get_cached_offer_price(cache_key)
        if cached:
            return cached
            
        # Load prices
        config = load_full_config() or {}
        prices = config.get("base_prices", [])
        if not prices:
            return None
        
        text = f"{listing_title} {listing_description}".lower()
        
        # Detect grade
        grade = "grade_b"
        if any(x in text for x in ["dead", "won't turn on", "no power", "for parts"]):
            grade = "doa"
        elif any(x in text for x in ["lines on screen", "lcd damage", "ink spots", "bad lcd"]):
            grade = "grade_d"
        elif "crack" in text and "not crack" not in text and "lcd" not in text:
            grade = "grade_c"
        
        # Detect lock status
        is_locked = any(x in text for x in ["locked", "verizon", "att", "t-mobile", "sprint"]) and "unlocked" not in text
        lock_text = "carrier locked" if is_locked else "unlocked"
        
        # Find best match
        best_match = None
        best_score = 0
        
        for item in prices:
            model = item.get("model", "").lower()
            score = 0
            
            # Must match brand
            if "iphone" in text and "iphone" not in model:
                continue
                
            # Score components
            if lock_text in model:
                score += 20
            
            # Extract iPhone model number
            iphone_match = re.search(r'iphone\s*(\d+)', text)
            if iphone_match and iphone_match.group(1) in model:
                score += 15
                
            # Storage matching
            storage_match = re.search(r'(\d+)\s*gb', text)
            if storage_match and storage_match.group(1) in model:
                score += 10
                
            # Variants
            for variant in ['pro', 'max', 'plus', 'mini']:
                if variant in text and variant in model:
                    score += 5
            
            if score > best_score:
                best_score = score
                best_match = item
        
        if not best_match:
            return None
            
        offer_price = best_match.get(grade, best_match.get("grade_b", "0"))
        
        result = {
            'model': best_match.get('model', ''),
            'grade': grade,
            'offer_price': offer_price,
            'detected_condition': grade,
            'is_unlocked': not is_locked
        }
        
        sqlite_manager.cache_offer_price(cache_key, result)
        return result
        
    except:
        return None

if __name__ == "__main__":
    # Test with 2025 sample (from tools/context)
    sample_data = [
        {"model": "iPhone 15 Pro Max", "grade_b": "600", "grade_c": "480", "grade_d": "360", "doa": "180"},
        {"model": "iPhone 15 Pro", "grade_b": "480", "grade_c": "384", "grade_d": "288", "doa": "144"},
        # Add more from your Google Doc structure...
    ]
    update_pricing_data(sample_data, 20.0)
    price = get_offer_price("iPhone 15 Pro Max locked", "good but carrier locked")
    print(f"Test offer: {price}")
