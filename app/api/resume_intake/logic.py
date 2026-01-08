"""Core processing logic for resume processing pipeline with async support."""

import json
import asyncio
import logging
from typing import Dict, Any
from openai import AsyncOpenAI

from config import get_settings
from app.services.resume_intake.resume_parser import ResumeParser
from app.services.resume_intake.database import DatabaseService
from app.services.resume_intake.embeddings import EmbeddingService
from app.services.resume_intake.vector_store import VectorStoreService

logger = logging.getLogger(__name__)


# Canonical JSON Schema (DO NOT CHANGE KEYS)
CANONICAL_SCHEMA = {
    "basic_information": {
        "first_name": None,
        "last_name": None,
        "email": None,
        "mobile_phone": None,
        "home_phone": None,
        "work_phone": None,
        "work_extension": None,
        "birth_date": None
    },
    "location_information": {
        "address": None,
        "city": None,
        "country": None,
        "zipcode": None
    },
    "skills_expertise": {
        "total_experience_years": None,
        "technical_skills": [],
        "soft_skills": [],
        "languages": []
    },
    "professional_summary": None,
    "education": [
        {
            "degree": None,
            "field_of_study": None,
            "school": None,
            "year": None,
            "gpa": None
        }
    ],
    "certifications": [
        {
            "name": None,
            "issuing_organization": None,
            "issue_date": None,
            "expiry_date": None,
            "credential_id": None,
            "credential_url": None
        }
    ],
    "work_experience": [
        {
            "job_title": None,
            "company": None,
            "location": None,
            "start_date": None,
            "end_date": None,
            "currently_working": None,
            "job_description": None
        }
    ],
    "projects": [
        {
            "name": None,
            "description": None,
            "url": None,
            "start_date": None,
            "end_date": None,
            "technologies_used": []
        }
    ],
    "achievements": []
}


# OpenAI System Message
SYSTEM_PROMPT = """You are a resume parser.
Return ONLY valid JSON.
Follow the provided schema EXACTLY.
Do NOT add extra keys.
Do NOT guess or infer missing information.
If a field is not explicitly present in the resume, return null or [].
Dates must be in YYYY-MM-DD format or null.
total_experience_years must be an integer (rounded down)."""


def get_user_prompt(resume_text: str) -> str:
    """Generate user prompt with schema and resume text."""
    schema_str = json.dumps(CANONICAL_SCHEMA, indent=2)
    return f"""Extract information from the following resume text and map it strictly to the provided JSON schema.

IMPORTANT RULES:
- Output must match the schema EXACTLY
- Do not infer or assume missing values
- If data is absent, return null or []
- Split full name into first_name and last_name
- Languages should be simple strings (e.g., "English", "Hindi")
- total_experience_years must be an integer

SCHEMA:
{schema_str}

RESUME TEXT:
{resume_text}
"""


async def structure_resume_data(text: str) -> Dict[str, Any]:
    """
    Structure resume text into JSON format using GPT-4o (async).
    
    Args:
        text: Raw resume text
        
    Returns:
        Structured JSON dictionary matching the canonical schema
        
    Raises:
        ValueError: If OpenAI API key is not configured
    """
    settings = get_settings()
    
    if not settings.openai_api_key:
        raise ValueError("OpenAI API key not configured. Please set OPENAI_API_KEY in .env file")
    
    client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
    
    user_prompt = get_user_prompt(text)
    
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.1
    )
    
    # Parse JSON response
    structured_data = json.loads(response.choices[0].message.content)
    return structured_data


def convert_json_to_text(data: Dict[str, Any]) -> str:
    """
    Convert structured JSON resume data to text representation for embeddings.
    
    Args:
        data: Structured resume JSON (canonical schema)
        
    Returns:
        Text representation of the resume
    """
    text_parts = []
    
    # Helper function to safely get dict value
    def safe_get_dict(value, default=None):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except:
                return default if default is not None else {}
        return value if isinstance(value, dict) else (default if default is not None else {})
    
    def safe_get_list(value, default=None):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except:
                return default if default is not None else []
        return value if isinstance(value, list) else (default if default is not None else [])
    
    # Basic Information
    if 'basic_information' in data:
        basic = safe_get_dict(data.get('basic_information'), {})
        if isinstance(basic, dict):
            first_name = basic.get('first_name', '')
            last_name = basic.get('last_name', '')
            name = f"{first_name} {last_name}".strip()
            if name:
                text_parts.append(f"Name: {name}")
            
            email = basic.get('email', '')
            if email:
                text_parts.append(f"Email: {email}")
            
            mobile = basic.get('mobile_phone', '')
            if mobile:
                text_parts.append(f"Phone: {mobile}")
    
    # Location Information
    if 'location_information' in data:
        location = safe_get_dict(data.get('location_information'), {})
        if isinstance(location, dict):
            location_parts = []
            if location.get('address'):
                location_parts.append(str(location.get('address')))
            if location.get('city'):
                location_parts.append(str(location.get('city')))
            if location.get('country'):
                location_parts.append(str(location.get('country')))
            if location_parts:
                text_parts.append(f"Location: {', '.join(location_parts)}")
    
    # Professional Summary
    if 'professional_summary' in data and data.get('professional_summary'):
        text_parts.append(f"Summary: {data.get('professional_summary')}")
    
    # Skills and Expertise
    if 'skills_expertise' in data:
        skills = safe_get_dict(data.get('skills_expertise'), {})
        if isinstance(skills, dict):
            total_exp = skills.get('total_experience_years')
            if total_exp is not None:
                text_parts.append(f"Total Experience: {total_exp} years")
            
            tech_skills = skills.get('technical_skills', [])
            if isinstance(tech_skills, list) and tech_skills:
                text_parts.append(f"Technical Skills: {', '.join(str(s) for s in tech_skills)}")
            
            soft_skills = skills.get('soft_skills', [])
            if isinstance(soft_skills, list) and soft_skills:
                text_parts.append(f"Soft Skills: {', '.join(str(s) for s in soft_skills)}")
            
            languages = skills.get('languages', [])
            if isinstance(languages, list) and languages:
                text_parts.append(f"Languages: {', '.join(str(l) for l in languages)}")
    
    # Work Experience
    if 'work_experience' in data:
        work_exp = safe_get_list(data.get('work_experience'), [])
        for exp in work_exp:
            if isinstance(exp, dict):
                job_title = exp.get('job_title', '')
                company = exp.get('company', '')
                start_date = exp.get('start_date', '')
                end_date = exp.get('end_date', '')
                currently_working = exp.get('currently_working', False)
                
                if job_title or company:
                    text_parts.append(f"Job: {job_title} at {company}")
                    if start_date:
                        end_str = "Present" if currently_working else end_date
                        text_parts.append(f"Duration: {start_date} to {end_str}")
                    if exp.get('job_description'):
                        text_parts.append(f"Description: {exp.get('job_description')}")
    
    # Education
    if 'education' in data:
        education = safe_get_list(data.get('education'), [])
        for edu in education:
            if isinstance(edu, dict):
                degree = edu.get('degree', '')
                field = edu.get('field_of_study', '')
                school = edu.get('school', '')
                year = edu.get('year', '')
                if degree or field or school:
                    text_parts.append(f"Education: {degree} in {field} from {school} ({year})")
    
    # Certifications
    if 'certifications' in data:
        certs = safe_get_list(data.get('certifications'), [])
        for cert in certs:
            if isinstance(cert, dict):
                name = cert.get('name', '')
                org = cert.get('issuing_organization', '')
                if name or org:
                    text_parts.append(f"Certification: {name} from {org}")
    
    # Projects
    if 'projects' in data:
        projects = safe_get_list(data.get('projects'), [])
        for project in projects:
            if isinstance(project, dict):
                name = project.get('name', '')
                desc = project.get('description', '')
                if name or desc:
                    text_parts.append(f"Project: {name} - {desc}")
    
    # Achievements
    if 'achievements' in data:
        achievements = safe_get_list(data.get('achievements'), [])
        if achievements:
            text_parts.append(f"Achievements: {', '.join(str(a) for a in achievements)}")
    
    return "\n".join(text_parts)


async def process_resume_async(file_path: str, candidate_id: int) -> Dict[str, Any]:
    """
    Process a resume file through the complete pipeline (async).
    
    Pipeline steps:
    1. Parse resume file (PDF/DOCX/TXT) to extract text
    2. Structure data using GPT-4o with canonical schema
    3. Update database records in parallel (raw and parsed)
    4. Generate embeddings
    5. Store embeddings in Qdrant
    
    Args:
        file_path: Path to the resume file
        candidate_id: Candidate ID from logged-in user (required)
        
    Returns:
        Dictionary with success status and candidate_id
        
    Raises:
        Exception: If any step in the pipeline fails
    """
    try:
        # Step 1: Parse resume (run in thread pool for I/O)
        parser = ResumeParser()
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, parser.parse, file_path)
        
        # Step 2: Structure data using GPT-4o (async) with canonical schema
        structured_data = await structure_resume_data(text)
        
        # Step 3: Prepare data for parallel operations
        db_service = DatabaseService()
        embedding_service = EmbeddingService()
        vector_store = VectorStoreService()
        
        # Convert structured data to text for embeddings (synchronous, fast)
        resume_text = convert_json_to_text(structured_data)
        
        # Step 4: Run independent operations in parallel
        # - Database updates can run in parallel (they don't depend on each other)
        # - Embedding generation can run in parallel with database operations
        # - Qdrant storage depends on embeddings, so it runs after
        
        # Create tasks for parallel execution
        tasks = [
            # Database operations (run in parallel)
            loop.run_in_executor(
                None,
                db_service.update_raw_resume,
                candidate_id,
                structured_data,
                file_path
            ),
            loop.run_in_executor(
                None,
                db_service.update_parsed_resume,
                candidate_id,
                structured_data,
                resume_text
            ),
            # Embedding generation (async, can run in parallel with DB operations)
            embedding_service.generate_async(resume_text)
        ]
        
        # Wait for all parallel operations to complete
        raw_result, parsed_result, embeddings = await asyncio.gather(*tasks)
        
        # Step 5: Store embeddings in Qdrant (depends on embeddings, so runs after)
        await loop.run_in_executor(
            None,
            vector_store.store,
            candidate_id,
            embeddings,
            {"resume_text": resume_text[:500]}  # Store first 500 chars as metadata
        )
        
        logger.info(f"Successfully processed resume for candidate_id={candidate_id}")
        
        return {
            "success": True,
            "candidate_id": candidate_id,
            "message": f"Resume processed successfully. Candidate ID: {candidate_id}"
        }
        
    except Exception as e:
        logger.error(f"Error processing resume for candidate_id={candidate_id}: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "message": f"Error processing resume: {str(e)}"
        }
