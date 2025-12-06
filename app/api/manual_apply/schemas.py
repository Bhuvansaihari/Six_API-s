"""
Pydantic models for Manual Apply API.
"""
from pydantic import BaseModel, Field
from typing import Optional


class ManualApplyRequest(BaseModel):
    """Request model for manual job application"""
    cand_id: int = Field(..., description="Candidate ID", gt=0)
    requirement_id: int = Field(..., description="Requirement/Job ID", gt=0)


class ManualApplyResponse(BaseModel):
    """Response model for manual job application"""
    success: bool
    message: str
    cand_id: int
    requirement_id: int
    selection_id: Optional[int] = None
    application_id: Optional[int] = None

