"""
Configuration management for Marketplace Bot
Handles saving/loading user settings and license information
"""

import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from gui.backend.models import AutomationConfig, ProductPricing, AutomationState

class ConfigManager:
    """Manages user configuration and license information"""
    
    def __init__(self):
        self.config_dir = os.path.expanduser("~/.marketplace-bot")
        self.config_file = os.path.join(self.config_dir, "config.json")
        self.license_file = os.path.join(self.config_dir, "license.json")
        self.state_file = os.path.join(self.config_dir, "automation_state.json")
        
        # Create config directory if it doesn't exist
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Set directory permissions
        os.chmod(self.config_dir, 0o700)
    
    def save_config(self, config: Dict[str, Any]):
        """Save user configuration while preserving pricing data"""
        try:
            print(f"DEBUG: Attempting to save config with keys: {list(config.keys())}")
            print(f"DEBUG: gemini_api_key value: '{config.get('gemini_api_key', 'NOT_PROVIDED')}'")
            print(f"DEBUG: gemini_api_key type: {type(config.get('gemini_api_key'))}")
            
            # Validate configuration
            automation_config = AutomationConfig(**config)
            print(f"DEBUG: Pydantic validation successful")
            print(f"DEBUG: Validated gemini_api_key: '{automation_config.gemini_api_key}'")
            
            # Load existing config to preserve pricing data
            existing_config = {}
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    existing_config = json.load(f)
            
            # Merge new config with existing, preserving pricing manager data
            merged_config = existing_config.copy()
            merged_config.update(automation_config.dict())
            
            # Preserve pricing manager fields if they exist
            pricing_fields = ['base_prices', 'offer_prices', 'margin_percent', 'last_updated', 'pricing_count']
            for field in pricing_fields:
                if field in existing_config:
                    merged_config[field] = existing_config[field]
                    print(f"DEBUG: Preserved pricing field '{field}'")
            
            # Save merged config to file
            with open(self.config_file, 'w') as f:
                json.dump(merged_config, f, indent=2)
            
            print(f"DEBUG: Configuration saved to {self.config_file} (pricing data preserved)")
            
            # Set file permissions
            os.chmod(self.config_file, 0o600)
            
        except Exception as e:
            print(f"DEBUG: Config save failed with error: {e}")
            print(f"DEBUG: Error type: {type(e)}")
            raise Exception(f"Failed to save configuration: {e}")
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                
                # Migrate old format to new format if needed
                config_data = self._migrate_config_format(config_data)
                    
                # Validate and return
                automation_config = AutomationConfig(**config_data)
                return automation_config.dict()
            else:
                # Return default configuration
                default_config = AutomationConfig(
                    gemini_api_key="",  # User must provide
                    search_products=[ProductPricing(name="iPhone 13 Pro Max")],
                    max_conversations=10
                )
                return default_config.dict()
                
        except Exception as e:
            print(f"Error loading configuration: {e}")
            # Return default config on error
            return AutomationConfig(gemini_api_key="").dict()
    
    def _migrate_config_format(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate old configuration format to new format"""
        try:
            # Check if we need to migrate from old format (string products + separate pricing)
            if "search_products" in config_data and isinstance(config_data["search_products"], list):
                if len(config_data["search_products"]) > 0 and isinstance(config_data["search_products"][0], str):
                    print("Migrating old configuration format to new per-product pricing format...")
                    
                    # Get pricing from old format
                    base_offer_unlocked = config_data.get("base_offer_unlocked", 300)
                    base_offer_locked = config_data.get("base_offer_locked", 250)
                    base_offer_unlocked_damaged = config_data.get("base_offer_unlocked_damaged", 150)
                    base_offer_locked_damaged = config_data.get("base_offer_locked_damaged", 100)
                    
                    # Convert products to new format
                    new_products = []
                    for product_name in config_data["search_products"]:
                        new_products.append({
                            "name": product_name,
                            "base_offer_unlocked": base_offer_unlocked,
                            "base_offer_locked": base_offer_locked,
                            "base_offer_unlocked_damaged": base_offer_unlocked_damaged,
                            "base_offer_locked_damaged": base_offer_locked_damaged,
                        })
                    
                    # Update config with new format
                    config_data["search_products"] = new_products
                    
                    # Remove old pricing fields
                    for old_field in ["base_offer_unlocked", "base_offer_locked", "base_offer_unlocked_damaged", "base_offer_locked_damaged"]:
                        config_data.pop(old_field, None)
                    
                    # Save migrated config
                    self.save_config(config_data)
                    print("Configuration migration completed successfully!")
            
            return config_data
        except Exception as e:
            print(f"Error during config migration: {e}")
            return config_data
    
    def save_license(self, license_key: str, license_info: Dict[str, Any]):
        """Save license information"""
        try:
            license_data = {
                "license_key": license_key,
                "license_info": license_info,
                "saved_at": datetime.now().isoformat()
            }
            
            with open(self.license_file, 'w') as f:
                json.dump(license_data, f, indent=2)
            
            # Set file permissions
            os.chmod(self.license_file, 0o600)
            
        except Exception as e:
            raise Exception(f"Failed to save license: {e}")
    
    def get_license_status(self) -> Dict[str, Any]:
        """Get current license status"""
        try:
            if os.path.exists(self.license_file):
                with open(self.license_file, 'r') as f:
                    license_data = json.load(f)
                
                return {
                    "has_license": True,
                    "license_key": license_data.get("license_key", ""),
                    "license_info": license_data.get("license_info", {}),
                    "saved_at": license_data.get("saved_at", "")
                }
            else:
                return {
                    "has_license": False,
                    "license_key": "",
                    "license_info": {},
                    "saved_at": ""
                }
                
        except Exception as e:
            print(f"Error getting license status: {e}")
            return {
                "has_license": False,
                "license_key": "",
                "license_info": {},
                "saved_at": ""
            }
    
    def is_license_valid(self) -> bool:
        """Check if current license is valid"""
        try:
            license_status = self.get_license_status()
            if not license_status["has_license"]:
                return False
            
            license_info = license_status["license_info"]
            
            # Check if license is marked as valid
            if not license_info.get("valid", False):
                return False
            
            # Check expiration
            if "expires_at" in license_info:
                expires_at = datetime.fromisoformat(license_info["expires_at"])
                if datetime.now() > expires_at:
                    return False
            
            return True
            
        except Exception as e:
            print(f"Error checking license validity: {e}")
            return False
    
    def clear_license(self):
        """Clear saved license"""
        try:
            if os.path.exists(self.license_file):
                os.remove(self.license_file)
        except Exception as e:
            print(f"Error clearing license: {e}")
    
    def get_config_for_scripts(self) -> Dict[str, Any]:
        """Get configuration formatted for automation scripts"""
        config = self.get_config()
        
        # Format for scripts
        script_config = {
            # API Configuration
            "gemini_api_key": config.get("gemini_api_key", ""),
            
            # Search Configuration  
            "search_products": [
                product.get("name") if isinstance(product, dict) else str(product)
                for product in config.get("search_products", ["iPhone 13 Pro Max"])
            ],
            "search_keywords": config.get("search_keywords", []),
            
            # Product-specific pricing (will be passed per product)
            "product_pricing": {
                product.get("name") if isinstance(product, dict) else str(product): {
                    "unlocked_base": product.get("base_offer_unlocked", 300) if isinstance(product, dict) else 300,
                    "locked_base": product.get("base_offer_locked", 250) if isinstance(product, dict) else 250,
                    "unlocked_damaged": product.get("base_offer_unlocked_damaged", 150) if isinstance(product, dict) else 150,
                    "locked_damaged": product.get("base_offer_locked_damaged", 100) if isinstance(product, dict) else 100,
                }
                for product in config.get("search_products", ["iPhone 13 Pro Max"])
            },
            
            # Global price settings
            "pricing": {
                "flexibility": config.get("price_flexibility", 20)
            },
            
            # Limits
            "limits": {
                "max_conversations": config.get("max_conversations", 10),
                "max_offers_per_run": config.get("max_offers_per_run", 5)
            },
            
            # Browser Settings
            "browser": {
                "headless": config.get("browser_headless", False),
                "delay": config.get("browser_delay", 2)
            },
            
            # Advanced Settings
            "advanced": {
                "strategy": config.get("strategy", "primary"),
                "enable_negotiation": config.get("enable_negotiation", True)
            }
        }
        
        return script_config
    
    def export_config(self) -> Dict[str, Any]:
        """Export configuration for backup/sharing"""
        config = self.get_config()
        
        # Remove sensitive data
        export_config = config.copy()
        export_config.pop("gemini_api_key", None)
        
        return {
            "config": export_config,
            "exported_at": datetime.now().isoformat(),
            "version": "1.0.0"
        }
    
    def import_config(self, imported_config: Dict[str, Any]):
        """Import configuration from backup"""
        try:
            if "config" in imported_config:
                config = imported_config["config"]
                
                # Preserve existing API key if not in import
                current_config = self.get_config()
                if "gemini_api_key" not in config:
                    config["gemini_api_key"] = current_config.get("gemini_api_key", "")
                
                self.save_config(config)
            else:
                raise Exception("Invalid configuration format")
                
        except Exception as e:
            raise Exception(f"Failed to import configuration: {e}")
    
    def load_automation_state(self) -> AutomationState:
        """Load current automation state"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state_data = json.load(f)
                
                # Convert timestamp string back to datetime if needed
                if isinstance(state_data.get("last_run_timestamp"), str):
                    state_data["last_run_timestamp"] = datetime.fromisoformat(state_data["last_run_timestamp"])
                
                # Validate and return
                automation_state = AutomationState(**state_data)
                return automation_state
            else:
                # Return default state
                return AutomationState()
                
        except Exception as e:
            print(f"Error loading automation state: {e}")
            # Return default state on error
            return AutomationState()
    
    def save_automation_state(self, state: AutomationState):
        """Save automation state"""
        try:
            # Convert to dict and handle datetime serialization
            state_dict = state.model_dump()
            if isinstance(state_dict.get("last_run_timestamp"), datetime):
                state_dict["last_run_timestamp"] = state_dict["last_run_timestamp"].isoformat()
            
            with open(self.state_file, 'w') as f:
                json.dump(state_dict, f, indent=2)
            
            # Set file permissions
            os.chmod(self.state_file, 0o600)
            
            print(f"Automation state saved: product {state.last_completed_product_index + 1}/{len(state.current_cycle_products)}")
            
        except Exception as e:
            print(f"Error saving automation state: {e}")
            raise Exception(f"Failed to save automation state: {e}")
    
    def reset_automation_state(self, product_names: List[str] = None, automation_type: str = "full_automation"):
        """Reset automation state for a new cycle"""
        try:
            if product_names is None:
                # Get current product names from config
                config = self.get_config()
                search_products = config.get("search_products", [])
                product_names = [
                    product.get("name") if isinstance(product, dict) else str(product)
                    for product in search_products
                ]
            
            new_state = AutomationState(
                last_completed_product_index=-1,
                last_run_timestamp=datetime.now(),
                current_cycle_products=product_names,
                automation_type=automation_type,
                cycle_count=0
            )
            
            self.save_automation_state(new_state)
            print(f"Automation state reset for {len(product_names)} products")
            
            return new_state
            
        except Exception as e:
            print(f"Error resetting automation state: {e}")
            raise Exception(f"Failed to reset automation state: {e}")
    
    def get_automation_progress_info(self) -> Dict[str, Any]:
        """Get human-readable automation progress information"""
        try:
            state = self.load_automation_state()
            
            if not state.current_cycle_products:
                return {
                    "has_progress": False,
                    "message": "No automation progress tracked",
                    "next_product": None,
                    "progress_percentage": 0
                }
            
            next_index = state.get_next_product_index()
            total_products = len(state.current_cycle_products)
            
            if state.is_cycle_complete():
                return {
                    "has_progress": True,
                    "message": f"Cycle complete! Ready to start new cycle with {total_products} products",
                    "next_product": state.current_cycle_products[0] if state.current_cycle_products else None,
                    "progress_percentage": 100,
                    "cycle_count": state.cycle_count
                }
            elif state.last_completed_product_index == -1:
                return {
                    "has_progress": False,
                    "message": f"Ready to start automation with {total_products} products",
                    "next_product": state.current_cycle_products[0] if state.current_cycle_products else None,
                    "progress_percentage": 0
                }
            else:
                completed_count = state.last_completed_product_index + 1
                next_product = state.current_cycle_products[next_index] if next_index < total_products else None
                progress_percentage = int((completed_count / total_products) * 100)
                
                return {
                    "has_progress": True,
                    "message": f"Resume from '{next_product}' ({completed_count}/{total_products} products completed)",
                    "next_product": next_product,
                    "progress_percentage": progress_percentage,
                    "completed_products": state.current_cycle_products[:completed_count],
                    "last_run": state.last_run_timestamp.isoformat() if state.last_run_timestamp else None
                }
                
        except Exception as e:
            print(f"Error getting automation progress info: {e}")
            return {
                "has_progress": False,
                "message": "Error loading progress information",
                "next_product": None,
                "progress_percentage": 0
            }