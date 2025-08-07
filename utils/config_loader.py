#!/usr/bin/env python3

"""
Configuration loader utility for Marketplace Bot
Provides centralized access to configuration values with fallback logic
"""

import os
import json
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file (safety net)
try:
    # Try to load from project root
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)  # Go up from utils/ to project root
    env_file = os.path.join(project_root, ".env")
    load_dotenv(dotenv_path=env_file, override=False)  # Don't override if already loaded
except ImportError:
    # python-dotenv not installed, skip loading
    pass
except Exception:
    # If path resolution fails, try default
    try:
        load_dotenv()
    except:
        pass


def get_gemini_api_key() -> str:
    """
    Get Gemini API key from environment variable or config file
    
    Priority:
    1. GEMINI_API_KEY environment variable (useful for CI/CD, Docker, etc.)
    2. ~/.marketplace-bot/config.json file (GUI configuration)
    
    Returns:
        str: The Gemini API key
        
    Raises:
        ValueError: If API key is not found in either location
    """
    # Try environment variable first (highest priority)
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key and api_key.strip():
        print("✅ Using Gemini API key from environment variable")
        return api_key.strip()
    
    # Fallback to config file
    try:
        config_file = os.path.expanduser("~/.marketplace-bot/config.json")
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                api_key = config.get("gemini_api_key")
                if api_key and api_key.strip():
                    print("✅ Using Gemini API key from config file (~/.marketplace-bot/config.json)")
                    return api_key.strip()
    except (json.JSONDecodeError, IOError, KeyError) as e:
        print(f"⚠️ Error reading config file: {e}")
    
    # If we get here, no API key was found
    raise ValueError(
        "GEMINI_API_KEY not found. Please either:\n"
        "1. Set GEMINI_API_KEY environment variable, or\n"
        "2. Configure API key through the GUI (stored in ~/.marketplace-bot/config.json)"
    )


def get_config_value(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get a configuration value from config file
    
    Args:
        key: Configuration key to retrieve
        default: Default value if not found
        
    Returns:
        Configuration value or default
    """
    try:
        config_file = os.path.expanduser("~/.marketplace-bot/config.json")
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                return config.get(key, default)
    except (json.JSONDecodeError, IOError, KeyError) as e:
        print(f"⚠️ Error reading config file for key '{key}': {e}")
    
    return default


def config_exists() -> bool:
    """
    Check if the config file exists
    
    Returns:
        bool: True if config file exists, False otherwise
    """
    config_file = os.path.expanduser("~/.marketplace-bot/config.json")
    return os.path.exists(config_file)


def load_full_config() -> dict:
    """
    Load the full configuration from config file
    
    Returns:
        dict: Full configuration or empty dict if not found
    """
    try:
        config_file = os.path.expanduser("~/.marketplace-bot/config.json")
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️ Error reading full config: {e}")
    
    return {}


if __name__ == "__main__":
    """Test the config loader"""
    try:
        api_key = get_gemini_api_key()
        print(f"✅ API key found: {api_key[:10]}...{api_key[-4:]}")
        
        if config_exists():
            print("✅ Config file exists")
            config = load_full_config()
            print(f"✅ Config keys available: {list(config.keys())}")
        else:
            print("❌ Config file not found")
            
    except ValueError as e:
        print(f"❌ Error: {e}")