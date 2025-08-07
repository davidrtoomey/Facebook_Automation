#!/usr/bin/env python3

"""
Messaging Success Pattern Cache for Facebook Marketplace

This module caches successful messaging interaction patterns to improve
the reliability of finding and using message input elements on Facebook.

@file purpose: Cache successful DOM interaction patterns for messaging reliability
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import hashlib


@dataclass
class MessagePattern:
    """Represents a successful messaging interaction pattern"""
    pattern_id: str
    success_timestamp: str
    url_pattern: str  # Pattern to match URLs (e.g., "marketplace/item/*")
    steps: List[Dict[str, Any]]  # Sequence of successful actions
    dom_selectors: List[str]  # CSS selectors that worked
    success_indicators: List[str]  # Text/elements that indicate success
    failure_recovery: List[Dict[str, Any]]  # Steps to try if pattern fails
    success_count: int = 1
    failure_count: int = 0
    last_used: Optional[str] = None
    effectiveness_score: float = 1.0


class MessagingSuccessCache:
    """Manages caching and retrieval of successful messaging patterns"""
    
    def __init__(self, db_path: str = None):
        """
        Initialize the messaging success cache
        
        Args:
            db_path: Path to SQLite database file
        """
        if db_path is None:
            db_path = os.path.expanduser("~/.marketplace-bot/messaging_patterns.db")
        
        self.db_path = db_path
        self._ensure_directory()
        self._initialize_database()
    
    def _ensure_directory(self):
        """Ensure the database directory exists"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def _initialize_database(self):
        """Initialize the SQLite database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS message_patterns (
                    pattern_id TEXT PRIMARY KEY,
                    success_timestamp TEXT NOT NULL,
                    url_pattern TEXT NOT NULL,
                    steps TEXT NOT NULL,
                    dom_selectors TEXT NOT NULL,
                    success_indicators TEXT NOT NULL,
                    failure_recovery TEXT NOT NULL,
                    success_count INTEGER DEFAULT 1,
                    failure_count INTEGER DEFAULT 0,
                    last_used TEXT,
                    effectiveness_score REAL DEFAULT 1.0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS pattern_usage_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    execution_time_ms INTEGER,
                    error_message TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (pattern_id) REFERENCES message_patterns (pattern_id)
                )
            ''')
            
            conn.commit()
    
    def generate_pattern_id(self, url: str, steps: List[Dict]) -> str:
        """Generate a unique pattern ID based on URL and steps"""
        content = f"{url}_{json.dumps(steps, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def cache_successful_pattern(self, url: str, steps: List[Dict[str, Any]], 
                                dom_selectors: List[str], success_indicators: List[str],
                                failure_recovery: List[Dict[str, Any]] = None) -> str:
        """
        Cache a successful messaging pattern
        
        Args:
            url: The Facebook listing URL
            steps: Sequence of successful actions taken
            dom_selectors: CSS selectors that worked
            success_indicators: Elements/text that indicated success
            failure_recovery: Alternative steps if this pattern fails
            
        Returns:
            Generated pattern ID
        """
        if failure_recovery is None:
            failure_recovery = []
        
        pattern_id = self.generate_pattern_id(url, steps)
        url_pattern = self._extract_url_pattern(url)
        
        pattern = MessagePattern(
            pattern_id=pattern_id,
            success_timestamp=datetime.now().isoformat(),
            url_pattern=url_pattern,
            steps=steps,
            dom_selectors=dom_selectors,
            success_indicators=success_indicators,
            failure_recovery=failure_recovery
        )
        
        with sqlite3.connect(self.db_path) as conn:
            # Check if pattern already exists
            existing = conn.execute(
                'SELECT success_count FROM message_patterns WHERE pattern_id = ?',
                (pattern_id,)
            ).fetchone()
            
            if existing:
                # Update existing pattern
                new_count = existing[0] + 1
                effectiveness = min(2.0, 1.0 + (new_count * 0.1))  # Cap at 2.0
                
                conn.execute('''
                    UPDATE message_patterns 
                    SET success_count = ?, effectiveness_score = ?, 
                        last_used = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE pattern_id = ?
                ''', (new_count, effectiveness, datetime.now().isoformat(), pattern_id))
                
                print(f"🔄 Updated existing pattern {pattern_id[:8]}... (count: {new_count})")
            else:
                # Insert new pattern
                conn.execute('''
                    INSERT INTO message_patterns 
                    (pattern_id, success_timestamp, url_pattern, steps, dom_selectors, 
                     success_indicators, failure_recovery, success_count, failure_count, 
                     last_used, effectiveness_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    pattern.pattern_id, pattern.success_timestamp, pattern.url_pattern,
                    json.dumps(pattern.steps), json.dumps(pattern.dom_selectors),
                    json.dumps(pattern.success_indicators), json.dumps(pattern.failure_recovery),
                    pattern.success_count, pattern.failure_count, pattern.last_used,
                    pattern.effectiveness_score
                ))
                
                print(f"✅ Cached new successful pattern {pattern_id[:8]}...")
            
            conn.commit()
        
        return pattern_id
    
    def get_best_patterns_for_url(self, url: str, limit: int = 3) -> List[MessagePattern]:
        """
        Get the best messaging patterns for a given URL
        
        Args:
            url: The Facebook listing URL
            limit: Maximum number of patterns to return
            
        Returns:
            List of MessagePattern objects, ordered by effectiveness
        """
        url_pattern = self._extract_url_pattern(url)
        
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute('''
                SELECT * FROM message_patterns 
                WHERE url_pattern = ? 
                ORDER BY effectiveness_score DESC, success_count DESC, 
                         failure_count ASC, updated_at DESC
                LIMIT ?
            ''', (url_pattern, limit)).fetchall()
        
        patterns = []
        for row in rows:
            pattern = MessagePattern(
                pattern_id=row[0],
                success_timestamp=row[1],
                url_pattern=row[2],
                steps=json.loads(row[3]),
                dom_selectors=json.loads(row[4]),
                success_indicators=json.loads(row[5]),
                failure_recovery=json.loads(row[6]),
                success_count=row[7],
                failure_count=row[8],
                last_used=row[9],
                effectiveness_score=row[10]
            )
            patterns.append(pattern)
        
        return patterns
    
    def record_pattern_usage(self, pattern_id: str, url: str, success: bool, 
                           execution_time_ms: int = None, error_message: str = None):
        """
        Record the usage of a pattern and its outcome
        
        Args:
            pattern_id: ID of the pattern used
            url: URL where pattern was used
            success: Whether the pattern worked
            execution_time_ms: Time taken to execute
            error_message: Error message if failed
        """
        with sqlite3.connect(self.db_path) as conn:
            # Log the usage
            conn.execute('''
                INSERT INTO pattern_usage_log 
                (pattern_id, url, success, execution_time_ms, error_message)
                VALUES (?, ?, ?, ?, ?)
            ''', (pattern_id, url, success, execution_time_ms, error_message))
            
            # Update pattern statistics
            if success:
                conn.execute('''
                    UPDATE message_patterns 
                    SET success_count = success_count + 1,
                        last_used = ?,
                        effectiveness_score = MIN(2.0, effectiveness_score + 0.1),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE pattern_id = ?
                ''', (datetime.now().isoformat(), pattern_id))
                print(f"📈 Pattern {pattern_id[:8]}... success recorded")
            else:
                conn.execute('''
                    UPDATE message_patterns 
                    SET failure_count = failure_count + 1,
                        effectiveness_score = MAX(0.1, effectiveness_score - 0.2),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE pattern_id = ?
                ''', (pattern_id,))
                print(f"📉 Pattern {pattern_id[:8]}... failure recorded")
            
            conn.commit()
    
    def _extract_url_pattern(self, url: str) -> str:
        """
        Extract a URL pattern for matching similar URLs
        
        Args:
            url: Full Facebook listing URL
            
        Returns:
            URL pattern for matching
        """
        # Extract the base pattern from Facebook Marketplace URLs
        if 'facebook.com/marketplace/item/' in url:
            return 'facebook.com/marketplace/item/*'
        elif 'facebook.com/marketplace/' in url:
            return 'facebook.com/marketplace/*'
        else:
            # Fallback to domain pattern
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return f"{parsed.netloc}/*"
    
    def get_pattern_statistics(self) -> Dict[str, Any]:
        """Get statistics about cached patterns"""
        with sqlite3.connect(self.db_path) as conn:
            stats = {}
            
            # Total patterns
            stats['total_patterns'] = conn.execute(
                'SELECT COUNT(*) FROM message_patterns'
            ).fetchone()[0]
            
            # Success rate
            success_data = conn.execute('''
                SELECT 
                    SUM(success_count) as total_successes,
                    SUM(failure_count) as total_failures
                FROM message_patterns
            ''').fetchone()
            
            total_attempts = (success_data[0] or 0) + (success_data[1] or 0)
            if total_attempts > 0:
                stats['overall_success_rate'] = (success_data[0] or 0) / total_attempts
            else:
                stats['overall_success_rate'] = 0
            
            # Most effective patterns
            stats['most_effective'] = conn.execute('''
                SELECT pattern_id, effectiveness_score, success_count, failure_count
                FROM message_patterns 
                ORDER BY effectiveness_score DESC, success_count DESC
                LIMIT 5
            ''').fetchall()
            
            # Recent activity
            stats['recent_usage'] = conn.execute('''
                SELECT COUNT(*) FROM pattern_usage_log 
                WHERE timestamp > datetime('now', '-24 hours')
            ''').fetchone()[0]
            
            return stats
    
    def cleanup_old_patterns(self, days_old: int = 30, min_effectiveness: float = 0.3):
        """
        Clean up old or ineffective patterns
        
        Args:
            days_old: Remove patterns older than this many days
            min_effectiveness: Remove patterns below this effectiveness score
        """
        cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            # Remove old ineffective patterns
            removed = conn.execute('''
                DELETE FROM message_patterns 
                WHERE (updated_at < ? OR effectiveness_score < ?) 
                AND success_count < 2
            ''', (cutoff_date, min_effectiveness)).rowcount
            
            # Clean up orphaned usage logs
            conn.execute('''
                DELETE FROM pattern_usage_log 
                WHERE pattern_id NOT IN (SELECT pattern_id FROM message_patterns)
            ''')
            
            conn.commit()
        
        if removed > 0:
            print(f"🧹 Cleaned up {removed} old/ineffective patterns")
    
    def export_patterns_for_debugging(self, output_file: str = None) -> str:
        """
        Export patterns to JSON for debugging
        
        Args:
            output_file: Output file path (optional)
            
        Returns:
            JSON string of all patterns
        """
        if output_file is None:
            output_file = os.path.expanduser("~/.marketplace-bot/pattern_export.json")
        
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute('''
                SELECT * FROM message_patterns 
                ORDER BY effectiveness_score DESC
            ''').fetchall()
        
        patterns = []
        for row in rows:
            pattern_dict = {
                'pattern_id': row[0],
                'success_timestamp': row[1],
                'url_pattern': row[2],
                'steps': json.loads(row[3]),
                'dom_selectors': json.loads(row[4]),
                'success_indicators': json.loads(row[5]),
                'failure_recovery': json.loads(row[6]),
                'success_count': row[7],
                'failure_count': row[8],
                'last_used': row[9],
                'effectiveness_score': row[10]
            }
            patterns.append(pattern_dict)
        
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'total_patterns': len(patterns),
            'patterns': patterns
        }
        
        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"📤 Exported {len(patterns)} patterns to {output_file}")
        return json.dumps(export_data, indent=2)


# Helper functions for integration with offer_agent.py

def create_success_pattern_from_agent_result(url: str, agent_result: str, 
                                           message_sent: bool) -> Dict[str, Any]:
    """
    Create a success pattern from agent execution results
    
    Args:
        url: The listing URL
        agent_result: The agent's execution result string
        message_sent: Whether the message was successfully sent
        
    Returns:
        Pattern data dict or None if no useful pattern found
    """
    if not message_sent:
        return None
    
    # Extract DOM selectors and actions from agent result
    steps = []
    dom_selectors = []
    success_indicators = []
    
    # Parse common successful actions from agent results
    result_lower = agent_result.lower()
    
    # Look for button clicks
    if 'clicked' in result_lower and 'message' in result_lower:
        steps.append({
            'action': 'click_message_button',
            'description': 'Click message or contact seller button'
        })
    
    # Look for text input
    if 'typed' in result_lower or 'entered' in result_lower:
        steps.append({
            'action': 'input_message',
            'description': 'Enter message text in input field'
        })
    
    # Look for send button
    if 'send' in result_lower and 'clicked' in result_lower:
        steps.append({
            'action': 'click_send',
            'description': 'Click send button'
        })
    
    # Extract selectors (this would need to be enhanced based on actual agent output)
    # For now, use common Facebook selectors
    dom_selectors = [
        '[aria-label*="Message"]',
        '[data-testid*="message"]', 
        'textarea[placeholder*="message"]',
        'button[type="submit"]',
        '[aria-label*="Send"]'
    ]
    
    # Success indicators
    success_indicators = [
        'message sent',
        'successfully sent',
        'message delivered',
        'facebook.com/messages/t/'
    ]
    
    if steps:
        return {
            'steps': steps,
            'dom_selectors': dom_selectors,
            'success_indicators': success_indicators,
            'failure_recovery': [
                {'action': 'refresh_page', 'description': 'Refresh and retry'},
                {'action': 'wait_and_retry', 'description': 'Wait 5s and retry'}
            ]
        }
    
    return None


if __name__ == "__main__":
    """Test the messaging success cache"""
    cache = MessagingSuccessCache()
    
    print("=" * 60)
    print("🧪 MESSAGING SUCCESS CACHE - TEST MODE")
    print("=" * 60)
    
    # Test caching a pattern
    test_url = "https://www.facebook.com/marketplace/item/123456789"
    test_steps = [
        {'action': 'click_message_button', 'selector': '[aria-label="Message"]'},
        {'action': 'input_message', 'text': 'Hi I can do $300 cash for it'},
        {'action': 'click_send', 'selector': 'button[type="submit"]'}
    ]
    test_selectors = ['[aria-label="Message"]', 'textarea', 'button[type="submit"]']
    test_indicators = ['message sent', 'successfully sent']
    
    pattern_id = cache.cache_successful_pattern(
        test_url, test_steps, test_selectors, test_indicators
    )
    
    print(f"✅ Cached test pattern: {pattern_id}")
    
    # Test retrieval
    patterns = cache.get_best_patterns_for_url(test_url)
    print(f"📋 Retrieved {len(patterns)} patterns for URL")
    
    for pattern in patterns:
        print(f"  Pattern {pattern.pattern_id[:8]}... (score: {pattern.effectiveness_score})")
    
    # Test statistics
    stats = cache.get_pattern_statistics()
    print(f"\n📊 Cache Statistics:")
    print(f"  Total patterns: {stats['total_patterns']}")
    print(f"  Success rate: {stats['overall_success_rate']:.2%}")
    
    print("\n✅ Test completed successfully")