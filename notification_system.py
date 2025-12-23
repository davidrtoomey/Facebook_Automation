#!/usr/bin/env python3

"""
Email Notification System for Facebook Marketplace Bot
Uses AWS SES for email notifications when deals close or agent needs help
"""

import os
import boto3
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# AWS SES configuration
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
SES_FROM_EMAIL = os.getenv('SES_FROM_EMAIL', 'david@kitekeylabs.com')  # Verified sender email
# Email address is now configurable via config
DEFAULT_EMAIL = 'example@gmail.com'

def send_email(subject, message, email_address=None):
    """Send email notification using AWS SES"""
    try:
        target_email = email_address or DEFAULT_EMAIL
        
        if not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, SES_FROM_EMAIL]):
            print("⚠️ AWS SES credentials not configured. Add to .env file:")
            print("AWS_ACCESS_KEY_ID=your_access_key")
            print("AWS_SECRET_ACCESS_KEY=your_secret_key") 
            print("AWS_REGION=us-east-1")
            print("SES_FROM_EMAIL=your_verified@email.com")
            print(f"Would have sent email to {target_email} with subject: {subject}")
            print(f"Message: {message}")
            return False
            
        # Create SES client
        ses_client = boto3.client(
            'ses',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        
        # Send email using SES
        response = ses_client.send_email(
            Source=SES_FROM_EMAIL,
            Destination={
                'ToAddresses': [target_email]
            },
            Message={
                'Subject': {
                    'Data': subject,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Text': {
                        'Data': message,
                        'Charset': 'UTF-8'
                    }
                }
            }
        )
        
        print(f"✅ Email sent successfully to {target_email}: {response['MessageId']}")
        return True
        
    except ses_client.exceptions.MessageRejected as e:
        print(f"❌ Email rejected by SES: {e}")
        print("This usually means the recipient email is invalid or the sender email is not verified")
        return False
    except ses_client.exceptions.SendingPausedException as e:
        print(f"❌ SES sending is paused: {e}")
        print("Your SES account may be in sandbox mode or temporarily suspended")
        return False
    except ses_client.exceptions.MailFromDomainNotVerifiedException as e:
        print(f"❌ Sender email not verified: {e}")
        print(f"Please verify {SES_FROM_EMAIL} in the AWS SES console")
        return False
    except Exception as e:
        print(f"❌ Failed to send email to {target_email}: {e}")
        print(f"Subject was: {subject}")
        print(f"Message was: {message}")
        return False

def notify_deal_closed(listing_item, agreed_price, seller_name=None, meetup_time=None, email_address=None):
    """Send notification when a deal is successfully closed"""

    # Handle both Pydantic models and dictionaries
    if hasattr(listing_item, 'offer_amount'):
        # It's a ConversationModel (Pydantic)
        fallback_price = listing_item.offer_amount or 'Unknown'
        url = listing_item.conversation_url or 'No URL'
        product = listing_item.product_name or 'iPhone'
    elif isinstance(listing_item, dict):
        # It's a dictionary
        fallback_price = listing_item.get('offer_price', listing_item.get('offer_amount', 'Unknown'))
        url = listing_item.get('url', listing_item.get('conversation_url', 'No URL'))
        product = listing_item.get('product_name', 'iPhone')
    else:
        fallback_price = 'Unknown'
        url = 'No URL'
        product = 'iPhone'

    price = agreed_price or fallback_price
    seller = seller_name or "Unknown Seller"
    meetup = meetup_time or "TBD"

    subject = f"✅ DEAL CLOSED - {product} ${price}"

    message = f"""Deal Successfully Closed!

Item: {product} - ${price}
Seller: {seller}
Meetup: {meetup} at Wawa Collegeville
Link: {url}
Time: {datetime.now().strftime('%I:%M %p on %m/%d/%Y')}

Please verify all details before the meetup and bring exact cash amount."""

    return send_email(subject, message, email_address)

def notify_agent_needs_help(listing_item, issue_description, last_seller_message, seller_name=None, email_address=None):
    """Send notification when agent needs human help"""

    # Handle both Pydantic models and dictionaries
    if hasattr(listing_item, 'offer_amount'):
        # It's a ConversationModel (Pydantic)
        price = listing_item.offer_amount or 'Unknown'
        url = listing_item.conversation_url or 'No URL'
        product = listing_item.product_name or 'Unknown Product'
    elif isinstance(listing_item, dict):
        # It's a dictionary
        price = listing_item.get('offer_price', listing_item.get('offer_amount', 'Unknown'))
        url = listing_item.get('url', listing_item.get('conversation_url', 'No URL'))
        product = listing_item.get('product_name', 'Unknown Product')
    else:
        price = 'Unknown'
        url = 'No URL'
        product = 'Unknown Product'

    seller = seller_name or "Unknown Seller"

    # Truncate long messages for subject, but keep full message in body
    truncated_message = last_seller_message[:100] + "..." if len(last_seller_message) > 100 else last_seller_message

    subject = f"🤖 AGENT HELP NEEDED - {seller} (${price})"

    message = f"""Agent Needs Human Intervention

Item: {product} - ${price}
Seller: {seller}
Issue: {issue_description}
Time: {datetime.now().strftime('%I:%M %p on %m/%d/%Y')}

Last message from seller:
"{last_seller_message}"

Link to conversation: {url}

Please review the conversation and take appropriate action. The agent was unable to handle this situation automatically."""

    return send_email(subject, message, email_address)

def test_email_system(email_address=None):
    """Test the email notification system"""
    subject = "🧪 Email Test - Facebook Marketplace Bot"
    
    test_message = f"""Email Notification Test

Facebook Marketplace Bot
System: Operational
Time: {datetime.now().strftime('%I:%M %p on %m/%d/%Y')}

This is a test email to verify that the AWS SNS email notification system is working correctly.

If you received this email, the notification system is properly configured and ready to send alerts for:
- Deal closures
- Deal declines
- Agent help requests
- High-value deal warnings"""
    
    print("Testing email notification system...")
    success = send_email(subject, test_message, email_address)
    
    if success:
        print("✅ Email system working correctly!")
    else:
        print("❌ Email system needs configuration")
    
    return success

if __name__ == '__main__':
    # Test the system when run directly
    test_email_system()
