#!/usr/bin/env python3

"""
Format raw pricing data JSON into marketplace bot config format

This script takes the raw scraped pricing data and formats it for use
in the marketplace bot configuration with applied margins.
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, Any, Optional


def parse_price(price_str: str) -> Optional[int]:
    """Parse price string to integer"""
    if not price_str:
        return None
    
    # Remove currency symbols and extra characters
    cleaned = re.sub(r'[^\d.]', '', str(price_str))
    
    if not cleaned:
        return None
    
    try:
        return int(float(cleaned))
    except (ValueError, TypeError):
        return None


def format_pricing_data(raw_data: list, margin_percentage: float = 20.0) -> Dict[str, Any]:
    """Format raw pricing data into config structure"""
    formatted_data = {}
    
    print(f"📊 Processing {len(raw_data)} iPhone models...")
    
    for item in raw_data:
        if not isinstance(item, dict):
            continue
            
        model_name = item.get('model', '').strip()
        if not model_name:
            continue
            
        print(f"🔄 Processing: {model_name}")
        
        model_pricing = {}
        
        # Map the scraped columns to our format
        column_mapping = {
            'swap': 'swap_value',
            'grade_a': 'grade_a', 
            'grade_b': 'grade_b',
            'grade_c': 'grade_c',
            'grade_d': 'grade_d',
            'doa': 'doa_value'
        }
        
        for raw_key, formatted_key in column_mapping.items():
            price_str = item.get(raw_key, '')
            price = parse_price(price_str)
            
            if price and price > 0:
                # Apply margin reduction for offer price
                offer_price = int(price * (1 - margin_percentage / 100))
                
                model_pricing[formatted_key] = {
                    'market_price': price,
                    'offer_price': offer_price
                }
                
                print(f"  ✅ {formatted_key}: ${price} → ${offer_price}")
        
        if model_pricing:
            formatted_data[model_name] = model_pricing
            print(f"✅ Added {model_name} with {len(model_pricing)} price points")
        else:
            print(f"⚠️ No valid pricing found for {model_name}")
    
    return formatted_data


def save_to_config(pricing_data: Dict[str, Any], margin_percentage: float = 20.0):
    """Save pricing data to marketplace bot config"""
    config_path = os.path.expanduser("~/.marketplace-bot/config.json")
    
    # Load existing config
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading existing config: {e}")
    
    # Update dynamic pricing section
    config['dynamic_pricing'] = {
        'enabled': True,
        'last_updated': datetime.now().isoformat(),
        'margin_percentage': margin_percentage,
        'data_source': 'google_sheets_scraped',
        'prices': pricing_data,
        'update_count': config.get('dynamic_pricing', {}).get('update_count', 0) + 1
    }
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    
    # Save updated config
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Saved pricing data to {config_path}")
    print(f"📊 Updated {len(pricing_data)} iPhone models")


def main():
    print("=" * 60)
    print("🔧 PRICING DATA FORMATTER")
    print("=" * 60)
    
    # Check if raw data file exists
    raw_file = "pricing_data_raw.json"
    if not os.path.exists(raw_file):
        print(f"❌ Raw pricing data file not found: {raw_file}")
        print("Run get_pricing_data.py first to scrape the data")
        return False
    
    # Load raw data
    try:
        with open(raw_file, 'r') as f:
            raw_data = json.load(f)
        print(f"📥 Loaded raw data from {raw_file}")
    except Exception as e:
        print(f"❌ Error loading raw data: {e}")
        return False
    
    # Format the data
    margin_percentage = 20.0
    formatted_data = format_pricing_data(raw_data, margin_percentage)
    
    if not formatted_data:
        print("❌ No valid pricing data found after formatting")
        return False
    
    # Save to config
    save_to_config(formatted_data, margin_percentage)
    
    # Also save formatted data to a separate file for inspection
    formatted_file = "pricing_data_formatted.json"
    with open(formatted_file, 'w') as f:
        json.dump(formatted_data, f, indent=2)
    print(f"📄 Also saved formatted data to {formatted_file} for inspection")
    
    print("\n✅ Pricing data formatting completed successfully!")
    return True


if __name__ == "__main__":
    main()