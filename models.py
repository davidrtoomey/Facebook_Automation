from pydantic import BaseModel, Field 
from typing import List, Optional, Dict, Any
try:
    # Pydantic v2
    from pydantic import RootModel
except ImportError:
    # Fallback for older Pydantic versions
    from pydantic import create_model
    def RootModel(root_type):
        return create_model('RootModel', __root__=(root_type, ...))
from datetime import datetime
import re

class ListingModel(BaseModel):
    """Model for a marketplace listing."""
    url: str
    messaged: bool = False
    messaged_at: Optional[str] = None
    product: Optional[str] = None
    
    def normalize_url(self) -> str:
        """Normalize URL by removing tracking parameters."""
        if not self.url:
            return ""
            
        # For Facebook URLs, standardize to domain + path pattern
        if "facebook.com" in self.url or self.url.startswith("/marketplace"):
            # Extract the item ID
            match = re.search(r'(?:facebook\.com)?/marketplace/item/(\d+)', self.url)
            if match:
                item_id = match.group(1)
                return f"https://www.facebook.com/marketplace/item/{item_id}"
                
        # Default case - just strip query parameters
        return self.url.split('?')[0]
    
    def ensure_full_url(self) -> None:
        """Ensure URL has full domain if it's a Facebook marketplace URL."""
        if self.url and self.url.startswith('/marketplace/item/'):
            self.url = f"https://www.facebook.com{self.url}"
    
class ListingsData(RootModel):
    """Model for the listings.json file structure."""
    root: List[ListingModel] = Field(default_factory=list)
    
    def __iter__(self):
        return iter(self.root)
    
    def __getitem__(self, item):
        return self.root[item]
    
    def __len__(self):
        return len(self.root)
        
    def append(self, listing: ListingModel):
        self.root.append(listing)
        
    def save(self, filepath: str) -> None:
        """Save listings to a JSON file."""
        import json
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump([listing.model_dump() for listing in self.root], f, indent=4)
            
    @classmethod
    def load(cls, filepath: str) -> 'ListingsData':
        """Load listings from a JSON file."""
        import json
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                listings_data = json.load(f)
                return cls(root=[ListingModel(**item) for item in listings_data])
        except (FileNotFoundError, json.JSONDecodeError):
            return cls()
    
class ConversationModel(BaseModel):
    """Model for a marketplace conversation."""

    conversation_url: str
    seller_name: Optional[str] = None
    product_name: Optional[str] = None
    title: Optional[str] = None  # For backward compatibility with get_marketplace_urls.py
    status: Optional[str] = "new"  # new, active, negotiating, deal_closed, cancelled
    last_message: Optional[str] = None
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())
    message_history: List[Dict[str, Any]] = Field(default_factory=list)
    offer_amount: Optional[float] = None
    counter_offer: Optional[float] = None
    final_price: Optional[float] = None
    message_id: Optional[str] = None


class MessagesData(BaseModel):
    """Model for the messages.json file structure."""

    conversations: List[ConversationModel] = Field(default_factory=list)
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())
    total_conversations: int = 0
    active_conversations: int = 0
    closed_conversations: int = 0
    deals_closed: int = 0
    total_spent: float = 0


def load_messages_json() -> MessagesData:
    """Load messages.json file, create if it doesn't exist."""
    import json
    
    messages_file = "messages.json"
    try:
        with open(messages_file, "r") as f:
            data = json.load(f)

        # Convert the loaded JSON to our Pydantic model
        if isinstance(data, dict):
            # Convert conversations to ConversationModel objects
            if "conversations" in data:
                conversations = []
                for conv in data["conversations"]:
                    if isinstance(conv, dict):
                        conversations.append(ConversationModel(**conv))
                data["conversations"] = conversations

            return MessagesData(**data)
        else:
            # Default if data is not in expected format
            return MessagesData()

    except (FileNotFoundError, json.JSONDecodeError):
        # Create default structure
        default_messages = MessagesData()
        with open(messages_file, "w") as f:
            json.dump(default_messages.model_dump(), f, indent=2)
        return default_messages


def save_messages_json(messages_data: MessagesData) -> MessagesData:
    """Save messages.json file."""
    import json
    
    # Update the timestamp and counts
    messages_data.last_updated = datetime.now().isoformat()
    messages_data.total_conversations = len(messages_data.conversations)

    # Extract message IDs for deduplication
    def extract_message_id(url):
        if not url:
            return None
        match = re.search(r"facebook\.com/messages/t/([^/?&]+)", url)
        return match.group(1) if match else None

    # Deduplicate conversations by message ID
    deduplicated = {}
    for conv in messages_data.conversations:
        msg_id = extract_message_id(conv.conversation_url)
        if msg_id and msg_id not in deduplicated:
            deduplicated[msg_id] = conv
        elif msg_id and msg_id in deduplicated:
            # If duplicate, keep the one with the most recent update
            existing_conv = deduplicated[msg_id]
            if conv.last_updated > existing_conv.last_updated:
                deduplicated[msg_id] = conv

    # Update conversations list with deduplicated entries
    messages_data.conversations = list(deduplicated.values())

    # Save to file
    with open("messages.json", "w") as f:
        # Convert to dict for JSON serialization
        json_data = messages_data.model_dump()
        json.dump(json_data, f, indent=2)

    print(f"✅ Saved {len(messages_data.conversations)} conversations to messages.json")
    return messages_data


def extract_message_id_from_url(url):
    """Extract message thread ID from Facebook URL."""
    if not url:
        return None

    # Clean URL first - remove any trailing markers, newlines, or garbage text
    clean_url = str(url).strip()

    # Remove escaped newlines and anything after them
    clean_url = re.sub(r'\\n.*$', '', clean_url)
    clean_url = re.sub(r'\n.*$', '', clean_url)

    # Remove CONVERSATION_URL markers
    clean_url = re.sub(r'\s*CONVERSATION_URL_END.*$', '', clean_url)
    clean_url = re.sub(r'\s*CONVERSATION_URL_START.*$', '', clean_url)
    clean_url = clean_url.strip()

    # Extract the message ID - should be numeric only
    # Pattern: get everything after /t/ that looks like a message ID (numbers only)
    match = re.search(r"facebook\.com/messages/t/(\d+)", clean_url)
    if match:
        return match.group(1)

    # Fallback: try to extract any alphanumeric ID (some IDs might have letters)
    match = re.search(r"facebook\.com/messages/t/([a-zA-Z0-9]+)", clean_url)
    return match.group(1) if match else None


def find_conversation_by_message_id(
    messages_data: MessagesData, message_id: str
) -> Optional[ConversationModel]:
    """Find existing conversation by message thread ID."""
    if not message_id:
        return None

    for conv in messages_data.conversations:
        # Try both the stored message_id and extracted from URL (to handle malformed data)
        conv_message_id = extract_message_id_from_url(conv.conversation_url)
        stored_message_id = extract_message_id_from_url(conv.message_id) if conv.message_id else None
        
        if (conv_message_id and conv_message_id == message_id) or \
           (stored_message_id and stored_message_id == message_id):
            return conv
    return None