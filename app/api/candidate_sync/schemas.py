from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr


class CandidateSyncRequest(BaseModel):
    """Incoming payload for candidate sync."""

    email: EmailStr


class CandidateContact(BaseModel):
    """Subset of candidate information persisted to Supabase."""

    candidate_id: int
    first_name: Optional[str]
    last_name: Optional[str]
    email: EmailStr
    password: Optional[str]
    birth_date: Optional[date]
    ssn: Optional[str]
    over_18_age: Optional[bool]
    mobile: Optional[str]
    home: Optional[str]
    work: Optional[str]
    work_ext: Optional[str]
    relocation: Optional[bool]


class CandidateSyncResponse(BaseModel):
    """API response for candidate sync attempts."""

    success: bool
    message: str
    data: Optional[CandidateContact] = None

