"""
SMS service for Outreach Agent V1 using Twilio.
"""
import logging
from twilio.rest import Client as TwilioClient
from config import get_settings

logger = logging.getLogger(__name__)


def send_sms(candidate_mobile: str, message_body: str) -> str:
    """
    Send an SMS using Twilio.
    
    Args:
        candidate_mobile: Recipient phone number (E.164 format, e.g., +1234567890)
        message_body: SMS message text (max 160 characters recommended)
        
    Returns:
        Message SID from Twilio
        
    Raises:
        ValueError: If Twilio configuration is missing
        Exception: If SMS sending fails
    """
    settings = get_settings()
    
    account_sid = settings.outreach_agent_twilio_account_sid
    auth_token = settings.outreach_agent_twilio_auth_token
    from_phone = settings.outreach_agent_twilio_phone_number
    
    if not account_sid or not auth_token or not from_phone:
        raise ValueError("TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER must be set in .env file")
    
    try:
        client = TwilioClient(
            account_sid.get_secret_value(),
            auth_token.get_secret_value()
        )
        message = client.messages.create(
            body=message_body,
            from_=from_phone,
            to=candidate_mobile
        )
        logger.info(f"✅ SMS sent to {candidate_mobile} (SID: {message.sid})")
        return message.sid
        
    except Exception as e:
        logger.error(f"❌ Error sending SMS to {candidate_mobile}: {str(e)}", exc_info=True)
        raise

