"""
Pydantic models for the Marketplace Bot API
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class ProductPricing(BaseModel):
    """Pricing configuration for a specific product"""
    name: str = Field(..., description="Product name")
    base_offer_unlocked: int = Field(default=300, description="Base offer for unlocked devices")
    base_offer_locked: int = Field(default=250, description="Base offer for locked devices") 
    base_offer_unlocked_damaged: int = Field(default=150, description="Base offer for unlocked damaged devices")
    base_offer_locked_damaged: int = Field(default=100, description="Base offer for locked damaged devices")

class LicenseRequest(BaseModel):
    """License validation request"""
    license_key: str = Field(..., min_length=1, description="License key to validate")

class LicenseInfo(BaseModel):
    """License information"""
    license_key: str
    valid: bool
    expires_at: Optional[datetime] = None
    plan_type: str = "basic"
    features: List[str] = []

class AutomationConfig(BaseModel):
    """User configuration for automation"""
    # API Keys
    gemini_api_key: str = Field(default="", description="User's Gemini API key")
    
    # Notification Configuration
    notification_email: str = Field(default="", description="Email address for notifications")
    
    # Search Configuration
    search_products: List[ProductPricing] = Field(
        default=[ProductPricing(name="iPhone 13 Pro Max")], 
        description="Products to search for with their pricing"
    )
    search_keywords: List[str] = Field(default=[], description="Additional keywords")
    
    # Global Price Configuration
    price_flexibility: int = Field(default=20, description="Price flexibility range")
    
    # Limits
    max_conversations: int = Field(default=10, description="Maximum conversations to extract")
    max_offers_per_run: int = Field(default=5, description="Maximum offers to send per run")
    
    # Browser Settings
    browser_headless: bool = Field(default=False, description="Run browser in headless mode")
    browser_delay: int = Field(default=2, description="Delay between browser actions (seconds)")
    
    # Advanced Settings
    strategy: str = Field(default="primary", description="Automation strategy")
    enable_negotiation: bool = Field(default=True, description="Enable automatic negotiation")
    
class ConfigurationRequest(BaseModel):
    """Configuration save/update request"""
    config: AutomationConfig

class AutomationStatus(BaseModel):
    """Current automation status"""
    status: str = Field(default="idle", description="Current status: idle, running, completed, error")
    progress: int = Field(default=0, description="Progress percentage (0-100)")
    message: str = Field(default="", description="Status message")
    results: List[Dict[str, Any]] = Field(default=[], description="Automation results")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class AutomationResult(BaseModel):
    """Single automation result"""
    url: str
    status: str
    message: str
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None

class WebSocketMessage(BaseModel):
    """WebSocket message format"""
    type: str = Field(..., description="Message type: status, log, result")
    data: Dict[str, Any] = Field(..., description="Message data")
    timestamp: datetime = Field(default_factory=datetime.now)

class LogEntry(BaseModel):
    """Log entry for real-time updates"""
    level: str = Field(..., description="Log level: info, warning, error")
    message: str = Field(..., description="Log message")
    timestamp: datetime = Field(default_factory=datetime.now)
    details: Optional[Dict[str, Any]] = None

class AutomationState(BaseModel):
    """Tracks automation progress across runs"""
    last_completed_product_index: int = Field(default=-1, description="Index of last completed product (-1 means none completed)")
    last_run_timestamp: datetime = Field(default_factory=datetime.now, description="When automation last ran")
    current_cycle_products: List[str] = Field(default=[], description="Product names from current cycle configuration")
    automation_type: str = Field(default="full_automation", description="Type of automation: full_automation, offers_only, conversations_only")
    cycle_count: int = Field(default=0, description="Number of complete cycles run")
    
    def is_cycle_complete(self) -> bool:
        """Check if current cycle is complete"""
        return self.last_completed_product_index >= len(self.current_cycle_products) - 1
    
    def get_next_product_index(self) -> int:
        """Get the index of the next product to process"""
        if self.is_cycle_complete():
            return 0  # Start new cycle
        return self.last_completed_product_index + 1
    
    def reset_for_new_cycle(self, product_names: List[str]) -> 'AutomationState':
        """Reset state for a new automation cycle"""
        return AutomationState(
            last_completed_product_index=-1,
            last_run_timestamp=datetime.now(),
            current_cycle_products=product_names,
            automation_type=self.automation_type,
            cycle_count=self.cycle_count + 1 if self.is_cycle_complete() else self.cycle_count
        )