"""
Automation runner for Marketplace Bot
Executes the automation scripts with user configuration
"""

import asyncio
import sys
import os
import json
import subprocess
import signal
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime
import importlib.util
import importlib.machinery

# Add parent directory to path to import existing scripts
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

from gui.backend.models import AutomationResult, AutomationState

class AutomationRunner:
    """Runs automation scripts with user configuration"""
    
    def __init__(self):
        self.is_running = False
        self.should_stop = False
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.scripts_dir = self.project_root  # Main project directory contains the scripts
        self.running_processes = []  # Track running subprocesses
        
        # Initialize config manager for state tracking
        from gui.backend.config_manager import ConfigManager
        self.config_manager = ConfigManager()
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"[SIGNAL] Received signal {signum}, initiating shutdown...")
        self.stop()
        self._cleanup_processes()
        sys.exit(0)
    
    def _cleanup_processes(self):
        """Clean up all running subprocesses"""
        print(f"[CLEANUP] Terminating {len(self.running_processes)} subprocess(es)...")
        for process in self.running_processes[:]:  # Make a copy to avoid modification during iteration
            try:
                if process.returncode is None:  # Process is still running
                    print(f"[CLEANUP] Terminating process {process.pid}")
                    process.terminate()
                    # For async processes, we can't use wait() directly
            except Exception as e:
                print(f"[CLEANUP] Error terminating process: {e}")
        
        # Give processes a moment to terminate
        import time
        time.sleep(1)
        
        # Force kill any remaining processes
        for process in self.running_processes[:]:
            try:
                if process.returncode is None:
                    print(f"[CLEANUP] Force killing process {process.pid}")
                    process.kill()
            except Exception as e:
                print(f"[CLEANUP] Error killing process: {e}")
        
        self.running_processes.clear()
        print("[CLEANUP] All subprocesses terminated")
    
    def _kill_existing_automation_processes(self):
        """Kill any existing Python processes running automation scripts from previous sessions"""
        try:
            print("[STARTUP CLEANUP] Checking for existing automation processes...")
            
            # Get list of Python processes
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                print("[STARTUP CLEANUP] Could not list processes")
                return
            
            lines = result.stdout.split('\n')
            killed_processes = []
            
            for line in lines:
                # Look for Python processes running our automation scripts
                if ('python' in line.lower() and 
                    any(script in line for script in ['offer_agent.py', 'conversation_agent.py', 'get_listing_urls.py'])):
                    
                    parts = line.split()
                    if len(parts) > 1:
                        try:
                            pid = int(parts[1])
                            process_name = ' '.join(parts[10:])  # Command and args
                            
                            print(f"[STARTUP CLEANUP] Found existing automation process: PID {pid} - {process_name}")
                            
                            # Kill the process
                            os.kill(pid, signal.SIGTERM)
                            killed_processes.append(pid)
                            print(f"[STARTUP CLEANUP] Terminated process {pid}")
                            
                        except (ValueError, ProcessLookupError, PermissionError) as e:
                            print(f"[STARTUP CLEANUP] Could not kill process: {e}")
            
            # Wait a moment for processes to terminate
            if killed_processes:
                import time
                time.sleep(2)
                
                # Force kill any that didn't terminate
                for pid in killed_processes:
                    try:
                        os.kill(pid, signal.SIGKILL)
                        print(f"[STARTUP CLEANUP] Force killed process {pid}")
                    except ProcessLookupError:
                        # Process already dead, that's good
                        pass
                    except Exception as e:
                        print(f"[STARTUP CLEANUP] Could not force kill {pid}: {e}")
                
                print(f"[STARTUP CLEANUP] Cleaned up {len(killed_processes)} existing automation processes")
            else:
                print("[STARTUP CLEANUP] No existing automation processes found")
                
        except Exception as e:
            print(f"[STARTUP CLEANUP] Error during process cleanup: {e}")
            # Don't fail startup if cleanup fails
    
    def _get_product_names_from_config(self, config: Dict[str, Any]) -> List[str]:
        """Extract product names from configuration"""
        search_products = config.get("search_products", [])
        return [
            product.get("name") if isinstance(product, dict) else str(product)
            for product in search_products
        ]
    
    def _initialize_automation_state(self, config: Dict[str, Any], automation_type: str = "full_automation") -> AutomationState:
        """Initialize or load automation state for the current run"""
        try:
            current_products = self._get_product_names_from_config(config)
            existing_state = self.config_manager.load_automation_state()
            
            # Check if we need to reset state due to configuration changes
            print(f"[STATE DEBUG] Existing state check:")
            print(f"[STATE DEBUG] - Has existing products: {bool(existing_state.current_cycle_products)}")
            print(f"[STATE DEBUG] - Previous products: {existing_state.current_cycle_products}")
            print(f"[STATE DEBUG] - Current products: {current_products}")
            print(f"[STATE DEBUG] - Products match: {existing_state.current_cycle_products == current_products}")
            print(f"[STATE DEBUG] - Previous automation type: {existing_state.automation_type}")
            print(f"[STATE DEBUG] - Current automation type: {automation_type}")
            print(f"[STATE DEBUG] - Automation type match: {existing_state.automation_type == automation_type}")
            
            if (not existing_state.current_cycle_products or 
                existing_state.current_cycle_products != current_products or
                existing_state.automation_type != automation_type):
                
                print(f"[STATE] Configuration changed or first run, resetting automation state")
                print(f"[STATE] Previous products: {existing_state.current_cycle_products}")
                print(f"[STATE] Current products: {current_products}")
                
                new_state = self.config_manager.reset_automation_state(current_products, automation_type)
                return new_state
            
            print(f"[STATE] Loaded existing automation state - last completed: {existing_state.last_completed_product_index}")
            return existing_state
            
        except Exception as e:
            print(f"[STATE] Error initializing automation state: {e}")
            # Fallback to reset state
            return self.config_manager.reset_automation_state(self._get_product_names_from_config(config), automation_type)
    
    def _save_product_completion(self, state: AutomationState, completed_product_index: int):
        """Save progress after completing a product"""
        try:
            state.last_completed_product_index = completed_product_index
            state.last_run_timestamp = datetime.now()
            self.config_manager.save_automation_state(state)
            
            product_name = state.current_cycle_products[completed_product_index] if completed_product_index < len(state.current_cycle_products) else "Unknown"
            print(f"[STATE] Saved completion of product '{product_name}' (index {completed_product_index})")
            
        except Exception as e:
            print(f"[STATE] Error saving product completion: {e}")

    async def _send_result_update(self, progress_callback: Callable, result: Dict[str, Any]):
        """Send individual result update to trigger dashboard statistics updates"""
        try:
            # Import here to avoid circular imports
            import sys
            import os
            
            # Add the gui.backend path to import main module
            backend_path = os.path.join(os.path.dirname(__file__))
            if backend_path not in sys.path:
                sys.path.insert(0, backend_path)
            
            # Import and use active_connections from main
            import main
            
            disconnected_clients = []
            for client_id, websocket in main.active_connections.items():
                try:
                    await websocket.send_json({
                        "type": "result",
                        "result": result
                    })
                    print(f"[WEBSOCKET] Sent result update to {client_id}: offer_sent")
                except Exception as e:
                    print(f"Failed to send result update to {client_id}: {e}")
                    disconnected_clients.append(client_id)
            
            # Remove dead connections
            for client_id in disconnected_clients:
                if client_id in main.active_connections:
                    del main.active_connections[client_id]
                    
        except Exception as e:
            print(f"Error sending result update: {e}")
            # Fallback: just print the result
            print(f"[RESULT] Would have sent: {result}")
    
    async def _update_pricing_data(self, progress_callback: Callable):
        """Update pricing data from Google Sheets on startup"""
        try:
            await progress_callback("running", 1, "📊 Updating iPhone pricing data...")
            
            # Run get_pricing_data.py to update pricing
            pricing_script = os.path.join(self.project_root, "utils", "get_pricing_data.py")
            
            if os.path.exists(pricing_script):
                env = os.environ.copy()
                env["PYTHONUNBUFFERED"] = "1"
                
                process = await asyncio.create_subprocess_exec(
                    sys.executable, pricing_script,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=self.project_root
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    await progress_callback("running", 3, "✅ Pricing data updated successfully")
                    print("✅ Startup pricing update completed")
                else:
                    await progress_callback("running", 3, "⚠️ Pricing update had issues, continuing with existing data")
                    print(f"⚠️ Pricing update stderr: {stderr.decode()}")
            else:
                await progress_callback("running", 2, "⚠️ Pricing script not found, using existing data")
                
        except Exception as e:
            await progress_callback("running", 2, f"⚠️ Pricing update failed: {str(e)}, continuing with existing data")
            print(f"❌ Error updating pricing data: {e}")
    
    async def run(self, config: Dict[str, Any], progress_callback: Callable) -> List[Dict[str, Any]]:
        """
        Run automation with user configuration
        """
        if self.is_running:
            raise Exception("Automation is already running")
        
        self.is_running = True
        self.should_stop = False
        results = []
        
        # Update pricing data on startup
        await self._update_pricing_data(progress_callback)
        
        try:
            # Validate configuration
            if not config.get("gemini_api_key"):
                raise Exception("Gemini API key is required")
            
            search_products = config.get("search_products", [{"name": "iPhone 13 Pro Max"}])
            search_keywords = config.get("search_keywords", [])
            
            # Initialize automation state tracking
            automation_state = self._initialize_automation_state(config, "full_automation")
            
            # Debug: Log the products being processed
            print(f"[DEBUG] Processing {len(search_products)} products: {[p.get('name') if isinstance(p, dict) else p for p in search_products]}")
            
            # Determine starting point from state
            start_index = automation_state.get_next_product_index()
            total_products = len(search_products)
            
            if start_index > 0:
                await progress_callback("running", 5, f"Resuming automation from product {start_index + 1}/{total_products}: '{automation_state.current_cycle_products[start_index]}'")
            else:
                await progress_callback("running", 5, f"Starting automation for {total_products} search products...")
            
            # Process products starting from the resume point
            for product_index in range(start_index, total_products):
                product = search_products[product_index]
                # Handle both old format (string) and new format (dict)
                if isinstance(product, dict):
                    search_product = product["name"]
                    product_pricing = product
                else:
                    search_product = str(product)
                    product_pricing = {
                        "name": search_product,
                        "base_offer_unlocked": 300,
                        "base_offer_locked": 250, 
                        "base_offer_unlocked_damaged": 150,
                        "base_offer_locked_damaged": 100
                    }
                if self.should_stop:
                    print(f"[STATE] Automation stopped by user at product index {product_index}")
                    # Save progress for the last completed product (if any)
                    if product_index > 0:
                        self._save_product_completion(automation_state, product_index - 1)
                        print(f"[STATE] Saved progress up to product index {product_index - 1}")
                    return results
                
                base_progress = int((product_index / total_products) * 90)  # Reserve 10% for final completion
                
                await progress_callback("running", base_progress + 2, f"Processing '{search_product}' - Step 1: Finding listings...")
                
                # Step 1: Search for listings (get_listing_urls.py)
                await progress_callback("console", 0, f"DEBUG: About to run listing search for '{search_product}'")
                await self._run_listing_search(search_product, search_keywords, config, progress_callback, base_progress + 5)
                await progress_callback("console", 0, f"DEBUG: Listing search completed for '{search_product}'")
                
                if self.should_stop:
                    return results
                
                await progress_callback("running", base_progress + 15, f"Processing '{search_product}' - Step 2: Deduplicating listings...")
                
                # Step 2: Deduplicate listings (fix_duplicates.py)
                await progress_callback("console", 0, f"DEBUG: About to run deduplication for '{search_product}'")
                await self._fix_duplicates(search_product, config, progress_callback, base_progress + 15)
                await progress_callback("console", 0, f"DEBUG: Deduplication completed for '{search_product}'")
                
                if self.should_stop:
                    return results
                
                await progress_callback("running", base_progress + 30, f"Processing '{search_product}' - Step 3: Sending offers...")
                
                # Step 3: Send offers (offer_agent.py)
                offer_results = await self._send_offers(search_product, product_pricing, config, progress_callback, base_progress + 30)
                results.extend(offer_results)
                
                if self.should_stop:
                    print(f"[STATE] Automation stopped by user during offers step for product index {product_index}")
                    if product_index > 0:
                        self._save_product_completion(automation_state, product_index - 1)
                    return results
                
                await progress_callback("running", base_progress + 60, f"Processing '{search_product}' - Step 4: Getting conversation URLs...")
                
                # Step 4: Extract marketplace URLs (get_marketplace_urls.py) 
                await self._extract_marketplace_urls(search_product, config, progress_callback, base_progress + 60)
                
                if self.should_stop:
                    print(f"[STATE] Automation stopped by user during marketplace URLs step for product index {product_index}")
                    if product_index > 0:
                        self._save_product_completion(automation_state, product_index - 1)
                    return results
                
                # Step 5: Handle conversations (if enabled)
                if config.get("enable_negotiation", True):
                    await progress_callback("running", base_progress + 80, f"Processing '{search_product}' - Step 5: Managing conversations...")
                    conversation_results = await self._handle_conversations(search_product, config, progress_callback, base_progress + 80)
                    results.extend(conversation_results)
                
                await progress_callback("running", base_progress + 90, f"Completed processing '{search_product}'")
                
                # Save progress after completing this product
                self._save_product_completion(automation_state, product_index)
            
            # Check if we completed all products or just this batch
            if start_index + len(range(start_index, total_products)) >= total_products:
                # Completed full cycle, reset state for next cycle
                await progress_callback("running", 95, "Full automation cycle completed, resetting for next cycle...")
                automation_state = automation_state.reset_for_new_cycle(automation_state.current_cycle_products)
                self.config_manager.save_automation_state(automation_state)
                await progress_callback("running", 100, f"Automation cycle completed! Processed {total_products} products. Ready for next cycle.")
            else:
                await progress_callback("running", 100, f"Automation batch completed! Processed {len(range(start_index, total_products))} products.")
            
        except Exception as e:
            # Save current progress even if there was an error
            if 'automation_state' in locals() and 'product_index' in locals():
                print(f"[STATE] Saving progress due to error at product index {product_index}")
                self._save_product_completion(automation_state, product_index - 1)  # Save previous completed index
            await progress_callback("error", 0, f"Automation failed: {str(e)}")
            raise
        finally:
            self.is_running = False
            self.should_stop = False
            # Clean up any remaining processes
            self._cleanup_processes()
        
        return results
    
    async def run_offers_only(self, config: Dict[str, Any], progress_callback: Callable) -> List[Dict[str, Any]]:
        """
        Run only the offer agent for existing listings
        """
        if self.is_running:
            raise Exception("Automation is already running")
        
        self.is_running = True
        self.should_stop = False
        results = []
        
        try:
            # Kill any existing automation processes first
            self._kill_existing_automation_processes()
            
            # Validate configuration
            if not config.get("gemini_api_key"):
                raise Exception("Gemini API key is required")
            
            search_products = config.get("search_products", [{"name": "iPhone 13 Pro Max"}])
            
            # Initialize automation state tracking for offers only
            automation_state = self._initialize_automation_state(config, "offers_only")
            
            # Determine starting point from state
            start_index = automation_state.get_next_product_index()
            total_products = len(search_products)
            
            if start_index > 0:
                await progress_callback("running", 5, f"Resuming offer agent from product {start_index + 1}/{total_products}: '{automation_state.current_cycle_products[start_index]}'")
            else:
                await progress_callback("running", 5, "Starting offer agent for existing listings...")
            
            # Process products starting from the resume point
            for product_index in range(start_index, total_products):
                product = search_products[product_index]
                # Handle both old format (string) and new format (dict)
                if isinstance(product, dict):
                    search_product = product["name"]
                    product_pricing = product
                else:
                    search_product = str(product)
                    product_pricing = {
                        "name": search_product,
                        "base_offer_unlocked": 300,
                        "base_offer_locked": 250, 
                        "base_offer_unlocked_damaged": 150,
                        "base_offer_locked_damaged": 100
                    }
                    
                if self.should_stop:
                    return results
                
                base_progress = int((product_index / total_products) * 90)
                
                await progress_callback("running", base_progress + 10, f"Processing offers for '{search_product}'...")
                
                # Run only the offer agent
                offer_results = await self._send_offers(search_product, product_pricing, config, progress_callback, base_progress + 10)
                results.extend(offer_results)
                
                if self.should_stop:
                    return results
                
                # Save progress after completing this product's offers
                self._save_product_completion(automation_state, product_index)
            
            # Check if we completed all products
            if start_index + len(range(start_index, total_products)) >= total_products:
                # Completed full cycle, reset state for next cycle
                automation_state = automation_state.reset_for_new_cycle(automation_state.current_cycle_products)
                self.config_manager.save_automation_state(automation_state)
                await progress_callback("running", 95, f"Offer agent cycle completed! Processed {total_products} products. Ready for next cycle.")
            else:
                await progress_callback("running", 95, f"Offer agent batch completed! Processed {len(range(start_index, total_products))} products.")
            
        except Exception as e:
            await progress_callback("error", 0, f"Offer agent failed: {str(e)}")
            raise
        finally:
            self.is_running = False
            self.should_stop = False
            # Clean up any remaining processes
            self._cleanup_processes()
        
        return results
    
    async def run_conversations_only(self, config: Dict[str, Any], progress_callback: Callable) -> List[Dict[str, Any]]:
        """
        Run only the conversation agent for existing messages
        """
        if self.is_running:
            raise Exception("Automation is already running")
        
        self.is_running = True
        self.should_stop = False
        results = []
        
        try:
            # Kill any existing automation processes first
            self._kill_existing_automation_processes()
            
            # Validate configuration
            if not config.get("gemini_api_key"):
                raise Exception("Gemini API key is required")
            
            search_products = config.get("search_products", [{"name": "iPhone 13 Pro Max"}])
            
            # Initialize automation state tracking for conversations only
            automation_state = self._initialize_automation_state(config, "conversations_only")
            
            # Determine starting point from state
            start_index = automation_state.get_next_product_index()
            total_products = len(search_products)
            
            if start_index > 0:
                await progress_callback("running", 5, f"Resuming conversation agent from product {start_index + 1}/{total_products}: '{automation_state.current_cycle_products[start_index]}'")
            else:
                await progress_callback("running", 5, "Starting conversation agent for existing messages...")
            
            # Process products starting from the resume point
            for product_index in range(start_index, total_products):
                product = search_products[product_index]
                # Handle both old format (string) and new format (dict)
                if isinstance(product, dict):
                    search_product = product["name"]
                else:
                    search_product = str(product)
                    
                if self.should_stop:
                    return results
                
                base_progress = int((product_index / total_products) * 90)
                
                await progress_callback("running", base_progress + 10, f"Processing conversations for '{search_product}'...")
                
                # Step 1: Always get marketplace URLs to check for new conversations
                await progress_callback("running", base_progress + 5, f"Extracting marketplace conversation URLs...")
                marketplace_url_results = await self._get_marketplace_urls(search_product, config, progress_callback, base_progress + 5)
                
                # Step 2: Run deduplication/formatting script
                await progress_callback("running", base_progress + 10, f"Formatting and deduplicating conversation data...")
                await self._fix_duplicates(search_product, config, progress_callback, base_progress + 10)
                
                # Step 3: Then run the conversation agent
                if config.get("enable_negotiation", True):
                    conversation_results = await self._handle_conversations(search_product, config, progress_callback, base_progress + 20)
                    results.extend(conversation_results)
                else:
                    await progress_callback("running", base_progress + 25, f"Negotiation disabled, skipping conversations for '{search_product}'")
                
                if self.should_stop:
                    return results
                
                # Save progress after completing this product's conversations
                self._save_product_completion(automation_state, product_index)
            
            # Check if we completed all products
            if start_index + len(range(start_index, total_products)) >= total_products:
                # Completed full cycle, reset state for next cycle
                automation_state = automation_state.reset_for_new_cycle(automation_state.current_cycle_products)
                self.config_manager.save_automation_state(automation_state)
                await progress_callback("running", 95, f"Conversation agent cycle completed! Processed {total_products} products. Ready for next cycle.")
            else:
                await progress_callback("running", 95, f"Conversation agent batch completed! Processed {len(range(start_index, total_products))} products.")
            
        except Exception as e:
            await progress_callback("error", 0, f"Conversation agent failed: {str(e)}")
            raise
        finally:
            self.is_running = False
            self.should_stop = False
            # Clean up any remaining processes
            self._cleanup_processes()
        
        return results
    
    async def run_scrape_listings_only(self, config: Dict[str, Any], progress_callback: Callable) -> List[Dict[str, Any]]:
        """
        Run only the listing scraper with a custom search term
        """
        if self.is_running:
            raise Exception("Automation is already running")
        
        self.is_running = True
        self.should_stop = False
        results = []
        
        try:
            # Kill any existing automation processes first
            self._kill_existing_automation_processes()
            
            # Validate configuration
            if not config.get("gemini_api_key"):
                raise Exception("Gemini API key is required")
            
            search_term = config.get("search_term", "iPhone 13 Pro Max")
            search_keywords = config.get("search_keywords", [])
            
            await progress_callback("running", 5, f"Starting listing scraper for: {search_term}")
            
            if self.should_stop:
                return results
                
            await progress_callback("running", 15, f"Scraping listings for '{search_term}'...")
            
            # Run only the listing search script
            await self._run_listing_search(search_term, search_keywords, config, progress_callback, 15)
            
            if self.should_stop:
                return results
            
            await progress_callback("running", 70, f"Deduplicating listings for '{search_term}'...")
            
            # Also run fix_duplicates to clean up the results
            await self._fix_duplicates(search_term, config, progress_callback, 70)
            
            await progress_callback("running", 95, f"Listing scraper completed for '{search_term}'")
            
            # Return some basic stats as results
            results.append({
                "type": "listing_scrape",
                "search_term": search_term,
                "status": "completed",
                "message": f"Successfully scraped listings for {search_term}",
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            await progress_callback("error", 0, f"Listing scraper failed: {str(e)}")
            raise
        finally:
            self.is_running = False
            self.should_stop = False
            # Clean up any remaining processes
            self._cleanup_processes()
        
        return results
    
    def stop(self):
        """Stop the currently running automation - ALWAYS works"""
        print("[EMERGENCY STOP] Stop button clicked - initiating FORCE shutdown...")
        self.should_stop = True
        self.is_running = False  # Immediately set to False
        
        # AGGRESSIVE process cleanup
        self._force_cleanup_all_processes()
        
        print("[EMERGENCY STOP] Automation forcefully stopped")
    
    def _force_cleanup_all_processes(self):
        """Aggressively clean up ALL automation-related processes"""
        import psutil
        import signal
        
        # First, try graceful cleanup of tracked processes
        self._cleanup_processes()
        
        # Find and kill Python processes running automation scripts
        automation_scripts = [
            'get_listing_urls.py',
            'offer_agent.py', 
            'conversation_agent.py',
            'get_marketplace_urls.py',
            'get_pricing_data.py',
            'fix_duplicates.py'
        ]
        
        killed_count = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and len(cmdline) > 1:
                    # Check if it's a Python process running our scripts
                    if 'python' in proc.info['name'].lower():
                        for script in automation_scripts:
                            if any(script in arg for arg in cmdline):
                                print(f"[FORCE KILL] Terminating {script} process (PID: {proc.info['pid']})")
                                try:
                                    proc.terminate()  # Try graceful first
                                    proc.wait(timeout=2)  # Wait 2 seconds
                                except psutil.TimeoutExpired:
                                    proc.kill()  # Force kill if needed
                                except:
                                    pass
                                killed_count += 1
                                break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Also kill any Chrome processes that might be hanging around
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if 'chrome' in proc.info['name'].lower():
                        cmdline = proc.info.get('cmdline', [])
                        if any('browseruse' in str(arg) or 'agent' in str(arg) for arg in cmdline):
                            print(f"[FORCE KILL] Terminating Chrome browser process (PID: {proc.info['pid']})")
                            proc.terminate()
                            killed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except:
            pass
        
        self.running_processes.clear()
        print(f"[FORCE KILL] Terminated {killed_count} automation processes")
    
    async def _run_process_with_streaming(self, process, progress_callback: Callable):
        """Run process and stream output in real-time"""
        # Track the process
        self.running_processes.append(process)
        
        # Check if we should stop before waiting
        if self.should_stop:
            process.terminate()
            return [], []
        
        # Stream output in real-time while process runs
        stdout_lines = []
        stderr_lines = []
        
        async def read_stream(stream, lines_list, stream_name):
            print(f"[STREAM] Starting to read {stream_name}")
            while True:
                try:
                    line = await stream.readline()
                    if not line:
                        print(f"[STREAM] End of {stream_name}")
                        break
                    
                    decoded_line = line.decode().strip()
                    if decoded_line:
                        print(f"[STREAM] {stream_name}: {decoded_line}")
                        lines_list.append(decoded_line)
                        # Send console output via progress callback
                        await progress_callback("console", 0, decoded_line)
                except Exception as e:
                    print(f"[STREAM] Error reading {stream_name}: {e}")
                    break
        
        # Start reading both streams concurrently
        tasks = []
        if process.stdout:
            tasks.append(read_stream(process.stdout, stdout_lines, "stdout"))
        if process.stderr:
            tasks.append(read_stream(process.stderr, stderr_lines, "stderr"))
        
        # Wait for process to complete and streams to finish
        if tasks:
            await asyncio.gather(
                process.wait(),
                *tasks,
                return_exceptions=True
            )
        else:
            await process.wait()
        
        # Remove from tracking when done
        if process in self.running_processes:
            self.running_processes.remove(process)
        
        return stdout_lines, stderr_lines
    
    def _validate_product_pricing(self, search_products: List) -> bool:
        """Validate that all products have valid pricing configuration"""
        if not search_products:
            return False
        
        for product in search_products:
            # Handle both old format (strings) and new format (objects)
            if isinstance(product, dict):
                # New per-product pricing format
                required_fields = ["base_offer_unlocked", "base_offer_locked", 
                                 "base_offer_unlocked_damaged", "base_offer_locked_damaged"]
                for field in required_fields:
                    value = product.get(field, 0)
                    if not isinstance(value, (int, float)) or value <= 0:
                        return False
            elif isinstance(product, str):
                # Old format - assume default pricing is valid
                continue
            else:
                return False
        
        return True
    
    async def _run_listing_search(self, search_product: str, search_keywords: List[str], config: Dict[str, Any], progress_callback: Callable, current_progress: int = 0):
        """Run listing search using get_listing_urls.py"""
        try:
            # Prepare environment variables for the script
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"  # Force unbuffered output
            env["GEMINI_API_KEY"] = config["gemini_api_key"]
            env["SEARCH_PRODUCT"] = search_product
            env["SEARCH_KEYWORDS"] = ",".join(search_keywords) if search_keywords else ""
            
            # Run the listing search script
            script_path = os.path.join(self.project_root, "get_listing_urls.py")
            
            # Log debug info
            await progress_callback("console", 0, f"DEBUG: Script path: {script_path}")
            await progress_callback("console", 0, f"DEBUG: Script exists: {os.path.exists(script_path)}")
            await progress_callback("console", 0, f"DEBUG: Project root: {self.project_root}")
            await progress_callback("console", 0, f"DEBUG: Python executable: {sys.executable}")
            await progress_callback("console", 0, f"DEBUG: Environment vars set: SEARCH_PRODUCT={env.get('SEARCH_PRODUCT')}")
            
            await progress_callback("running", current_progress, f"Starting listing search for '{search_product}'...")
            
            # Execute the script
            process = await asyncio.create_subprocess_exec(
                sys.executable, script_path,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            # Track the process
            self.running_processes.append(process)
            print(f"[PROCESS] Started process {process.pid} for listing search")
            
            # Run process with streaming output
            stdout_lines, stderr_lines = await self._run_process_with_streaming(process, progress_callback)
            
            print(f"[DEBUG] Process completed with return code: {process.returncode}")
            
            # Remove from tracking once completed
            if process in self.running_processes:
                self.running_processes.remove(process)
            
            if process.returncode != 0:
                error_msg = "\n".join(stderr_lines) if stderr_lines else "Listing search failed"
                raise Exception(f"Listing search failed for '{search_product}': {error_msg}")
            
            await progress_callback("running", current_progress + 10, f"Listing search completed for '{search_product}'")
            
            # Give browser process time to fully terminate
            await asyncio.sleep(3)
            
        except Exception as e:
            raise Exception(f"Failed to run listing search for '{search_product}': {str(e)}")
    
    async def _fix_duplicates(self, search_product: str, config: Dict[str, Any], progress_callback: Callable, current_progress: int = 0):
        """Fix duplicates in listings.json using fix_duplicates.py"""
        try:
            # Run the fix_duplicates script
            script_path = os.path.join(self.project_root, "utils", "fix_duplicates.py")
            
            # Log debug info
            await progress_callback("console", 0, f"DEBUG: Fix duplicates script path: {script_path}")
            await progress_callback("console", 0, f"DEBUG: Fix duplicates script exists: {os.path.exists(script_path)}")
            
            await progress_callback("running", current_progress, f"Starting deduplication for '{search_product}'...")
            
            # Import and run the deduplication function directly
            sys.path.insert(0, os.path.join(self.project_root, "utils"))
            sys.path.insert(0, self.project_root)
            
            try:
                from fix_duplicates import fix_duplicates
                import json
                
                await progress_callback("console", 0, "Running deduplication function...")
                
                # Run deduplication in the project root directory
                original_cwd = os.getcwd()
                os.chdir(self.project_root)
                
                try:
                    # Call the function with auto_replace=True and no output file to update listings.json directly
                    deduplicated = fix_duplicates('listings.json', None, auto_replace=True)
                    
                    await progress_callback("console", 0, f"Deduplication completed successfully")
                    
                finally:
                    os.chdir(original_cwd)
                    
            except ImportError as e:
                await progress_callback("console", 0, f"Import error: {e}")
                raise Exception(f"Could not import fix_duplicates: {e}")
            except Exception as e:
                await progress_callback("console", 0, f"Deduplication error: {e}")
                raise Exception(f"Deduplication failed: {e}")
            
            await progress_callback("running", current_progress + 10, f"Deduplication completed for '{search_product}'")
            
        except Exception as e:
            raise Exception(f"Failed to run deduplication for '{search_product}': {str(e)}")
    
    async def _extract_marketplace_urls(self, search_product: str, config: Dict[str, Any], progress_callback: Callable, current_progress: int = 0):
        """Extract marketplace URLs using get_marketplace_urls.py"""
        try:
            # Prepare environment variables for the script
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"  # Force unbuffered output
            env["GEMINI_API_KEY"] = config["gemini_api_key"]
            env["SEARCH_PRODUCT"] = search_product
            
            # Run the marketplace URL extraction script
            script_path = os.path.join(self.project_root, "get_marketplace_urls.py")
            
            await progress_callback("running", current_progress, f"Starting marketplace URL extraction for '{search_product}'...")
            
            # Execute the script
            process = await asyncio.create_subprocess_exec(
                sys.executable, script_path,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            # Track the process
            self.running_processes.append(process)
            print(f"[PROCESS] Started process {process.pid} for marketplace URL extraction")
            
            # Run process with streaming output
            stdout_lines, stderr_lines = await self._run_process_with_streaming(process, progress_callback)
            
            print(f"[DEBUG] Process completed with return code: {process.returncode}")
            
            # Remove from tracking once completed
            if process in self.running_processes:
                self.running_processes.remove(process)
            
            if process.returncode != 0:
                error_msg = "\n".join(stderr_lines) if stderr_lines else "URL extraction failed"
                raise Exception(f"URL extraction failed for '{search_product}': {error_msg}")
            
            await progress_callback("running", current_progress + 10, f"URL extraction completed for '{search_product}'")
            
        except Exception as e:
            raise Exception(f"Failed to extract marketplace URLs for '{search_product}': {str(e)}")
    
    async def _send_offers(self, search_product: str, product_pricing: Dict[str, Any], config: Dict[str, Any], progress_callback: Callable, current_progress: int = 0) -> List[Dict[str, Any]]:
        """Send offers using the offer agent"""
        results = []
        
        try:
            # Prepare environment variables for the script
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"  # Force unbuffered output
            env["GEMINI_API_KEY"] = config["gemini_api_key"]
            env["SEARCH_PRODUCT"] = search_product
            env["BASE_OFFER_UNLOCKED"] = str(product_pricing.get("base_offer_unlocked", 300))
            env["BASE_OFFER_LOCKED"] = str(product_pricing.get("base_offer_locked", 250))
            env["BASE_OFFER_UNLOCKED_DAMAGED"] = str(product_pricing.get("base_offer_unlocked_damaged", 150))
            env["BASE_OFFER_LOCKED_DAMAGED"] = str(product_pricing.get("base_offer_locked_damaged", 100))
            env["PRICE_FLEXIBILITY"] = str(config.get("price_flexibility", 20))
            env["HEADLESS_OFFERS"] = str(config.get("headless_offers", True)).lower()
            
            # Pass all configured products for relevance checking
            import json
            all_products = config.get("search_products", [])
            env["ALL_PRODUCTS_CONFIG"] = json.dumps(all_products)
            
            # Run the offer agent script
            script_path = os.path.join(self.project_root, "offer_agent.py")
            
            await progress_callback("running", current_progress, f"Starting offer agent for '{search_product}'...")
            
            # Execute the script
            process = await asyncio.create_subprocess_exec(
                sys.executable, script_path,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            # Track the process
            self.running_processes.append(process)
            print(f"[PROCESS] Started process {process.pid} for offer agent")
            
            # Run process with streaming output
            stdout_lines, stderr_lines = await self._run_process_with_streaming(process, progress_callback)
            
            print(f"[DEBUG] Process completed with return code: {process.returncode}")
            
            # Remove from tracking once completed
            if process in self.running_processes:
                self.running_processes.remove(process)
            
            if process.returncode != 0:
                error_msg = "\n".join(stderr_lines) if stderr_lines else "Offer agent failed"
                raise Exception(f"Offer agent failed for '{search_product}': {error_msg}")
            
            await progress_callback("running", current_progress + 15, f"Offer agent completed for '{search_product}'")
            
            # Read the updated listings.json to get results
            listings_file = os.path.join(self.project_root, "listings.json")
            if os.path.exists(listings_file):
                with open(listings_file, 'r') as f:
                    listings = json.load(f)
                    
                # Count all messaged listings from this run and send WebSocket updates
                offers_sent_count = 0
                for listing in listings:
                    if isinstance(listing, dict):
                        # Check if this was messaged recently (within last hour) to count as new offer
                        messaged_recently = False
                        if listing.get("messaged", False) and listing.get("messaged_at"):
                            try:
                                from datetime import datetime, timedelta
                                messaged_time = datetime.fromisoformat(listing["messaged_at"])
                                if datetime.now() - messaged_time < timedelta(hours=1):
                                    messaged_recently = True
                            except:
                                pass
                        
                        # Include listings for current search product or any messaged listings
                        listing_product = listing.get("product", "")
                        is_current_product = search_product.lower() in listing_product.lower() or not listing_product
                        
                        if is_current_product or messaged_recently:
                            result = {
                                "url": listing.get("url", ""),
                                "status": "offer_sent" if listing.get("messaged", False) else "pending",
                                "message": listing.get("last_message", "Offer sent"),
                                "timestamp": datetime.now().isoformat(),
                                "offer_amount": product_pricing.get("base_offer_unlocked", 300),
                                "type": "offer",
                                "product": search_product
                            }
                            results.append(result)
                            
                            # Send WebSocket update for each recently messaged listing
                            if messaged_recently:
                                offers_sent_count += 1
                                await self._send_result_update(progress_callback, result)
                                print(f"[STATS] Sent WebSocket update for offer #{offers_sent_count}")
                
                print(f"[STATS] Total offers sent this run: {offers_sent_count}")
            
            return results
            
        except Exception as e:
            raise Exception(f"Failed to send offers for '{search_product}': {str(e)}")
    
    async def _get_marketplace_urls(self, search_product: str, config: Dict[str, Any], progress_callback: Callable, current_progress: int = 0) -> List[Dict[str, Any]]:
        """Extract marketplace conversation URLs using get_marketplace_urls.py"""
        results = []
        
        try:
            # Prepare environment variables for the script
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"  # Force unbuffered output
            env["GEMINI_API_KEY"] = config["gemini_api_key"]
            env["SEARCH_PRODUCT"] = search_product
            
            # Run the get_marketplace_urls script
            script_path = os.path.join(self.project_root, "get_marketplace_urls.py")
            
            await progress_callback("running", current_progress, f"🚀 Starting URL extraction - launching browser...")
            
            # Execute the script
            process = await asyncio.create_subprocess_exec(
                sys.executable, script_path,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            # Track the process
            self.running_processes.append(process)
            print(f"[PROCESS] Started process {process.pid} for marketplace URL extraction")
            
            # Wait for completion
            stdout, stderr = await process.communicate()
            
            # Remove from tracking
            if process in self.running_processes:
                self.running_processes.remove(process)
            
            if process.returncode == 0:
                await progress_callback("running", current_progress + 5, f"Successfully extracted marketplace URLs")
                print(f"[SUCCESS] Marketplace URL extraction completed for '{search_product}'")
            else:
                error_message = stderr.decode() if stderr else "Unknown error"
                await progress_callback("error", current_progress, f"Marketplace URL extraction failed: {error_message}")
                print(f"[ERROR] Marketplace URL extraction failed: {error_message}")
                raise Exception(f"Marketplace URL extraction failed: {error_message}")
            
            return results
            
        except Exception as e:
            raise Exception(f"Failed to extract marketplace URLs for '{search_product}': {str(e)}")
    
    async def _handle_conversations(self, search_product: str, config: Dict[str, Any], progress_callback: Callable, current_progress: int = 0) -> List[Dict[str, Any]]:
        """Handle ongoing conversations using the conversation agent"""
        results = []
        
        try:
            # Prepare environment variables for the script
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"  # Force unbuffered output
            env["GEMINI_API_KEY"] = config["gemini_api_key"]
            env["SEARCH_PRODUCT"] = search_product
            env["ENABLE_NEGOTIATION"] = str(config.get("enable_negotiation", True)).lower()
            env["PRICE_FLEXIBILITY"] = str(config.get("price_flexibility", 20))
            env["NOTIFICATION_EMAIL"] = config.get("notification_email", "")
            env["HEADLESS_CONVERSATIONS"] = str(config.get("headless_conversations", False)).lower()
            
            # Run the conversation agent script
            script_path = os.path.join(self.project_root, "conversation_agent.py")
            
            await progress_callback("running", current_progress, f"Starting conversation agent for '{search_product}'...")
            
            # Execute the script
            process = await asyncio.create_subprocess_exec(
                sys.executable, script_path,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            # Track the process
            self.running_processes.append(process)
            print(f"[PROCESS] Started process {process.pid} for conversation agent")
            
            # Run process with streaming output
            stdout_lines, stderr_lines = await self._run_process_with_streaming(process, progress_callback)
            
            print(f"[DEBUG] Process completed with return code: {process.returncode}")
            
            # Remove from tracking once completed
            if process in self.running_processes:
                self.running_processes.remove(process)
            
            if process.returncode != 0:
                error_msg = "\n".join(stderr_lines) if stderr_lines else "Conversation agent failed"
                raise Exception(f"Conversation agent failed for '{search_product}': {error_msg}")
            
            await progress_callback("running", current_progress + 15, f"Conversation agent completed for '{search_product}'")
            
            # Read the conversation results and send WebSocket updates
            messages_file = os.path.join(self.project_root, "messages.json")
            if os.path.exists(messages_file):
                with open(messages_file, 'r') as f:
                    messages_data = json.load(f)
                    
                # Send WebSocket updates for active negotiations
                conversations = messages_data.get("conversations", []) if isinstance(messages_data, dict) else []
                active_statuses = ["awaiting_response", "negotiating", "answering_questions", "deal_pending"]
                
                for conversation in conversations:
                    if isinstance(conversation, dict):
                        conv_status = conversation.get("status", "unknown")
                        
                        # Determine result status for frontend
                        if conv_status in active_statuses:
                            result_status = "negotiating"
                        elif conv_status == "deal_closed":
                            result_status = "accepted"
                        elif conv_status in ["needs_help", "error"]:
                            result_status = "error"
                        else:
                            result_status = "conversation_handled"
                        
                        result = {
                            "url": conversation.get("conversation_url", ""),
                            "status": result_status,
                            "message": conversation.get("last_message", "Conversation processed"),
                            "timestamp": conversation.get("last_updated", ""),
                            "type": "conversation",
                            "product": search_product
                        }
                        results.append(result)
                        
                        # Send WebSocket update for active negotiations
                        if conv_status in active_statuses:
                            await self._send_result_update(progress_callback, result)
                            print(f"[STATS] Sent WebSocket update for active negotiation: {conv_status}")
                        elif conv_status == "deal_closed":
                            await self._send_result_update(progress_callback, result)
                            print(f"[STATS] Sent WebSocket update for completed deal")
                
                print(f"[STATS] Processed {len(conversations)} conversations, sent WebSocket updates for active negotiations")
            
            return results
            
        except Exception as e:
            raise Exception(f"Failed to handle conversations for '{search_product}': {str(e)}")
    
    def get_script_status(self) -> Dict[str, Any]:
        """Get current status of running scripts"""
        return {
            "is_running": self.is_running,
            "should_stop": self.should_stop,
            "scripts_available": self._check_scripts_available()
        }
    
    def _check_scripts_available(self) -> Dict[str, bool]:
        """Check if required scripts are available"""
        script_files = [
            "get_listing_urls.py",
            "utils/fix_duplicates.py",
            "offer_agent.py", 
            "get_marketplace_urls.py",
            "conversation_agent.py"
        ]
        
        return {
            script: os.path.exists(os.path.join(self.project_root, script))
            for script in script_files
        }
    
    async def test_configuration(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test configuration without running full automation"""
        try:
            # Test Gemini API key
            if not config.get("gemini_api_key"):
                raise Exception("Gemini API key is required")
            
            # Test browser setup
            # This would test if Chrome is available, profile can be created, etc.
            
            # Test other configurations
            validation_results = {
                "gemini_api_key": bool(config.get("gemini_api_key")),
                "search_products": len(config.get("search_products", [])) > 0,
                "pricing_valid": self._validate_product_pricing(config.get("search_products", [])),
                "scripts_available": self._check_scripts_available()
            }
            
            all_valid = all(validation_results.values())
            
            return {
                "valid": all_valid,
                "details": validation_results,
                "message": "Configuration is valid" if all_valid else "Configuration has issues"
            }
            
        except Exception as e:
            return {
                "valid": False,
                "details": {},
                "message": f"Configuration test failed: {str(e)}"
            }