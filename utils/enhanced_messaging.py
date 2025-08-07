#!/usr/bin/env python3

"""
Enhanced messaging module with success pattern caching

This module provides improved messaging functionality that learns from
successful patterns and uses them to increase messaging reliability.

@file purpose: Enhanced messaging with pattern learning and caching for improved reliability
"""

import time
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from utils.messaging_success_cache import MessagingSuccessCache, create_success_pattern_from_agent_result


class EnhancedMessenger:
    """Enhanced messaging class that learns from successful patterns"""
    
    def __init__(self, cache_path: str = None):
        """
        Initialize enhanced messenger
        
        Args:
            cache_path: Path to pattern cache database
        """
        self.cache = MessagingSuccessCache(cache_path)
        self.current_attempt_data = {}
    
    def create_enhanced_messaging_task(self, url: str, pricing: Dict[str, int]) -> str:
        """
        Create an enhanced messaging task that uses cached successful patterns
        
        Args:
            url: Facebook listing URL
            pricing: Pricing dictionary with offer amounts
            
        Returns:
            Enhanced task prompt with cached pattern guidance
        """
        # Get successful patterns for this URL type
        patterns = self.cache.get_best_patterns_for_url(url, limit=3)
        
        base_task = f'''Continue with messaging using the correct pricing:

STEP 6: Read the item description and compose appropriate message:
- If mentions "carrier unlocked" or "factory unlocked": Type exactly "Hi I can do ${pricing['base_offer_unlocked']} cash for it"
- If mentions "network locked" or specific carrier: Type exactly "Hi I can do ${pricing['base_offer_locked']} cash for it"  
- If mentions damage/cracked/broken: Type exactly "Hi, can you tell me more about the damage?"
- Otherwise: Type exactly "Hi I can do ${pricing['base_offer_unlocked']} cash for it"

IMPORTANT: Type the message exactly as shown above. Do not add greetings like "Good evening" or modify the template.

STEP 7: Click Send button to send the message'''
        
        if patterns:
            print(f"🧠 Found {len(patterns)} successful patterns for similar URLs")
            
            # Add pattern-based guidance
            enhanced_task = base_task + f'''

ENHANCED GUIDANCE FROM SUCCESSFUL PATTERNS:
Based on {len(patterns)} previously successful messaging attempts, try these proven approaches:

MESSAGING APPROACH PRIORITY:
1. FIRST TRY - Most Successful Pattern (Score: {patterns[0].effectiveness_score:.2f}):
   - Look for these working selectors: {', '.join(patterns[0].dom_selectors[:3])}
   - Success indicators to watch for: {', '.join(patterns[0].success_indicators[:2])}
   
2. FALLBACK METHODS (if first approach fails):
   - Alternative selectors from successful attempts: {', '.join(patterns[1].dom_selectors[:3]) if len(patterns) > 1 else 'Standard Facebook selectors'}
   - Try different button text variations: "Message", "Contact Seller", "Send Message"

STEP-BY-STEP SUCCESS PATTERN:
{self._format_pattern_steps(patterns[0] if patterns else None)}

TROUBLESHOOTING (if elements not found):
- Wait 2-3 seconds for page to fully load
- Scroll down to ensure message button is visible
- Look for message button in different locations (top, bottom, sidebar)
- Try clicking seller name first, then look for message option

SUCCESS VALIDATION:
- After sending, look for these success signs: {', '.join(patterns[0].success_indicators) if patterns else 'message sent confirmation'}
- Report current URL to capture message thread ID
- Confirm message appears in conversation thread'''
        else:
            print("💡 No cached patterns found - using standard approach")
            enhanced_task = base_task + '''

TROUBLESHOOTING GUIDANCE (Learning Mode):
Since we're building success patterns, please be extra thorough:

- DOCUMENT ALL SUCCESSFUL STEPS: Report each successful click/interaction
- CAPTURE WORKING SELECTORS: Note which buttons/inputs worked  
- WAIT FOR ELEMENTS: Allow 2-3 seconds between actions
- SCROLL IF NEEDED: Ensure all elements are visible before clicking
- REPORT CURRENT URL: After successful send, report the current page URL

DETAILED SUCCESS REPORTING:
Please report in this format when successful:
- SUCCESSFUL_STEP: [describe what worked]
- WORKING_SELECTOR: [CSS selector or element description that worked]  
- SUCCESS_INDICATOR: [text or element that confirmed success]
- CURRENT_URL: [final URL after sending message]'''
        
        return enhanced_task
    
    def _format_pattern_steps(self, pattern: Any) -> str:
        """Format pattern steps for display in task prompt"""
        if not pattern or not pattern.steps:
            return "No specific pattern steps available"
        
        formatted_steps = []
        for i, step in enumerate(pattern.steps[:5], 1):  # Limit to 5 steps
            action = step.get('action', 'unknown_action')
            description = step.get('description', step.get('text', 'No description'))
            formatted_steps.append(f"   {i}. {action.replace('_', ' ').title()}: {description}")
        
        return '\n'.join(formatted_steps)
    
    def process_messaging_result(self, url: str, agent_result: str, 
                               message_result: str, message_sent: bool,
                               execution_time_ms: int = None) -> Optional[str]:
        """
        Process the results of a messaging attempt and cache successful patterns
        
        Args:
            url: The listing URL
            agent_result: Result from the first agent task
            message_result: Result from the messaging task
            message_sent: Whether message was successfully sent
            execution_time_ms: Time taken for the messaging attempt
            
        Returns:
            Pattern ID if cached, None otherwise
        """
        combined_result = f"{agent_result} {message_result}"
        
        # Record the attempt
        start_time = time.time()
        
        if message_sent:
            print("🎯 Messaging successful - analyzing pattern for caching...")
            
            # Create pattern from successful result
            pattern_data = create_success_pattern_from_agent_result(
                url, combined_result, message_sent
            )
            
            if pattern_data:
                # Cache the successful pattern
                pattern_id = self.cache.cache_successful_pattern(
                    url=url,
                    steps=pattern_data['steps'],
                    dom_selectors=pattern_data['dom_selectors'],
                    success_indicators=pattern_data['success_indicators'],
                    failure_recovery=pattern_data['failure_recovery']
                )
                
                # Record successful usage
                self.cache.record_pattern_usage(
                    pattern_id=pattern_id,
                    url=url,
                    success=True,
                    execution_time_ms=execution_time_ms
                )
                
                print(f"✅ Cached successful messaging pattern: {pattern_id[:8]}...")
                return pattern_id
            else:
                print("⚠️ Could not extract useful pattern from successful attempt")
        else:
            print("❌ Messaging failed - recording failure for pattern learning")
            
            # If we tried to use a pattern, record its failure
            patterns = self.cache.get_best_patterns_for_url(url, limit=1)
            if patterns:
                self.cache.record_pattern_usage(
                    pattern_id=patterns[0].pattern_id,
                    url=url,
                    success=False,
                    execution_time_ms=execution_time_ms,
                    error_message="Messaging attempt failed"
                )
        
        return None
    
    def get_messaging_statistics(self) -> Dict[str, Any]:
        """Get statistics about messaging patterns and success rates"""
        return self.cache.get_pattern_statistics()
    
    def cleanup_old_patterns(self):
        """Clean up old or ineffective patterns"""
        self.cache.cleanup_old_patterns()
    
    def export_patterns_for_analysis(self, output_file: str = None) -> str:
        """Export patterns for analysis and debugging"""
        return self.cache.export_patterns_for_debugging(output_file)


async def enhance_messaging_workflow(agent, listing_item, pricing, index):
    """
    Enhanced messaging workflow that uses pattern caching
    
    This is a replacement for the messaging portion of process_single_url
    """
    url = listing_item['url']
    listing_id = listing_item.get('listing_id')
    
    # Initialize enhanced messenger
    messenger = EnhancedMessenger()
    
    print(f"🧠 Starting enhanced messaging for Listing ID {listing_id}")
    
    # Record start time for performance tracking
    start_time = time.time()
    
    try:
        # Create enhanced messaging task with pattern guidance
        enhanced_task = messenger.create_enhanced_messaging_task(url, pricing)
        
        # Run the enhanced messaging task
        print(f"📝 Running enhanced messaging task for URL {index + 1}...")
        message_result = await agent.run(enhanced_task)
        
        # Calculate execution time
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        print(f'📤 Enhanced messaging completed for URL {index + 1}: {"successful" if message_result.is_successful else "not successful"}')
        
        # Determine if message was sent
        combined_result_str = str(message_result).lower()
        message_sent = message_result.is_successful and any(keyword in combined_result_str for keyword in [
            "message sent", "sent successfully", "successfully sent", 
            "message delivered", "sent message", "completed successfully"
        ])
        
        # Process the result and potentially cache the pattern
        pattern_id = messenger.process_messaging_result(
            url=url,
            agent_result="",  # We don't have the first agent result here
            message_result=str(message_result),
            message_sent=message_sent,
            execution_time_ms=execution_time_ms
        )
        
        if pattern_id:
            print(f"🎯 New successful pattern cached: {pattern_id[:8]}...")
        
        # Show messaging statistics periodically
        if index % 10 == 0:  # Every 10 attempts
            stats = messenger.get_messaging_statistics()
            print(f"📊 Messaging Success Rate: {stats['overall_success_rate']:.2%} ({stats['total_patterns']} patterns)")
        
        return message_result, message_sent, execution_time_ms
        
    except Exception as e:
        execution_time_ms = int((time.time() - start_time) * 1000)
        print(f"❌ Enhanced messaging error: {e}")
        
        # Record the failure
        patterns = messenger.cache.get_best_patterns_for_url(url, limit=1)
        if patterns:
            messenger.cache.record_pattern_usage(
                pattern_id=patterns[0].pattern_id,
                url=url,
                success=False,
                execution_time_ms=execution_time_ms,
                error_message=str(e)
            )
        
        raise e


# Integration helper for offer_agent.py
def create_enhanced_process_single_url():
    """
    Factory function to create an enhanced version of process_single_url
    that includes pattern caching
    """
    messenger = EnhancedMessenger()
    
    async def enhanced_process_single_url(agent, listing_item, index):
        """Enhanced version of process_single_url with pattern caching"""
        url = listing_item['url']
        listing_id = listing_item.get('listing_id')
        print(f"\n--- Enhanced Processing Listing ID {listing_id} (URL {index + 1}): {url} ---")
        
        # Skip if already messaged (safety check)
        if listing_item.get('messaged'):
            print(f"Skipping Listing ID {listing_id} - already messaged this seller")
            return {"url": url, "status": "skipped", "result": "Already messaged", "message_sent": False}
        
        start_time = time.time()
        
        try:
            # STEP 1: Initial listing analysis (unchanged)
            print(f"🌐 Starting browser task for URL: {url}")
            agent.add_new_task(f'''Check this Facebook Marketplace URL efficiently: {url}

STEP 1: Navigate to the URL

STEP 2: IMMEDIATELY check if we should skip this listing
- If listing shows "Sold", "No longer available", "Removed", "Deleted", or similar → Report "LISTING_UNAVAILABLE" and STOP immediately
- If page shows error, 404, or listing not found → Report "LISTING_UNAVAILABLE" and STOP immediately

STEP 3: Extract basic listing information
- Report "LISTING_TITLE: [exact title from the listing]"
- Report "SELLER_NAME: [seller's first name from their profile]"

STEP 4: Check if this is a relevant device for any configured product
- Look at title, description, and images
- Check if it matches ANY of these configured products: iPhone 13 Pro Max
- If it's accessories (cases, chargers, etc.) or none of the configured models, report "NOT_RELEVANT" and STOP immediately
- If it matches any configured product, report "MATCHED_PRODUCT: [product name]" and continue

STEP 5: Find and click the "Message" or "Contact Seller" button

STEP 6: Check for existing conversation
- If you see "Message Again" or previous messages from us, report "ALREADY_MESSAGED" and STOP immediately
- If fresh message box, report "READY_FOR_MESSAGE" and wait for instructions

IMPORTANT: STOP immediately when you encounter LISTING_UNAVAILABLE, NOT_RELEVANT, or ALREADY_MESSAGED conditions. Do NOT continue with unnecessary steps.
''')
            
            print(f"🤖 Running agent task for URL {index + 1}...")
            result = await agent.run()
            print(f'✅ Agent task completed for URL {index + 1}: {"successful" if result.is_successful else "not successful"}')
            
            result_str = str(result).lower()
            
            # Handle early termination conditions (unchanged)
            if "listing_unavailable" in result_str or "listing unavailable" in result_str:
                print(f"Skipping Listing ID {listing_id} - listing is sold or unavailable")
                return {"url": url, "status": "skipped", "result": "Listing sold or unavailable", "message_sent": False}
            
            if "not_relevant" in result_str or "not relevant" in result_str:
                print(f"Skipping Listing ID {listing_id} - not relevant to any configured product")
                return {"url": url, "status": "skipped", "result": "Not relevant - accessory or different model", "message_sent": False}
            
            if "already_messaged" in result_str or "already messaged" in result_str:
                print(f"Skipping Listing ID {listing_id} - already messaged this seller")
                return {"url": url, "status": "skipped", "result": "Already messaged this seller", "message_sent": False}
            
            # STEP 2: Enhanced messaging with pattern caching
            if "ready_for_message" not in result_str and "ready for message" not in result_str:
                print(f"⚠️ URL {index + 1} - Unexpected result, listing may not be ready for messaging")
                print(f"Result preview: {result_str[:200]}...")
            
            # Get pricing (simplified for this example)
            pricing = {
                'base_offer_unlocked': 300,
                'base_offer_locked': 250
            }
            
            # Use enhanced messaging
            enhanced_task = messenger.create_enhanced_messaging_task(url, pricing)
            
            print(f"🧠 Running enhanced messaging task for URL {index + 1}...")
            message_result = await agent.run(enhanced_task)
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Process results
            combined_result_str = (str(result) + " " + str(message_result)).lower()
            message_sent = message_result.is_successful and any(keyword in combined_result_str for keyword in [
                "message sent", "sent successfully", "successfully sent", 
                "message delivered", "sent message", "completed successfully"
            ])
            
            # Cache the pattern
            pattern_id = messenger.process_messaging_result(
                url=url,
                agent_result=str(result),
                message_result=str(message_result),
                message_sent=message_sent,
                execution_time_ms=execution_time_ms
            )
            
            print(f"📊 Final status for URL {index + 1}: messaged={message_sent}, cached_pattern={pattern_id is not None}")
            
            return {
                "url": url, 
                "status": "completed", 
                "result": str(message_result),
                "message_sent": message_sent,
                "pattern_cached": pattern_id is not None,
                "execution_time_ms": execution_time_ms
            }
            
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            print(f"Error in enhanced processing for URL {index + 1}: {e}")
            
            # Record pattern failure if we were using one
            patterns = messenger.cache.get_best_patterns_for_url(url, limit=1)
            if patterns:
                messenger.cache.record_pattern_usage(
                    pattern_id=patterns[0].pattern_id,
                    url=url,
                    success=False,
                    execution_time_ms=execution_time_ms,
                    error_message=str(e)
                )
            
            return {"url": url, "status": "error", "error": str(e), "message_sent": False}
    
    return enhanced_process_single_url


if __name__ == "__main__":
    """Test the enhanced messaging functionality"""
    print("=" * 60)
    print("🧪 ENHANCED MESSAGING - TEST MODE")
    print("=" * 60)
    
    messenger = EnhancedMessenger()
    
    # Test creating enhanced task
    test_url = "https://www.facebook.com/marketplace/item/123456789"
    test_pricing = {'base_offer_unlocked': 300, 'base_offer_locked': 250}
    
    enhanced_task = messenger.create_enhanced_messaging_task(test_url, test_pricing)
    print("📝 Enhanced task created:")
    print(enhanced_task[:300] + "...")
    
    # Test statistics
    stats = messenger.get_messaging_statistics()
    print(f"\n📊 Current Statistics:")
    print(f"  Total patterns: {stats['total_patterns']}")
    print(f"  Success rate: {stats['overall_success_rate']:.2%}")
    
    print("\n✅ Enhanced messaging test completed")