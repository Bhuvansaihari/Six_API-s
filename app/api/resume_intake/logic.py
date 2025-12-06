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


# Prompt for structuring resume data
STRUCTURE_PROMPT = """You are a data structuring specialist with deep knowledge of resume parsing and information extraction. 
Your task is to analyze the extracted resume text and structure it into a comprehensive JSON format.

Extract and organize the following information:

1. PersonalInformation:
   - Summary (if available)
   - Name
   - Email
   - Phone Number
   - Location (city, State, StateShortName, Country)
   - Zipcode
   - Links (LinkedIn, GitHub, Portfolio, etc.)

2. ProfessionalExperience:
   - Overall Experience (calculate total years based on employment dates)
   - Category (e.g., Software Engineer, Data Scientist, etc.)
   - List of Experiences, each with:
     * Job Title
     * Company Name
     * Industry
     * Dates (start and end dates)
     * Experience years (duration at this position)
     * Location
     * Skills used
     * Responsibilities

3. Education:
   - Degree type
   - Specialization
   - Institution
   - Graduation date

4. Skills:
   - Technical Skills
   - Soft Skills
   - Language Proficiency

5. Certification:
   - Name
   - Issuing Organization
   - Date

6. Projects (if any):
   - Project name
   - Description
   - Technologies used
   - Duration

7. AdditionalInformation:
   - Volunteer Experience
   - Interests/Hobbies

IMPORTANT REQUIREMENTS:
- Calculate overall experience based on employment dates
- All JSON keys must be in snake_case (e.g., personal_information, not PersonalInformation)
- Use 'certification' (singular), not 'certifications'
- Ensure all data is accurately extracted and properly formatted
- Return ONLY valid JSON, no additional text or markdown
- If a field is not found, use null or empty array/object as appropriate
"""


async def structure_resume_data(text: str) -> Dict[str, Any]:
    """
    Structure resume text into JSON format using GPT-4o (async).
    
    Args:
        text: Raw resume text
        
    Returns:
        Structured JSON dictionary
        
    Raises:
        ValueError: If OpenAI API key is not configured
    """
    settings = get_settings()
    
    if not settings.openai_api_key:
        raise ValueError("OpenAI API key not configured. Please set OPENAI_API_KEY in .env file")
    
    client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
    
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": STRUCTURE_PROMPT},
            {"role": "user", "content": f"Extract and structure the following resume text into JSON format:\n\n{text}"}
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
        data: Structured resume JSON
        
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
    
    # Personal Information
    if 'personal_information' in data:
        pi_raw = data['personal_information']
        pi = safe_get_dict(pi_raw, {})
        
        if isinstance(pi, dict):
            # Try both snake_case and PascalCase keys
            name = pi.get('Name', pi.get('name', ''))
            email = pi.get('Email', pi.get('email', ''))
            phone = pi.get('Phone Number', pi.get('phone_number', ''))
            text_parts.append(f"Name: {name}")
            text_parts.append(f"Email: {email}")
            text_parts.append(f"Phone: {phone}")
            
            if 'Location' in pi or 'location' in pi:
                loc_raw = pi.get('Location') or pi.get('location', {})
                loc = safe_get_dict(loc_raw, {})
                if isinstance(loc, dict):
                    city = loc.get('city', '') or loc.get('City', '')
                    state = loc.get('state', '') or loc.get('State', '')
                    country = loc.get('country', '') or loc.get('Country', '')
                    text_parts.append(f"Location: {city}, {state}, {country}")
            
            summary = pi.get('Summary', pi.get('summary', ''))
            if summary:
                text_parts.append(f"Summary: {summary}")
    
    # Professional Experience
    if 'professional_experience' in data:
        pe_raw = data['professional_experience']
        pe = safe_get_dict(pe_raw, {})
        
        if isinstance(pe, dict):
            exp_years = pe.get('Overall Experience', pe.get('overall_experience', ''))
            category = pe.get('Category', pe.get('category', ''))
            text_parts.append(f"Overall Experience: {exp_years} years")
            text_parts.append(f"Category: {category}")
            
            if 'Experiences' in pe or 'experiences' in pe:
                experiences = pe.get('Experiences', pe.get('experiences', []))
                experiences = safe_get_list(experiences, [])
                for exp in experiences:
                    if isinstance(exp, dict):
                        job_title = exp.get('Job Title', exp.get('job_title', ''))
                        company = exp.get('Company Name', exp.get('company_name', ''))
                        dates = exp.get('Dates', exp.get('dates', ''))
                        exp_yrs = exp.get('Experience Years', exp.get('experience_years', ''))
                        text_parts.append(f"Job: {job_title} at {company}")
                        text_parts.append(f"Duration: {dates} ({exp_yrs} years)")
                        if 'Responsibilities' in exp or 'responsibilities' in exp:
                            resp = exp.get('Responsibilities', exp.get('responsibilities', []))
                            if isinstance(resp, list):
                                text_parts.append(f"Responsibilities: {', '.join(str(r) for r in resp)}")
    
    # Education
    if 'education' in data:
        education = safe_get_list(data['education'], [])
        for edu in education:
            if isinstance(edu, dict):
                degree = edu.get('Degree Type', edu.get('degree_type', ''))
                specialization = edu.get('Specialization', edu.get('specialization', ''))
                institution = edu.get('Institution', edu.get('institution', ''))
                text_parts.append(f"Education: {degree} in {specialization} from {institution}")
    
    # Skills
    if 'skills' in data:
        skills_raw = data['skills']
        skills = safe_get_dict(skills_raw, {})
        if isinstance(skills, dict):
            tech_skills = skills.get('Technical Skills', skills.get('technical_skills', []))
            if isinstance(tech_skills, str):
                tech_skills = [s.strip() for s in tech_skills.split(',') if s.strip()]
            if isinstance(tech_skills, list):
                text_parts.append(f"Technical Skills: {', '.join(str(s) for s in tech_skills)}")
            
            soft_skills = skills.get('Soft Skills', skills.get('soft_skills', []))
            if isinstance(soft_skills, str):
                soft_skills = [s.strip() for s in soft_skills.split(',') if s.strip()]
            if isinstance(soft_skills, list):
                text_parts.append(f"Soft Skills: {', '.join(str(s) for s in soft_skills)}")
    
    # Certifications
    if 'certification' in data:
        certs = safe_get_list(data['certification'], [])
        for cert in certs:
            if isinstance(cert, dict):
                name = cert.get('Name', cert.get('name', ''))
                org = cert.get('Issuing Organization', cert.get('issuing_organization', ''))
                text_parts.append(f"Certification: {name} from {org}")
    
    # Projects
    if 'projects' in data:
        projects = safe_get_list(data['projects'], [])
        for project in projects:
            if isinstance(project, dict):
                name = project.get('Name', project.get('name', ''))
                desc = project.get('Description', project.get('description', ''))
                text_parts.append(f"Project: {name} - {desc}")
    
    return "\n".join(text_parts)


async def process_resume_async(file_path: str, candidate_id: int) -> Dict[str, Any]:
    """
    Process a resume file through the complete pipeline (async).
    
    Pipeline steps:
    1. Parse resume file (PDF/DOCX/TXT) to extract text
    2. Structure data using GPT-4o
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
        
        # Step 2: Structure data using GPT-4o (async)
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

