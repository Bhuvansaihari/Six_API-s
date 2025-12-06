"""
Pydantic models for Outreach Agent V1 API.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any


class WebhookPayload(BaseModel):
    """Webhook payload model from Supabase."""
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "type": "INSERT",
                "table": "job_application_tracking",
                "record": {
                    "cand_id": 2928,
                    "requirement_id": 130174
                },
                "schema": "public",
                "old_record": None
            }
        }
    )
    
    type: str
    table: str
    record: Dict[str, Any]
    schema_name: str = Field(..., alias="schema", description="Database schema name")
    old_record: Optional[Dict[str, Any]] = None


class WebhookResponse(BaseModel):
    """Response model for webhook endpoint."""
    status: str
    message: str
    cand_id: Optional[int] = None
    requirement_id: Optional[str] = None
    timestamp: str
    concurrency: Dict[str, int]

