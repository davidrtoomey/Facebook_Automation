#!/usr/bin/env python3
"""
Cleanup script to remove irrelevant listings from the database and JSON files.
"""

import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def is_relevant_listing(title, product):
    """Check if a listing title matches the product it was scraped for."""
    if not title or not product:
        return False

    title_lower = title.lower().strip()
    product_lower = product.lower().strip()

    # Remove common artifacts from title
    title_lower = title_lower.replace('\n', ' ').replace('\\n', ' ').strip()

    # Extract key parts of the product (e.g., "iPhone 13 Pro Max" -> ["iphone", "13", "pro", "max"])
    product_parts = product_lower.split()

    # For iPhone searches, validate properly
    if "iphone" in product_lower:
        # Must contain "iphone"
        if "iphone" not in title_lower:
            return False

        # Check for model number
        model_numbers = [p for p in product_parts if p.isdigit() or p in ["se", "xr", "xs", "x"]]
        if model_numbers:
            if not any(num in title_lower for num in model_numbers):
                return False

        # If searching for "Pro Max", title must have "pro max"
        if "pro" in product_lower and "max" in product_lower:
            if "pro max" not in title_lower and "pro-max" not in title_lower:
                # Check if both "pro" and "max" appear
                if not ("pro" in title_lower and "max" in title_lower):
                    return False
        # If searching for just "Pro" (not "Pro Max"), title must have "pro"
        elif "pro" in product_lower and "max" not in product_lower:
            if "pro" not in title_lower:
                return False
        # If searching for "Plus", title must have "plus"
        elif "plus" in product_lower:
            if "plus" not in title_lower:
                return False

    return True


def cleanup_listings():
    """Remove irrelevant listings from JSON and SQLite database."""

    # Load listings.json
    listings_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "listings.json")

    if not os.path.exists(listings_file):
        print("No listings.json found")
        return

    with open(listings_file, 'r') as f:
        listings = json.load(f)

    original_count = len(listings)
    print(f"Original listings count: {original_count}")

    # Categorize listings
    kept = []
    removed_irrelevant = []
    removed_no_title_not_messaged = []
    removed_title_mismatch = []

    for listing in listings:
        listing_id = listing.get('listing_id')
        title = listing.get('title')
        product = listing.get('product', '')
        messaged = listing.get('messaged', 0)
        relevant = listing.get('relevant', 1)
        unavailable = listing.get('unavailable', 0)

        # Clean title
        if title:
            title = title.replace('\\n', ' ').replace('\n', ' ').strip()
            # Remove corrupted data that leaked into title
            if 'ActionResult' in title or 'extracted_content' in title:
                title = title.split('ActionResult')[0].split('extracted_content')[0].strip()
                if title.endswith(','):
                    title = title[:-1].strip()

        # Skip unavailable listings that haven't been messaged
        if unavailable and not messaged:
            removed_irrelevant.append(listing)
            print(f"  Removing unavailable: {listing_id}")
            continue

        # Skip listings marked as not relevant
        if relevant == 0:
            removed_irrelevant.append(listing)
            print(f"  Removing marked irrelevant: {listing_id}")
            continue

        # Keep listings that have been messaged (we've already contacted them)
        if messaged:
            kept.append(listing)
            continue

        # For non-messaged listings, check if they have a title and if it matches
        if not title or title.lower() == 'unknown':
            removed_no_title_not_messaged.append(listing)
            print(f"  Removing no title (not messaged): {listing_id}")
            continue

        # Validate title matches product
        if not is_relevant_listing(title, product):
            removed_title_mismatch.append(listing)
            print(f"  Removing title mismatch: '{title[:50]}...' doesn't match '{product}'")
            continue

        # Listing passes all checks
        kept.append(listing)

    # Save cleaned listings
    with open(listings_file, 'w') as f:
        json.dump(kept, f, indent=4)

    print(f"\n=== Cleanup Summary ===")
    print(f"Original count: {original_count}")
    print(f"Kept: {len(kept)}")
    print(f"Removed (marked irrelevant/unavailable): {len(removed_irrelevant)}")
    print(f"Removed (no title, not messaged): {len(removed_no_title_not_messaged)}")
    print(f"Removed (title doesn't match product): {len(removed_title_mismatch)}")
    print(f"Total removed: {original_count - len(kept)}")

    # Also clean SQLite database
    try:
        from utils.sqlite_manager import SQLiteStateManager
        manager = SQLiteStateManager()

        # Get all listing IDs to remove
        ids_to_remove = []
        ids_to_remove.extend([l.get('listing_id') for l in removed_irrelevant])
        ids_to_remove.extend([l.get('listing_id') for l in removed_no_title_not_messaged])
        ids_to_remove.extend([l.get('listing_id') for l in removed_title_mismatch])

        if ids_to_remove:
            # Remove from SQLite
            conn = manager.get_connection()
            cursor = conn.cursor()
            for lid in ids_to_remove:
                if lid:
                    cursor.execute("DELETE FROM listings WHERE listing_id = ?", (lid,))
            conn.commit()
            print(f"\nRemoved {len(ids_to_remove)} listings from SQLite database")
    except Exception as e:
        print(f"\nWarning: Could not clean SQLite database: {e}")

    return kept


if __name__ == "__main__":
    cleanup_listings()
