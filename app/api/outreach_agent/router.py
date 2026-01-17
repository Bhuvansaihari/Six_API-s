"""
FastAPI router for Outreach Agent V1 API.

This module handles webhook-based job match notifications via email (SendGrid) and SMS (Twilio).
"""
import asyncio
import html
import re
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Request, status
from fastapi.responses import JSONResponse

from app.api.outreach_agent.schemas import WebhookPayload, WebhookResponse
from app.services.outreach_agent.database import (
    get_application_details,
    mark_email_sent,
    mark_sms_sent
)
from app.services.outreach_agent.utils import (
    format_phone_number,
    validate_phone_number,
    validate_webhook_payload,
    extract_plain_description
)
from app.services.outreach_agent.email_template import render_email_template, get_email_subject
from app.services.outreach_agent.email_service import send_email
from app.services.outreach_agent.sms_service import send_sms
from config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook/outreach", tags=["outreach-agent"])


async def process_notifications_for_application(
    cand_id: int,
    requirement_id: str,
    semaphore: asyncio.Semaphore
):
    """
    Process email and SMS notifications for a job application.
    
    This function is called asynchronously for each webhook event.
    It respects candidate preferences (notify_email, notify_sms) and
    marks notifications as sent in the database.
    
    Args:
        cand_id: Candidate ID
        requirement_id: Requirement ID
        semaphore: Semaphore for concurrency control
    """
    async with semaphore:
        try:
            # Fetch application details from database
            app_data = await asyncio.get_event_loop().run_in_executor(
                None, get_application_details, cand_id, requirement_id
            )
            
            if not app_data:
                logger.info("⏸️ Application not found or already sent. Skipping.")
                return

            candidate = app_data['candidate']
            requirement = app_data['requirement']
            application_id = app_data['application_id']
            application_status = app_data['application_status']
            email_sent = app_data['email_sent']
            sms_sent = app_data['sms_sent']
            notify_email = candidate.get("notify_email", True)
            notify_sms = candidate.get("notify_sms", False)

            # Extract and clean job description
            raw_description = requirement.get('requirement_description', '')
            plain_desc = extract_plain_description(raw_description)
            clean_description = re.sub(r'<[^>]+>', '', plain_desc)
            clean_description = html.unescape(clean_description)
            if len(clean_description) > 250:
                clean_description = clean_description[:250].strip() + '...'

            first_name = candidate['candidate_first_name']
            match_score_int = int(requirement['similarity_score'] * 100)
            job_type = "Contract"
            if requirement.get('requirement_duration'):
                job_type = f"Contract ({requirement['requirement_duration']})"

            # Send EMAIL if enabled and not already sent
            if notify_email and not email_sent:
                rendered_email_html = render_email_template(
                    candidate_name=first_name,
                    job_title=requirement['requirement_title'],
                    company_name=requirement.get('client_name', 'N/A'),
                    location=requirement.get('location', 'Remote'),
                    job_type=job_type,
                    match_score=str(match_score_int),
                    short_description=clean_description,
                    application_status=application_status.upper()
                )
                email_subject = get_email_subject(
                    job_title=requirement['requirement_title'],
                    company_name=requirement.get('client_name', 'N/A'),
                    match_score=str(match_score_int)
                )
                
                settings = get_settings()
                await asyncio.get_event_loop().run_in_executor(
                    None, send_email,
                    candidate['candidate_email'],
                    email_subject,
                    rendered_email_html,
                    settings.outreach_agent_sendgrid_from_email
                )
                await asyncio.get_event_loop().run_in_executor(
                    None, mark_email_sent, application_id
                )
                logger.info(
                    "✅ Email sent",
                    extra={'log_to_db': True, 'service_name': 'outreach_agent', 'action': 'email_sent', 'candidate_id': cand_id, 'application_id': application_id}
                )
            else:
                logger.info("⏭️ Email not sent (preference false or already sent)")

            # Send SMS if enabled and not already sent
            if notify_sms and not sms_sent:
                candidate_mobile = (
                    candidate.get('candidate_mobile') or 
                    candidate.get('candidate_work') or 
                    candidate.get('candidate_home') or 
                    ''
                )
                formatted_phone = format_phone_number(candidate_mobile)
                if candidate_mobile and validate_phone_number(formatted_phone):
                    sms_text = (
                        f"Hi {first_name or 'Candidate'}! "
                        f"Job Matched: {requirement['requirement_title']} "
                        f"({match_score_int}% fit). "
                        "Auto-applied for you. Recruiter will contact soon!"
                    )[:160]
                    await asyncio.get_event_loop().run_in_executor(
                        None, send_sms, formatted_phone, sms_text
                    )
                    await asyncio.get_event_loop().run_in_executor(
                        None, mark_sms_sent, application_id
                    )
                    logger.info(
                        "✅ SMS sent",
                        extra={'log_to_db': True, 'service_name': 'outreach_agent', 'action': 'sms_sent', 'candidate_id': cand_id, 'application_id': application_id}
                    )
                else:
                    logger.warning("⚠️ No valid phone for SMS")
            else:
                logger.info("⏭️ SMS not sent (preference false or already sent)")

        except Exception as e:
            logger.error(f"❌ Error in notification: {e}", exc_info=True)


@router.post("/job-match", response_model=WebhookResponse, status_code=status.HTTP_202_ACCEPTED)
async def webhook_handler(
    payload: WebhookPayload,
    request: Request,
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret")
):
    """
    Handle webhook events from Supabase for job match notifications.
    
    This endpoint receives webhook events when a new job application is created
    in the `job_application_tracking` table. It validates the webhook secret,
    extracts candidate and requirement IDs, and queues notification processing.
    
    Args:
        payload: Webhook payload from Supabase (JSON body)
        request: FastAPI request object (for accessing app state)
        x_webhook_secret: Webhook secret header for authentication
        
    Returns:
        WebhookResponse with status and queued task information
        
    Raises:
        HTTPException: If webhook secret is invalid or payload is malformed
    """
    try:
        settings = get_settings()
        
        # Validate webhook secret if configured
        webhook_secret = settings.outreach_agent_webhook_secret
        if webhook_secret:
            secret_value = webhook_secret.get_secret_value() if hasattr(webhook_secret, 'get_secret_value') else str(webhook_secret)
            if x_webhook_secret != secret_value:
                logger.error("❌ Invalid webhook secret")
                raise HTTPException(status_code=401, detail="Invalid webhook secret")
        
        logger.info(f"📨 WEBHOOK RECEIVED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Convert Pydantic model to dict for validation (using aliases to match original JSON structure)
        payload_dict = payload.model_dump(by_alias=True)
        
        # Validate payload structure
        if not validate_webhook_payload(payload_dict):
            raise HTTPException(status_code=400, detail="Invalid payload structure")
        
        # Only process INSERT events for job_application_tracking table
        if payload.type != "INSERT" or payload.table != "job_application_tracking":
            return JSONResponse(
                status_code=200,
                content={"status": "ignored"}
            )
        
        record = payload.record
        cand_id = record.get('cand_id')
        requirement_id = record.get('requirement_id')
        
        if not cand_id or not requirement_id:
            raise HTTPException(
                status_code=400, 
                detail="cand_id and requirement_id required"
            )
        
        # Convert requirement_id to string if it's not already (database function expects string)
        requirement_id = str(requirement_id)
        
        # Get semaphore from app state
        semaphore = request.app.state.outreach_agent_semaphore
        
        # Queue notification processing task
        asyncio.create_task(
            process_notifications_for_application(cand_id, requirement_id, semaphore)
        )
        
        return JSONResponse(
            status_code=202,
            content={
                "status": "accepted",
                "message": "Notifications queued",
                "cand_id": cand_id,
                "requirement_id": requirement_id,
                "timestamp": datetime.now().isoformat(),
                "concurrency": {
                    "max_concurrent_tasks": settings.outreach_agent_max_concurrent_tasks
                }
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """
    Health check endpoint for Outreach Agent API.
    
    Returns:
        dict: Health status and concurrency information
    """
    return {
        "status": "healthy",
        "service": "outreach-agent-v1",
        "timestamp": datetime.now().isoformat(),
        "capabilities": ["email", "sms", "html_templates", "parallel_processing"]
    }

