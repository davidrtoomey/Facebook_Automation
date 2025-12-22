"""
FastAPI backend for Marketplace Bot Desktop App
Serves React frontend and handles automation control
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file in project root
env_file_path = project_root / ".env"
print(f"🔍 Project root: {project_root}")
print(f"🔍 Looking for .env file at: {env_file_path}")
print(f"🔍 .env file exists: {env_file_path.exists()}")

# Force load from the specific path
load_dotenv(dotenv_path=str(env_file_path), override=True)
print(f"✅ Attempted to load .env file from: {env_file_path}")
print(f"🔑 GEMINI_API_KEY found: {'Yes' if os.getenv('GEMINI_API_KEY') else 'No'}")
if os.getenv('GEMINI_API_KEY'):
    print(f"🔑 GEMINI_API_KEY value: {os.getenv('GEMINI_API_KEY')[:10]}...")

from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import asyncio
import json
from typing import Dict, Any, Optional
import webbrowser
import threading

from gui.backend.models import LicenseRequest, ConfigurationRequest, AutomationStatus
from gui.backend.license_validator import validate_license_key
from gui.backend.config_manager import ConfigManager
from gui.backend.automation_runner import AutomationRunner

def update_env_file(key: str, value: str) -> bool:
    """
    Update or add a key-value pair in the .env file
    
    Args:
        key: Environment variable key (e.g., 'GEMINI_API_KEY')
        value: Environment variable value
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        env_file_path = project_root / ".env"
        
        # Read existing .env file content
        env_lines = []
        if env_file_path.exists():
            with open(env_file_path, 'r') as f:
                env_lines = f.readlines()
        
        # Update or add the key
        key_found = False
        updated_lines = []
        
        for line in env_lines:
            if line.strip().startswith(f"{key}="):
                # Update existing key
                updated_lines.append(f"{key}={value}\n")
                key_found = True
            else:
                updated_lines.append(line)
        
        # Add new key if not found
        if not key_found:
            updated_lines.append(f"{key}={value}\n")
        
        # Write back to .env file
        with open(env_file_path, 'w') as f:
            f.writelines(updated_lines)
        
        # Update current environment
        os.environ[key] = value
        
        print(f"✅ Updated .env file: {key}")
        return True
        
    except Exception as e:
        print(f"❌ Error updating .env file: {e}")
        return False

# Initialize FastAPI app
app = FastAPI(title="Marketplace Bot", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize managers
config_manager = ConfigManager()
automation_runner = AutomationRunner()

# Global state
active_connections: Dict[str, WebSocket] = {}
current_status = AutomationStatus(
    status="idle",
    progress=0,
    message="Ready to start",
    results=[]
)

# ========================================
# Static Files (React App)
# ========================================

# Serve React app from static files
@app.get("/")
async def serve_react():
    """Serve the React app"""
    static_dir = Path(__file__).parent / "static"
    index_file = static_dir / "index.html"
    
    if index_file.exists():
        return FileResponse(index_file)
    else:
        return {"message": "React app not built yet. Run 'npm run build' in frontend/"}

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    # Mount the static/static directory to serve JS/CSS files at /static route
    inner_static_dir = static_dir / "static"
    if inner_static_dir.exists():
        app.mount("/static", StaticFiles(directory=inner_static_dir), name="static")

# Serve other static files individually
@app.get("/favicon.ico")
async def serve_favicon():
    static_dir = Path(__file__).parent / "static"
    favicon_file = static_dir / "favicon.ico"
    if favicon_file.exists():
        return FileResponse(favicon_file)
    return {"error": "Favicon not found"}

@app.get("/manifest.json")
async def serve_manifest():
    static_dir = Path(__file__).parent / "static"
    manifest_file = static_dir / "manifest.json"
    if manifest_file.exists():
        return FileResponse(manifest_file)
    return {"error": "Manifest not found"}

@app.get("/robots.txt")
async def serve_robots():
    static_dir = Path(__file__).parent / "static"
    robots_file = static_dir / "robots.txt"
    if robots_file.exists():
        return FileResponse(robots_file)
    return {"error": "Robots not found"}


# ========================================
# License Validation
# ========================================

@app.post("/api/validate-license")
async def validate_license(request: dict):
    """Validate license key"""
    try:
        license_key = request.get("license_key")
        if not license_key:
            raise HTTPException(status_code=400, detail="License key is required")
            
        is_valid, license_info = validate_license_key(license_key)
        
        if is_valid:
            # Save valid license
            config_manager.save_license(license_key, license_info)
            return {
                "valid": True,
                "license_info": license_info,
                "message": "License validated successfully"
            }
        else:
            return {
                "valid": False,
                "message": "Invalid license key"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/license-status")
async def get_license_status():
    """Get current license status"""
    return config_manager.get_license_status()

# ========================================
# Configuration Management
# ========================================

@app.post("/api/configuration")
async def save_configuration(config: dict):
    """Save user configuration"""
    try:
        # Handle Gemini API key separately - save to .env file
        gemini_api_key = config.get("gemini_api_key", "")
        if gemini_api_key and gemini_api_key.strip():
            # Save API key to .env file
            if update_env_file("GEMINI_API_KEY", gemini_api_key.strip()):
                print(f"✅ Saved Gemini API key to .env file")
            else:
                raise HTTPException(status_code=500, detail="Failed to save API key to .env file")
        
        # Remove API key from config before saving to config.json
        config_without_api_key = config.copy()
        config_without_api_key.pop("gemini_api_key", None)
        
        # Save remaining configuration to config.json
        if config_without_api_key:  # Only save if there's other config data
            config_manager.save_config(config_without_api_key)
        
        return {"message": "Configuration saved successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/configuration")
async def get_configuration():
    """Get current configuration"""
    config = config_manager.get_config()
    
    # If gemini_api_key is empty in config but exists in environment, use environment value
    if not config.get("gemini_api_key") and os.getenv('GEMINI_API_KEY'):
        config["gemini_api_key"] = os.getenv('GEMINI_API_KEY')
        print(f"✅ Using Gemini API key from environment variable")
    
    return config

@app.get("/api/automation-progress")
async def get_automation_progress():
    """Get current automation progress information"""
    return config_manager.get_automation_progress_info()

@app.post("/api/reset-automation-progress")
async def reset_automation_progress():
    """Reset automation progress to start fresh"""
    try:
        config_manager.reset_automation_state()
        return {"message": "Automation progress reset successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/negotiation-script")
async def get_negotiation_script():
    """Get current negotiation script content"""
    try:
        script_path = os.path.join(project_root, "negotiation_script.md")
        if os.path.exists(script_path):
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return {"content": content}
        else:
            return {"content": "# Negotiation Script\n\nScript file not found."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read negotiation script: {str(e)}")

@app.post("/api/negotiation-script")
async def save_negotiation_script(request: dict):
    """Save negotiation script content"""
    try:
        content = request.get("content", "")
        script_path = os.path.join(project_root, "negotiation_script.md")
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {"message": "Negotiation script saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save negotiation script: {str(e)}")

@app.get("/api/meetup-location")
async def get_meetup_location():
    """Get current meetup location from negotiation script"""
    try:
        script_path = os.path.join(project_root, "negotiation_script.md")
        if os.path.exists(script_path):
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract location from the script
            import re
            location_match = re.search(r'\*\*Standard Location\*\*: (.+)', content)
            if location_match:
                location = location_match.group(1).strip()
                return {"location": location}
        
        return {"location": "Wawa at 1860 S Collegeville Rd, Collegeville"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read meetup location: {str(e)}")

@app.post("/api/meetup-location")
async def save_meetup_location(request: dict):
    """Save meetup location to negotiation script"""
    try:
        new_location = request.get("location", "")
        script_path = os.path.join(project_root, "negotiation_script.md")
        
        if os.path.exists(script_path):
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Update all location references in the script
            import re
            
            # Update standard location line
            content = re.sub(
                r'\*\*Standard Location\*\*: .+',
                f'**Standard Location**: {new_location}',
                content
            )
            
            # Update specific location references in responses
            content = re.sub(
                r'"I\'m located in [^"]+\. (?:Can we meet at this Wawa: [^"]+|We could meet at this Wawa: [^"]+)"',
                f'"I\'m located near {new_location}. Can we meet there?"',
                content
            )
            
            # Update Wawa references
            content = re.sub(
                r'"The Wawa works well for me[^"]*"',
                f'"The location at {new_location} works well for me since it\'s public and convenient. Is that location okay for you?"',
                content
            )
            
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        return {"message": "Meetup location updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save meetup location: {str(e)}")

@app.post("/api/test-configuration")
async def test_configuration(config: dict):
    """Test configuration"""
    try:
        result = await automation_runner.test_configuration(config)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========================================
# Automation Control
# ========================================

@app.post("/api/automation/start")
async def start_automation(config: dict, background_tasks: BackgroundTasks):
    """Start automation with user configuration"""
    print("\n" + "="*50)
    print("🔥 /api/automation/start endpoint called")
    print("="*50)
    try:
        print("📋 Received config keys:", list(config.keys()))
        print("🔑 Checking license validity...")

        # Validate license first
        license_valid = config_manager.is_license_valid()
        print(f"✅ License valid: {license_valid}")

        if not license_valid:
            print("❌ License validation failed!")
            raise HTTPException(status_code=401, detail="Invalid or expired license")

        print("💾 Saving configuration...")
        # Save configuration
        config_manager.save_config(config)
        print("✅ Configuration saved successfully")

        # Start automation in background
        print("🚀 Starting automation in background...")
        background_tasks.add_task(run_automation, config)

        print("✅ Automation started successfully")
        return {"message": "Automation started successfully"}
    except HTTPException:
        print("⚠️ HTTP Exception raised, re-raising...")
        raise
    except Exception as e:
        print(f"❌ ERROR in start_automation endpoint: {e}")
        print(f"❌ Error type: {type(e)}")
        import traceback
        print(f"❌ Traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/automation/stop")
async def stop_automation():
    """Stop running automation"""
    try:
        automation_runner.stop()
        await broadcast_status("stopped", 0, "Automation stopped by user")
        return {"message": "Automation stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/automation/run-offers")
async def run_offers_only(request: dict, background_tasks: BackgroundTasks):
    """Run only the offer agent script"""
    try:
        # Validate license first
        if not config_manager.is_license_valid():
            raise HTTPException(status_code=401, detail="Invalid or expired license")
        
        # Extract config and headless setting
        config = request.get("config", {})
        headless_offers = request.get("headless_offers", True)
        
        # Add headless setting to config for persistence
        config["headless_offers"] = headless_offers
        
        # Save configuration
        config_manager.save_config(config)
        
        # Start offer agent in background
        background_tasks.add_task(run_offers_automation, config)
        
        return {"message": "Offer agent started successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/automation/run-conversations")
async def run_conversations_only(request: dict, background_tasks: BackgroundTasks):
    """Run only the conversation agent script"""
    try:
        # Validate license first
        if not config_manager.is_license_valid():
            raise HTTPException(status_code=401, detail="Invalid or expired license")
        
        # Extract config and headless setting
        config = request.get("config", {})
        headless_conversations = request.get("headless_conversations", False)
        
        # Add headless setting to config for persistence
        config["headless_conversations"] = headless_conversations
        
        # Save configuration
        config_manager.save_config(config)
        
        # Start conversation agent in background
        background_tasks.add_task(run_conversations_automation, config)
        
        return {"message": "Conversation agent started successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/automation/scrape-listings")
async def scrape_listings_only(request: dict, background_tasks: BackgroundTasks):
    """Run only the listing scraper script with custom search term"""
    try:
        # Validate license first
        if not config_manager.is_license_valid():
            raise HTTPException(status_code=401, detail="Invalid or expired license")
        
        # Extract search term and config
        search_term = request.get("search_term", "iPhone 13 Pro Max")
        config = request.get("config", {})
        
        # Add search term to config
        config["search_term"] = search_term
        
        # Save configuration
        config_manager.save_config(config)
        
        # Start listing scraper in background
        background_tasks.add_task(run_scrape_listings_automation, config)
        
        return {"message": f"Listing scraper started for: {search_term}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/automation/status")
async def get_automation_status():
    """Get current automation status"""
    return current_status

@app.get("/api/automation/results")
async def get_automation_results():
    """Get automation results"""
    return {"results": current_status.results}

@app.get("/api/detailed/listings")
async def get_detailed_listings():
    """Get detailed listings data for modal - using actual data from listings.json"""
    try:
        import json
        listings_file = os.path.join(project_root, "listings.json")
        
        if os.path.exists(listings_file):
            with open(listings_file, 'r') as f:
                listings_data = json.load(f)
            
            # Process and format listings data with actual available fields
            formatted_listings = []
            for listing in listings_data:
                # Extract item ID from URL for display
                url = listing.get("url", "")
                item_id = "Unknown"
                if "/item/" in url:
                    try:
                        item_id = url.split("/item/")[1].split("/")[0][:12]  # Truncate for display
                    except:
                        item_id = "Unknown"
                
                formatted_listings.append({
                    "item_id": item_id,
                    "product": listing.get("product") or "Unknown Product",
                    "listing_id": listing.get("listing_id", "N/A"),
                    "messaged": listing.get("messaged", False),
                    "messaged_at": listing.get("messaged_at", "N/A")[:19].replace("T", " ") if listing.get("messaged_at") else "Never",
                    "url": url
                })
            
            return {"listings": formatted_listings, "total": len(formatted_listings)}
        else:
            return {"listings": [], "total": 0}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get detailed listings: {str(e)}")

@app.get("/api/detailed/offers")
async def get_detailed_offers():
    """Get detailed offers data for modal - using actual data from listings.json where messaged=true"""
    try:
        import json
        listings_file = os.path.join(project_root, "listings.json")
        
        if os.path.exists(listings_file):
            with open(listings_file, 'r') as f:
                listings_data = json.load(f)
            
            # Filter for listings where offers were sent (messaged = true)
            offers = []
            for listing in listings_data:
                if listing.get("messaged", False):
                    # Extract item ID from URL for display
                    url = listing.get("url", "")
                    item_id = "Unknown"
                    if "/item/" in url:
                        try:
                            item_id = url.split("/item/")[1].split("/")[0][:12]  # Truncate for display
                        except:
                            item_id = "Unknown"
                    
                    offers.append({
                        "item_id": item_id,
                        "product": listing.get("product") or "Unknown Product",
                        "listing_id": listing.get("listing_id", "N/A"),
                        "messaged_at": listing.get("messaged_at", "N/A")[:19].replace("T", " ") if listing.get("messaged_at") else "N/A",
                        "url": url
                    })
            
            return {"offers": offers, "total": len(offers)}
        else:
            return {"offers": [], "total": 0}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get detailed offers: {str(e)}")

@app.get("/api/detailed/negotiations")
async def get_detailed_negotiations():
    """Get conversations data for modal - using actual data from messages.json"""
    try:
        import json
        messages_file = os.path.join(project_root, "messages.json")
        
        if os.path.exists(messages_file):
            with open(messages_file, 'r') as f:
                messages_data = json.load(f)
            
            conversations = messages_data.get("conversations", [])
            
            # Process conversations data - filter out invalid entries and show actual data we have
            formatted_conversations = []
            for conv in conversations:
                # Skip invalid/malformed conversation entries
                if not isinstance(conv, dict) or not conv.get("conversation_url"):
                    continue
                
                # Skip clearly invalid message IDs
                message_id = conv.get("message_id", "")
                if message_id in ["\\", ".", ",", ")", "\n", "\nExtracted", "{conversation_id}", "{conversation_id}.", "{conversation_id}\\", "{conversation_id},", "{conversation_id}),"] or len(message_id) < 5:
                    continue
                
                # Only include conversations with valid URLs
                conv_url = conv.get("conversation_url", "")
                if not conv_url.startswith("https://www.facebook.com/messages/t/") or "{conversation_id}" in conv_url:
                    continue
                
                # Determine who sent the last message
                message_history = conv.get("message_history", [])
                last_from = "Unknown"
                message_count = len(message_history)
                if message_history:
                    last_from = "You" if message_history[-1].get("from") == "us" else "Seller"
                
                formatted_conversations.append({
                    "message_id": message_id[:12],  # Truncate for display
                    "status": conv.get("status", "unknown").replace("_", " ").title(),
                    "last_message": conv.get("last_message", "No messages")[:60] + ("..." if len(conv.get("last_message", "")) > 60 else ""),
                    "last_from": last_from,
                    "message_count": message_count,
                    "last_updated": conv.get("last_updated", "N/A")[:19].replace("T", " ") if conv.get("last_updated") else "N/A",
                    "counter_offer": f"${conv.get('counter_offer')}" if conv.get('counter_offer') else "None",
                    "conversation_url": conv_url
                })
            
            return {"negotiations": formatted_conversations, "total": len(formatted_conversations)}
        else:
            return {"negotiations": [], "total": 0}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get detailed negotiations: {str(e)}")

@app.get("/api/statistics")
async def get_statistics():
    """Get statistics from existing data files"""
    try:
        stats = {
            "total_conversations": 0,
            "offers_sent": 0,
            "negotiations_active": 0,
            "deals_completed": 0,
            "total_listings": 0
        }
        
        # Get stats from messages.json
        messages_file = project_root / "messages.json"
        if messages_file.exists():
            with open(messages_file, 'r') as f:
                messages_data = json.load(f)
                if isinstance(messages_data, dict):
                    conversations = messages_data.get("conversations", [])
                    stats["total_conversations"] = len(conversations)
                    
                    # Count active negotiations by status
                    active_statuses = ["awaiting_response", "negotiating", "answering_questions", "deal_pending"]
                    active_negotiations = sum(1 for conv in conversations 
                                           if isinstance(conv, dict) and conv.get("status") in active_statuses)
                    stats["negotiations_active"] = active_negotiations
                    
                    # Count completed deals
                    completed_deals = sum(1 for conv in conversations 
                                        if isinstance(conv, dict) and conv.get("status") == "deal_closed")
                    stats["deals_completed"] = completed_deals
                    
                    print(f"[STATS DEBUG] Found {active_negotiations} active negotiations out of {len(conversations)} total conversations")
                    print(f"[STATS DEBUG] Active statuses found: {[conv.get('status') for conv in conversations if isinstance(conv, dict) and conv.get('status') in active_statuses]}")
        
        # Get stats from listings.json
        listings_file = project_root / "listings.json"
        if listings_file.exists():
            with open(listings_file, 'r') as f:
                listings_data = json.load(f)
                if isinstance(listings_data, list):
                    stats["total_listings"] = len(listings_data)
                    offers_sent = sum(1 for listing in listings_data if isinstance(listing, dict) and listing.get("messaged", False))
                    stats["offers_sent"] = offers_sent
                    print(f"[STATS DEBUG] Found {offers_sent} messaged listings out of {len(listings_data)} total listings")
        
        return stats
    except Exception as e:
        return {
            "total_conversations": 0,
            "offers_sent": 0,
            "negotiations_active": 0,
            "deals_completed": 0,
            "total_listings": 0
        }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Marketplace Bot is running"}

@app.get("/api/api-key-status")
async def get_api_key_status():
    """Check if Gemini API key is available"""
    try:
        from utils.config_loader import get_gemini_api_key
        api_key = get_gemini_api_key()
        return {
            "has_api_key": bool(api_key and api_key.strip()),
            "key_source": "environment" if os.getenv('GEMINI_API_KEY') else "config_file",
            "key_preview": api_key[:10] + "..." if api_key else None
        }
    except Exception as e:
        return {
            "has_api_key": False,
            "error": str(e),
            "key_source": None,
            "key_preview": None
        }

@app.get("/api/test-websocket")
async def test_websocket():
    """Test WebSocket broadcast functionality"""
    print("[TEST] Testing WebSocket broadcast...")
    
    # Test console message
    await broadcast_status("console", 0, "This is a test console message from the backend!")
    
    # Test progress update
    await broadcast_status("running", 50, "Test progress update at 50%")
    
    return {
        "message": "WebSocket test broadcast sent",
        "connected_clients": len(active_connections),
        "client_ids": list(active_connections.keys())
    }

@app.get("/api/test-subprocess")
async def test_subprocess():
    """Test subprocess output capture"""
    import asyncio
    
    print("[TEST] Testing subprocess output capture...")
    
    # Create a simple test process
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-u", "test_subprocess_output.py",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(project_root)
    )
    
    # Read output
    async def read_and_broadcast(stream, stream_name):
        while True:
            line = await stream.readline()
            if not line:
                break
            decoded = line.decode().strip()
            if decoded:
                print(f"[TEST SUBPROCESS] {stream_name}: {decoded}")
                await broadcast_status("console", 0, f"[{stream_name}] {decoded}")
    
    # Read both streams
    await asyncio.gather(
        read_and_broadcast(process.stdout, "stdout"),
        read_and_broadcast(process.stderr, "stderr"),
        process.wait()
    )
    
    return {
        "message": "Subprocess test completed",
        "return_code": process.returncode
    }

# ========================================
# WebSocket for Real-time Updates
# ========================================

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time updates"""
    print(f"[WEBSOCKET] New connection request from client: {client_id}")
    await websocket.accept()
    active_connections[client_id] = websocket
    print(f"[WEBSOCKET] Client {client_id} connected. Total connections: {len(active_connections)}")
    
    try:
        # Send current status
        await websocket.send_json({
            "type": "progress",
            "status": current_status.status,
            "progress": current_status.progress,
            "message": current_status.message,
            "results": current_status.results
        })
        print(f"[WEBSOCKET] Initial status sent to {client_id}")
        
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            # Handle ping/pong or other messages if needed
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except:
                pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        if client_id in active_connections:
            del active_connections[client_id]

async def broadcast_status(status: str, progress: int, message: str, results: list = None):
    """Broadcast status update to all connected clients"""
    global current_status
    
    # Debug logging
    print(f"[BROADCAST] Status: {status}, Progress: {progress}, Connected clients: {len(active_connections)}")
    if status == "console":
        print(f"[BROADCAST] Console message: {message}")
    
    # Handle console output separately
    if status == "console":
        # Send console message to all connected clients
        disconnected_clients = []
        for client_id, websocket in active_connections.items():
            try:
                await websocket.send_json({
                    "type": "console",
                    "message": message
                })
                print(f"[BROADCAST] Console message sent to {client_id}")
            except Exception as e:
                # Mark for removal
                print(f"[BROADCAST] Failed to send to {client_id}: {e}")
                disconnected_clients.append(client_id)
        
        # Remove dead connections
        for client_id in disconnected_clients:
            del active_connections[client_id]
        return
    
    current_status = AutomationStatus(
        status=status,
        progress=progress,
        message=message,
        results=results or []
    )
    
    # Send to all connected clients
    disconnected_clients = []
    for client_id, websocket in active_connections.items():
        try:
            await websocket.send_json({
                "type": "progress",
                "status": status,
                "progress": progress,
                "message": message,
                "results": results or [],
                "is_running": automation_runner.is_running
            })
        except:
            # Mark for removal
            disconnected_clients.append(client_id)
    
    # Remove dead connections
    for client_id in disconnected_clients:
        del active_connections[client_id]

# ========================================
# Background Tasks
# ========================================

async def run_automation(config: dict):
    """Run automation with user configuration"""
    try:
        await broadcast_status("running", 0, "Starting automation...")
        
        # Run the automation
        results = await automation_runner.run(config, broadcast_status)
        
        await broadcast_status("completed", 100, f"Automation completed. Found {len(results)} results.", results)
        
    except Exception as e:
        await broadcast_status("error", 0, f"Automation failed: {str(e)}")

async def run_offers_automation(config: dict):
    """Run only the offer agent"""
    try:
        await broadcast_status("running", 0, "Starting offer agent...")
        
        # Run only the offer agent
        results = await automation_runner.run_offers_only(config, broadcast_status)
        
        await broadcast_status("completed", 100, f"Offer agent completed. Processed {len(results)} results.", results)
        
    except Exception as e:
        await broadcast_status("error", 0, f"Offer agent failed: {str(e)}")

async def run_conversations_automation(config: dict):
    """Run only the conversation agent"""
    try:
        await broadcast_status("running", 0, "Starting conversation agent...")
        
        # Run only the conversation agent
        results = await automation_runner.run_conversations_only(config, broadcast_status)
        
        await broadcast_status("completed", 100, f"Conversation agent completed. Processed {len(results)} results.", results)
        
    except Exception as e:
        await broadcast_status("error", 0, f"Conversation agent failed: {str(e)}")

async def run_scrape_listings_automation(config: dict):
    """Run only the listing scraper"""
    try:
        search_term = config.get("search_term", "iPhone 13 Pro Max")
        await broadcast_status("running", 0, f"Starting listing scraper for: {search_term}")
        
        # Run only the listing scraper
        results = await automation_runner.run_scrape_listings_only(config, broadcast_status)
        
        await broadcast_status("completed", 100, f"Listing scraper completed. Found {len(results)} new listings.", results)
        
    except Exception as e:
        await broadcast_status("error", 0, f"Listing scraper failed: {str(e)}")

# ========================================
# Application Startup
# ========================================

def open_browser():
    """Open browser to localhost after server starts"""
    import time
    time.sleep(1)  # Wait for server to start
    webbrowser.open("http://localhost:8000")

@app.on_event("startup")
async def startup_event():
    """Initialize app on startup"""
    print("🚀 Marketplace Bot Backend Starting...")
    print("📱 React frontend will be available at: http://localhost:8000")
    
    # Open browser automatically
    threading.Timer(1.0, open_browser).start()

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("🛑 Marketplace Bot Backend Shutting down...")
    
    # Stop any running automation
    automation_runner.stop()
    
    # Close all WebSocket connections
    for client_id, websocket in list(active_connections.items()):
        try:
            await websocket.close()
        except:
            pass
    active_connections.clear()

# ========================================
# Pricing Management Endpoints
# ========================================

class PricingRequest(BaseModel):
    margin_percent: float

@app.post("/api/update-pricing")
async def update_pricing_margin(request: PricingRequest):
    """Update pricing data with new margin percentage"""
    try:
        # Import the pricing manager
        from utils.pricing_manager import recalculate_offer_prices
        
        # Validate margin range
        if not (0 <= request.margin_percent <= 50):
            raise HTTPException(status_code=400, detail="Margin must be between 0 and 50 percent")
        
        # Recalculate offer prices with new margin
        success = recalculate_offer_prices(request.margin_percent)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update pricing data")
        
        # Load updated config to return stats
        config_file = os.path.expanduser("~/.marketplace-bot/config.json")
        total_models = 0
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                offer_prices = config.get("offer_prices", [])
                total_models = len(offer_prices)
        
        return {
            "success": True,
            "margin_percent": request.margin_percent,
            "total_models": total_models,
            "message": f"Pricing updated with {request.margin_percent}% margin"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update pricing: {str(e)}")

@app.post("/api/run-pricing-script")
async def run_pricing_script():
    """Run the pricing script to fetch data from Google Sheets"""
    try:
        import subprocess
        import sys
        
        # Path to the pricing script
        script_path = os.path.join(project_root, "utils", "get_pricing_data.py")
        venv_python = os.path.join(project_root, ".venv", "bin", "python")
        
        # Check if virtual environment exists
        if not os.path.exists(venv_python):
            venv_python = sys.executable  # Fallback to current Python
        
        # Run the pricing script
        result = subprocess.run(
            [venv_python, script_path],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode != 0:
            raise HTTPException(
                status_code=500, 
                detail=f"Pricing script failed: {result.stderr}"
            )
        
        # Check if pricing data was created
        raw_data_file = os.path.join(project_root, "pricing_data_raw.json")
        if not os.path.exists(raw_data_file):
            raise HTTPException(
                status_code=500,
                detail="Pricing script completed but no data file was created"
            )
        
        # Load the raw pricing data and transfer it to config.json
        try:
            from utils.pricing_manager import update_pricing_data
            import json
            
            with open(raw_data_file, 'r') as f:
                raw_pricing_data = json.load(f)
            
            # Get current margin from existing config or use 20% as fallback
            config_file = os.path.expanduser("~/.marketplace-bot/config.json")
            current_margin = 20.0  # fallback
            
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r') as f:
                        existing_config = json.load(f)
                    current_margin = existing_config.get("margin_percent", 20.0)
                    print(f"Using existing margin: {current_margin}%")
                except:
                    print("Could not read existing margin, using 20% fallback")
            
            # Update config.json with the fetched pricing data using current margin
            success = update_pricing_data(raw_pricing_data, current_margin)
            
            if not success:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to transfer pricing data to config.json"
                )
            
            return {
                "success": True,
                "message": f"Pricing data fetched and updated successfully! Processed {len(raw_pricing_data)} iPhone models.",
                "models_processed": len(raw_pricing_data),
                "output": result.stdout
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process pricing data: {str(e)}"
            )
        
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Pricing script timed out after 5 minutes")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run pricing script: {str(e)}")

# ========================================
# Catch-all route for React Router (MUST be last)
# ========================================

@app.get("/{path:path}")
async def serve_react_routes(path: str):
    """Serve React app for all frontend routes"""
    # Only serve React app for non-API routes and non-static files
    if not path.startswith("api") and not path.startswith("static"):
        static_dir = Path(__file__).parent / "static"
        index_file = static_dir / "index.html"
        
        if index_file.exists():
            return FileResponse(index_file)
    
    # Return 404 for unknown API routes or missing files
    raise HTTPException(status_code=404, detail="Not found")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)