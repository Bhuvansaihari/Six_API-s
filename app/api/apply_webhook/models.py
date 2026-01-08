from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class WebhookPayload(BaseModel):
    """Supabase webhook payload structure"""
    type: str
    table: str
    record: Optional[dict] = None
    old_record: Optional[dict] = None


class CandJobMatching(BaseModel):
    """Model for cand_job_matching table"""
    matching_id: int
    cand_id: int
    requirement_id: str
    similarity_score: Optional[float] = None
    match_reason: Optional[str] = None
    matched_skills: Optional[List[str]] = None
    matched_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = True


class AutoApplyCand(BaseModel):
    """Model for auto_apply_cand table"""
    cand_id: int
    disability_id: Optional[int] = None
    veteran_disclosure_id: Optional[int] = None
    ethnicity_id: Optional[int] = None
    race_id: Optional[int] = None
    gender_id: Optional[int] = None
    is_remote_preferred: Optional[bool] = None
    Preferred_MinimumPayrate_PerHour: Optional[float] = None


class StoredProcedureParams(BaseModel):
    """Parameters for Usp_SC_JobSeeker_IU_ApplyJob stored procedure"""
    CandidateID: int
    RequirementID: int
    DisabilityID: int = 0
    VeteranDisclosureID: int = 0
    EthnicityID: int = 0
    HumanRaceID: int = 0
    GenderID: int = 0
    FileName: Optional[str] = None
    FileExtension: Optional[str] = None
    FileType: Optional[str] = None
    FileContent: Optional[bytes] = None
    ResumeID: int = 0
    ServedAsTxnsJson: Optional[str] = None
    ReqTalentChannelID: int = 0

