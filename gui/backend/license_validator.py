"""
License validation system for Marketplace Bot
Validates license keys against a simple API or local storage
"""

import requests
import json
import os
from datetime import datetime, timedelta
from typing import Tuple, Dict, Any, Optional
import hashlib
import uuid

class LicenseValidator:
    """Simple license validation system"""
    
    def __init__(self):
        self.cache_file = os.path.expanduser("~/.marketplace-bot-license")
        self.license_api_url = "https://your-license-api.com/validate"  # Replace with actual API
        
    def validate_license_key(self, license_key: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Validate license key against API or local cache
        Returns (is_valid, license_info)
        """
        try:
            # First check local cache
            cached_license = self._load_cached_license()
            if cached_license and cached_license.get("license_key") == license_key:
                if self._is_license_still_valid(cached_license):
                    return True, cached_license
            
            # Validate against API
            is_valid, license_info = self._validate_against_api(license_key)
            
            if is_valid:
                # Cache valid license
                self._save_license_cache(license_key, license_info)
                return True, license_info
            
            return False, None
            
        except Exception as e:
            print(f"License validation error: {e}")
            # Fall back to cached license if API is unavailable
            cached_license = self._load_cached_license()
            if cached_license and cached_license.get("license_key") == license_key:
                if self._is_license_still_valid(cached_license):
                    return True, cached_license
            
            return False, None
    
    def _validate_against_api(self, license_key: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Validate license key against API"""
        try:
            # For now, implement simple validation logic
            # In production, this would call your license server
            
            # Simple validation: check if key matches expected format
            if self._is_valid_license_format(license_key):
                # Create mock license info
                license_info = {
                    "license_key": license_key,
                    "valid": True,
                    "expires_at": (datetime.now() + timedelta(days=30)).isoformat(),
                    "plan_type": "pro",
                    "features": ["marketplace_automation", "unlimited_runs"],
                    "validated_at": datetime.now().isoformat()
                }
                return True, license_info
            
            return False, None
            
        except Exception as e:
            print(f"API validation error: {e}")
            return False, None
    
    def _is_valid_license_format(self, license_key: str) -> bool:
        """Check if license key matches expected format"""
        # Simple format validation
        if not license_key:
            return False
            
        # Check for test key
        if license_key == "TEST-1234-5678-9ABC":
            return True
            
        # Check for proper format (e.g., XXXX-XXXX-XXXX-XXXX)
        parts = license_key.split("-")
        if len(parts) == 4:
            for part in parts:
                if len(part) == 4 and part.isalnum():
                    continue
                else:
                    return False
            return True
            
        return False
    
    def _load_cached_license(self) -> Optional[Dict[str, Any]]:
        """Load cached license from local storage"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading cached license: {e}")
        return None
    
    def _save_license_cache(self, license_key: str, license_info: Dict[str, Any]):
        """Save license to local cache"""
        try:
            cache_data = {
                **license_info,
                "cached_at": datetime.now().isoformat(),
                "machine_id": self._get_machine_id()
            }
            
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
                
            # Set file permissions (owner only)
            os.chmod(self.cache_file, 0o600)
            
        except Exception as e:
            print(f"Error saving license cache: {e}")
    
    def _is_license_still_valid(self, license_info: Dict[str, Any]) -> bool:
        """Check if cached license is still valid"""
        try:
            # Check expiration
            if "expires_at" in license_info:
                expires_at = datetime.fromisoformat(license_info["expires_at"])
                if datetime.now() > expires_at:
                    return False
            
            # Check machine ID (prevent license sharing)
            if "machine_id" in license_info:
                if license_info["machine_id"] != self._get_machine_id():
                    return False
            
            # Check cache age (revalidate periodically)
            if "cached_at" in license_info:
                cached_at = datetime.fromisoformat(license_info["cached_at"])
                if datetime.now() - cached_at > timedelta(days=7):
                    return False
            
            return True
            
        except Exception as e:
            print(f"Error checking license validity: {e}")
            return False
    
    def _get_machine_id(self) -> str:
        """Get unique machine identifier"""
        try:
            # Use MAC address as machine ID
            mac = uuid.getnode()
            return hashlib.md5(str(mac).encode()).hexdigest()
        except:
            return "unknown"
    
    def clear_license_cache(self):
        """Clear cached license"""
        try:
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
        except Exception as e:
            print(f"Error clearing license cache: {e}")

# Global instance
_license_validator = LicenseValidator()

def validate_license_key(license_key: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Validate license key (convenience function)"""
    return _license_validator.validate_license_key(license_key)

def clear_license_cache():
    """Clear license cache (convenience function)"""
    _license_validator.clear_license_cache()