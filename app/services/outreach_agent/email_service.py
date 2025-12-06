"""
Email service for Outreach Agent V1 using SendGrid.
"""
import logging
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from config import get_settings

logger = logging.getLogger(__name__)


def send_email(candidate_email: str, subject: str, html_content: str, from_email: str = None) -> int:
    """
    Send an email using SendGrid.
    
    Args:
        candidate_email: Recipient email address
        subject: Email subject line
        html_content: HTML content of the email
        from_email: Sender email address (optional, uses config default if not provided)
        
    Returns:
        HTTP status code from SendGrid API
        
    Raises:
        ValueError: If SendGrid configuration is missing
        Exception: If email sending fails
    """
    settings = get_settings()
    
    api_key = settings.outreach_agent_sendgrid_api_key
    if not api_key:
        raise ValueError("SENDGRID_API_KEY must be set in .env file")
    
    from_email = from_email or settings.outreach_agent_sendgrid_from_email
    if not from_email:
        raise ValueError("SENDGRID_FROM_EMAIL must be set in .env file")
    
    try:
        sg = SendGridAPIClient(api_key.get_secret_value())
        message = Mail(
            from_email=from_email,
            to_emails=candidate_email,
            subject=subject,
            html_content=html_content
        )
        
        # Add reply-to if configured
        if settings.outreach_agent_sendgrid_reply_to_email:
            message.reply_to = settings.outreach_agent_sendgrid_reply_to_email
        
        response = sg.send(message)
        logger.info(f"✅ Email sent to {candidate_email} (status: {response.status_code})")
        return response.status_code
        
    except Exception as e:
        logger.error(f"❌ Error sending email to {candidate_email}: {str(e)}", exc_info=True)
        raise

