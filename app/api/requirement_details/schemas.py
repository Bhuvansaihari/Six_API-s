"""
Pydantic models for Requirement Details API requests and responses.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Union
from decimal import Decimal


class RequirementDetailsResponse(BaseModel):
    """
    Response model for requirement details.
    
    Maps database column names to user-friendly field names.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "JobTitle": "Software Engineer",
                "City": "New York",
                "ZIPCode": "10001",
                "Duration": "12 months",
                "ShiftTimingFrom": "09:00",
                "ShiftTimingTo": "18:00",
                "HoursPerWeek": 37.5,
                "MinPayRate": 50000.0,
                "MaxPayRate": 80000.0,
                "JobDescription": "Job description here..."
            }
        }
    )
    
    JobTitle: Optional[str] = Field(None, alias="JobTitleText", description="Job title")
    City: Optional[str] = Field(None, alias="CityName", description="City name")
    ZIPCode: Optional[Union[str, int]] = Field(None, description="ZIP code")
    Duration: Optional[str] = Field(None, alias="RequirementDuration", description="Job duration")
    ShiftTimingFrom: Optional[str] = Field(None, alias="RequirementShiftTimingFrom", description="Shift start time")
    ShiftTimingTo: Optional[str] = Field(None, alias="RequirementShiftTimingTo", description="Shift end time")
    HoursPerWeek: Optional[Union[Decimal, float, str]] = Field(None, alias="RequirementHoursPerWeek", description="Hours per week")
    MinPayRate: Optional[Union[Decimal, float]] = Field(None, description="Minimum pay rate")
    MaxPayRate: Optional[Union[Decimal, float]] = Field(None, description="Maximum pay rate")
    JobDescription: Optional[str] = Field(None, alias="RequirementJobDescription", description="Job description")

