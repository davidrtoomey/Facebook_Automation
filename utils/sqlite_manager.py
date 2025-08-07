"""
SQLite state manager for efficient Facebook Marketplace automation
Provides faster, more reliable persistence than JSON files
"""
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import os
import logging
import shutil
from functools import lru_cache

# Setup structured logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SQLiteStateManager:
    """Manages marketplace automation state using SQLite for performance"""
    
    def __init__(self, db_path: str = "marketplace_automation.db"):
        dir_path = os.path.dirname(db_path) or '.'
        if not os.path.exists(dir_path):
            raise ValueError(f"Invalid database directory: {dir_path}")
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=5.0)
        self.conn.row_factory = sqlite3.Row
        self.init_database()
        self._cache_hits = 0
    
    def __del__(self):
        self.conn.close()
    
    def init_database(self):
        """Initialize SQLite database with required tables and optimal settings"""
        cursor = self.conn.cursor()
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA synchronous=NORMAL')
        cursor.execute('PRAGMA cache_size=10000')  # 10MB cache
        cursor.execute('PRAGMA temp_store=MEMORY')
        cursor.execute('PRAGMA foreign_keys=ON')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS listings (
                listing_id INTEGER PRIMARY KEY,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                seller_name TEXT,
                price TEXT,
                product TEXT,
                matched_product TEXT,
                messaged BOOLEAN DEFAULT FALSE,
                messaged_at TIMESTAMP,
                message_id TEXT,
                message_url TEXT,
                conversation_status TEXT,
                deal_status TEXT,
                offer_price INTEGER,
                negotiation_count INTEGER DEFAULT 0,
                condition_hints TEXT, -- JSON array
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_messaged ON listings(messaged)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_product ON listings(product)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversation ON listings(conversation_status)')
        
        # Product relevance cache table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_title TEXT UNIQUE NOT NULL,
                matched_product TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Session statistics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS session_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_date DATE,
                listings_processed INTEGER DEFAULT 0,
                messages_sent INTEGER DEFAULT 0,
                dom_optimizations INTEGER DEFAULT 0,
                cache_hits INTEGER DEFAULT 0,
                processing_time_seconds REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Schema version table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('INSERT OR REPLACE INTO schema_version (version) VALUES (1)')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pricing_cache (
                cache_key TEXT PRIMARY KEY,
                offer_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
        cursor.execute('ANALYZE')
        cursor.execute('PRAGMA integrity_check')
        logger.info("Database initialized with optimal PRAGMA settings")
    
    def migrate_from_json(self, json_path: str) -> int:
        """Migrate existing listings.json data to SQLite"""
        if not os.path.exists(json_path):
            return 0
        
        # Backup JSON
        backup_path = json_path + '.bak'
        shutil.copy(json_path, backup_path)
        logger.info(f"Backed up JSON to {backup_path}")
        
        with open(json_path, 'r') as f:
            listings = json.load(f)
        
        migrated_count = 0
        
        self.conn.execute('BEGIN')
        try:
            for listing in listings:
                # Handle condition_hints as JSON
                condition_hints = listing.get('condition_hints', [])
                if isinstance(condition_hints, list):
                    condition_hints_json = json.dumps(condition_hints)
                else:
                    condition_hints_json = json.dumps([])
                
                self.conn.execute('''
                    INSERT OR REPLACE INTO listings (
                        listing_id, url, title, seller_name, price, product,
                        matched_product, messaged, messaged_at, message_id,
                        message_url, conversation_status, deal_status,
                        offer_price, negotiation_count, condition_hints
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    listing.get('listing_id'),
                    listing.get('url'),
                    listing.get('title'),
                    listing.get('seller_name'),
                    listing.get('price'),
                    listing.get('product'),
                    listing.get('matched_product'),
                    listing.get('messaged', False),
                    listing.get('messaged_at'),
                    listing.get('message_id'),
                    listing.get('message_url'),
                    listing.get('conversation_status'),
                    listing.get('deal_status'),
                    listing.get('offer_price'),
                    listing.get('negotiation_count', 0),
                    condition_hints_json
                ))
                migrated_count += 1
            
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error migrating listing: {e}")
            raise
        
        logger.info(f"✅ Migrated {migrated_count} listings from JSON to SQLite")
        return migrated_count
    
    def get_unmessaged_listings(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all unmessaged listings efficiently"""
        query = '''
            SELECT listing_id, url, title, seller_name, price, product,
                   matched_product, condition_hints
            FROM listings
            WHERE messaged = FALSE
            ORDER BY created_at DESC
        '''
        
        if limit:
            query += f' LIMIT {limit}'
        
        cursor = self.conn.cursor()
        cursor.execute(query)
        
        listings = []
        for row in cursor.fetchall():
            listing = dict(row)
            # Parse condition_hints JSON
            try:
                listing['condition_hints'] = json.loads(listing['condition_hints'] or '[]')
            except:
                listing['condition_hints'] = []
            listings.append(listing)
        
        return listings
    
    def update_listing(self, listing_id: int, updates: Dict[str, Any]) -> bool:
        """Update a specific listing efficiently"""
        if not updates:
            return False
        
        # Handle condition_hints serialization
        if 'condition_hints' in updates:
            updates['condition_hints'] = json.dumps(updates['condition_hints'])
        
        # Add updated timestamp
        updates['updated_at'] = datetime.now().isoformat()
        
        # Build dynamic UPDATE query
        set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values()) + [listing_id]
        
        query = f"UPDATE listings SET {set_clause} WHERE listing_id = ?"
        
        self.conn.execute('BEGIN IMMEDIATE')
        try:
            cursor = self.conn.execute(query, values)
            success = cursor.rowcount > 0
            self.conn.commit()
            
            if success:
                logger.info(f"✅ Updated listing {listing_id}: {list(updates.keys())}")
            else:
                logger.warning(f"⚠️ Listing {listing_id} not found for update")
            
            return success
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error updating listing {listing_id}: {e}")
            raise
    
    def batch_update_listings(self, updates_list: List[Dict[str, Any]]) -> int:
        """Batch update multiple listings in a single transaction"""
        if not updates_list:
            return 0
        
        updated_count = 0
        
        self.conn.execute('BEGIN')
        try:
            for update_data in updates_list:
                listing_id = update_data.pop('listing_id')
                updates = update_data
                
                # Handle condition_hints serialization
                if 'condition_hints' in updates:
                    updates['condition_hints'] = json.dumps(updates['condition_hints'])
                
                # Add updated timestamp
                updates['updated_at'] = datetime.now().isoformat()
                
                # Build dynamic UPDATE query
                set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
                values = list(updates.values()) + [listing_id]
                
                query = f"UPDATE listings SET {set_clause} WHERE listing_id = ?"
                cursor = self.conn.execute(query, values)
                
                if cursor.rowcount > 0:
                    updated_count += 1
            
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error in batch update: {e}")
            raise
        
        logger.info(f"💾 Batch updated {updated_count} listings")
        return updated_count
    
    def add_listing(self, url: str, **kwargs) -> int:
        """Add a new listing and return its ID"""
        # Handle condition_hints serialization
        if 'condition_hints' in kwargs:
            kwargs['condition_hints'] = json.dumps(kwargs['condition_hints'])
        
        # Build dynamic INSERT query
        columns = ['url'] + list(kwargs.keys())
        placeholders = ', '.join(['?' for _ in columns])
        values = [url] + list(kwargs.values())
        
        query = f"INSERT INTO listings ({', '.join(columns)}) VALUES ({placeholders})"
        
        self.conn.execute('BEGIN IMMEDIATE')
        try:
            cursor = self.conn.execute(query, values)
            listing_id = cursor.lastrowid
            self.conn.commit()
            
            logger.info(f"✅ Added new listing {listing_id}: {url}")
            return listing_id
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error adding listing: {e}")
            raise
    
    def cache_product_relevance(self, listing_title: str, matched_product: str):
        """Cache a product relevance decision"""
        key = re.sub(r'\W+', '', listing_title.lower())  # Normalized key
        self.conn.execute('BEGIN EXCLUSIVE')
        try:
            self.conn.execute('''
                INSERT OR REPLACE INTO product_cache (listing_title, matched_product)
                VALUES (?, ?)
            ''', (key, matched_product))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error caching relevance: {e}")
            raise
    
    @lru_cache(maxsize=1000)  # In-memory layer for hot keys
    def get_cached_product_relevance(self, listing_title: str) -> Optional[str]:
        """Get cached product relevance decision"""
        key = re.sub(r'\W+', '', listing_title.lower())  # Normalized key
        self.conn.execute('BEGIN DEFERRED')
        try:
            cursor = self.conn.execute('''
                SELECT matched_product FROM product_cache
                WHERE listing_title = ? AND created_at > DATETIME('now', '-30 days')
            ''', (key,))
            
            result = cursor.fetchone()
            if result:
                self._cache_hits += 1
                logger.debug(f"Cache hit for {key}")
                return result[0]
            return None
        finally:
            self.conn.rollback()  # Read-only, rollback fine

    def get_cached_offer_price(self, cache_key):
        """Retrieve cached offer price data."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT offer_data FROM pricing_cache WHERE cache_key = ? AND created_at > DATETIME('now', '-30 days')", (cache_key,))
        result = cursor.fetchone()
        if result:
            return json.loads(result[0])
        return None

    def cache_offer_price(self, cache_key, result):
        """Cache offer price data with TTL support."""
        self.conn.execute("INSERT OR REPLACE INTO pricing_cache (cache_key, offer_data) VALUES (?, ?)", (cache_key, json.dumps(result)))
        self.conn.commit()
    
    def log_session_stats(self, processed: int, messages: int, dom_opts: int,
                         cache_hits: int, processing_time: float):
        """Log session statistics for analysis"""
        self.conn.execute('BEGIN IMMEDIATE')
        try:
            self.conn.execute('''
                INSERT INTO session_stats (
                    session_date, listings_processed, messages_sent,
                    dom_optimizations, cache_hits, processing_time_seconds
                ) VALUES (DATE('now'), ?, ?, ?, ?, ?)
            ''', (processed, messages, dom_opts, cache_hits, processing_time))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error logging stats: {e}")
            raise
    
    def get_session_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get session statistics for the last N days"""
        cursor = self.conn.cursor()
        cursor.execute('BEGIN DEFERRED')
        try:
            cursor.execute('''
                SELECT * FROM session_stats
                WHERE session_date >= DATE('now', '-{} days')
                ORDER BY created_at DESC
            '''.format(days))
            
            return [dict(row) for row in cursor.fetchall()]
        finally:
            self.conn.rollback()
    
    def get_listing_stats(self) -> Dict[str, int]:
        """Get overall listing statistics"""
        stats = {}
        cursor = self.conn.cursor()
        cursor.execute('BEGIN DEFERRED')
        try:
            # Total listings
            cursor.execute('SELECT COUNT(*) FROM listings')
            stats['total_listings'] = cursor.fetchone()[0]
            
            # Total messaged
            cursor.execute('SELECT COUNT(*) FROM listings WHERE messaged = TRUE')
            stats['messaged_listings'] = cursor.fetchone()[0]
            
            # Unmessaged listings
            stats['unmessaged_listings'] = stats['total_listings'] - stats['messaged_listings']
            
            # Active conversations
            cursor.execute('''
                SELECT COUNT(*) FROM listings
                WHERE conversation_status IN ('awaiting_response', 'negotiating')
            ''')
            stats['active_conversations'] = cursor.fetchone()[0]
            
            # Cache entries
            cursor.execute('SELECT COUNT(*) FROM product_cache')
            stats['cache_entries'] = cursor.fetchone()[0]
            
            return stats
        finally:
            self.conn.rollback()
    
    def cleanup_old_cache(self, days: int = 30):
        """Clean up old cache entries"""
        self.conn.execute('BEGIN IMMEDIATE')
        try:
            cursor = self.conn.execute('''
                DELETE FROM product_cache
                WHERE created_at < DATE('now', '-{} days')
            '''.format(days))
            
            deleted = cursor.rowcount
            self.conn.commit()
            
            # Limit to 10000 entries, delete oldest if over
            cursor.execute('SELECT COUNT(*) FROM product_cache')
            if cursor.fetchone()[0] > 10000:
                cursor.execute('DELETE FROM product_cache ORDER BY created_at ASC LIMIT ?',
                               (deleted - 10000,))
                self.conn.commit()
            
            logger.info(f"🧹 Cleaned up {deleted} old cache entries")
            return deleted
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error cleaning cache: {e}")
            raise
    
    def check_integrity(self) -> str:
        """Verify database integrity"""
        cursor = self.conn.cursor()
        cursor.execute('PRAGMA integrity_check')
        return cursor.fetchone()[0]
    
    def invalidate_cache_for_title(self, title: str):
        """Invalidate cache for a specific title"""
        key = re.sub(r'\W+', '', title.lower())
        self.conn.execute('DELETE FROM product_cache WHERE listing_title = ?', (key,))
        self.conn.commit()
        logger.info(f"Invalidated cache for title: {title}")
    
    def log_cache_hit(self):
        self._cache_hits += 1
        # Could log to stats periodically

    def is_migrated(self):
        """Check if migration has been completed by looking for a flag table."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='migration_flag'")
        return cursor.fetchone() is not None

    def set_migrated(self):
        """Set the migration flag by creating a simple table."""
        cursor = self.conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS migration_flag (flag INTEGER)")
        cursor.execute("INSERT OR REPLACE INTO migration_flag (flag) VALUES (1)")
        self.conn.commit()
