# Facebook Marketplace Negotiation Script

## Initial Offer Strategy (Handled by offer_agent.py)
- **Unlocked phones**: "Hi I can do $300 cash for it"
- **Network locked phones**: "Hi I can do $200 cash for it" 
- **Damaged items**: "Hi, can you tell me more about the damage?"

## Response Handling (For conversation_agent.py)

### If Seller Accepts Our Initial Offer
**Response**: "Okay great, I'm located in Collegeville. Can we meet at this Wawa: 1860 S Collegeville Rd"

### If Seller Declines Initial Offer (No Counter-Offer)
**Response**: "How much were you looking to get for it?"

### If Seller Makes Counter-Offer
**Response**: "Hmm ${their_counter_offer} would be tough for me. I could do ${our_initial_offer + $10-20} though"

**Examples**:
- Our initial: $280, Their counter: $350 → "Hmm $350 would be tough for me. I could do $300 though"
- Our initial: $300, Their counter: $400 → "Hmm $400 would be tough for me. I could do $320 though"
- Our initial: $200, Their counter: $320 → "Hmm $320 would be tough for me. I could do $270 though"

### If Seller Declines Our Counter-Offer
**Response**: "Okay I totally understand. Let me know if anything changes - my offer will still stand."

## Additional Scenarios

### If Seller Asks About Location/Where We're Located
**Response**: "I'm located in Collegeville. We could meet at this Wawa: 1860 S Collegeville Rd"

### If Seller Asks Questions About Phone Condition
**Response**: "I'm looking for a working iPhone 13 Pro Max in good condition. What's the condition like?"

### If Seller Asks About Payment Method
**Response**: "I can do cash - that works best for me"

### If Seller Asks About Timing/When to Meet
**Response**: "I'm pretty flexible with timing. What works best for you?"

### If Seller Mentions Other Interested Buyers
**Response**: "No problem, let me know if the other buyer doesn't work out"

### If Seller Says Item is Sold
**Response**: "Thanks for letting me know! If it falls through let me know"

### If Seller Asks for More Details About Us
**Response**: "I'm a local buyer looking for an iPhone 13 Pro Max for personal use"

### If Seller Wants to Negotiate Meeting Location
**Response**: "The Wawa works well for me since it's public and convenient. Is that location okay for you?"

## Agent Help Request Scenarios

### When Agent Needs Human Help
**Trigger Situations**:
- Seller response is unclear or confusing
- Seller asks complex questions about the phone's technical specs
- Seller makes unusual requests or conditions
- Seller mentions issues not covered in standard responses
- Seller becomes aggressive or suspicious
- Conversation takes unexpected turns

**Agent Action**: 
1. Stop responding to the seller
2. Mark conversation as "needs_human_help"
3. Send SMS notification with details
4. Wait for human instructions

**SMS Format for Help Requests**:
```
🤖 AGENT HELP NEEDED
Item: iPhone 13 Pro Max - $[price]
Seller: [seller_name]
Issue: [brief description]
Last message: "[seller's message]"
Link: [marketplace_url]
```

## Notification Triggers

### Deal Closed Successfully
**Trigger**: Seller agrees to meet at our location with agreed price
**SMS Format**:
```
✅ DEAL CLOSED!
Item: iPhone 13 Pro Max - $[agreed_price]
Seller: [seller_name] 
Meetup: [agreed_time] at Wawa Collegeville
Link: [marketplace_url]
```

## Meetup Location
**Standard Location**: Wawa at 1860 S Collegeville Rd, Collegeville

## Notes
- Initial offers already sent by offer_agent.py
- Always stick to cash offers
- Maximum counter-offer: Initial offer + $20
- Keep responses concise and friendly
- Always suggest the same Wawa location for consistency
- Be polite and understanding if deals don't work out
- Stay firm on pricing boundaries while being respectful
- **When uncertain, ask for human help rather than risk the deal**
