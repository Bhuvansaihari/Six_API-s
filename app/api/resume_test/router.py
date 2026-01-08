"""
TEST ENDPOINT - Resume Parsing Test
===================================

This is a temporary test endpoint for testing resume parsing.
Can be safely deleted later without affecting main APIs.

Endpoint: POST /test/resume-parse
"""

import asyncio
import json
import logging
import tempfile
import os
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from app.api.resume_intake.logic import structure_resume_data, convert_json_to_text
from app.services.resume_intake.resume_parser import ResumeParser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/test", tags=["test-resume-parsing"])


@router.post("/resume-parse")
async def test_resume_parse(file: UploadFile = File(...)):
    """
    TEST ENDPOINT: Upload and parse a resume file.
    
    This endpoint:
    1. Accepts a resume file (PDF, DOCX, TXT)
    2. Extracts text from the file
    3. Structures data using GPT-4o
    4. Returns the parsed JSON
    
    ⚠️ This is a temporary test endpoint and can be deleted later.
    
    Args:
        file: Resume file to parse (PDF, DOCX, or TXT)
        
    Returns:
        JSON response with:
        - success: bool
        - parsed_data: Complete parsed JSON matching canonical schema
        - text_preview: First 500 characters of extracted text
        - text_representation: Text format for embeddings
        - file_info: File metadata
        
    Raises:
        HTTPException: If file type is unsupported or parsing fails
    """
    # Validate file type
    allowed_extensions = {'.pdf', '.docx', '.doc', '.txt'}
    file_extension = Path(file.filename).suffix.lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_extension}. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    tmp_file_path = None
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        logger.info(f"Testing resume parsing for file: {file.filename}")
        
        # Step 1: Parse resume file
        parser = ResumeParser()
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, parser.parse, tmp_file_path)
        
        if not text or len(text.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail="Failed to extract text from resume file. File may be empty or corrupted."
            )
        
        # Step 2: Structure data using GPT-4o
        try:
            structured_data = await structure_resume_data(text)
        except ValueError as e:
            if "OpenAI API key" in str(e):
                raise HTTPException(
                    status_code=500,
                    detail="OpenAI API key not configured. Please set OPENAI_API_KEY in .env file"
                )
            raise HTTPException(status_code=500, detail=f"Error structuring data: {str(e)}")
        except Exception as e:
            logger.error(f"Error structuring resume data: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error parsing resume: {str(e)}")
        
        # Step 3: Convert to text representation (for embeddings)
        resume_text = convert_json_to_text(structured_data)
        
        # Step 4: Prepare response
        response_data = {
            "success": True,
            "message": "Resume parsed successfully",
            "file_info": {
                "filename": file.filename,
                "file_type": file_extension,
                "file_size": len(content),
                "text_length": len(text)
            },
            "text_preview": text[:500] + "..." if len(text) > 500 else text,
            "parsed_data": structured_data,
            "text_representation": resume_text
        }
        
        logger.info(f"Successfully parsed resume: {file.filename}")
        
        return JSONResponse(
            status_code=200,
            content=response_data
        )
        
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"File not found: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid file format: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error parsing resume: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing resume: {str(e)}")
    finally:
        # Clean up temporary file
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.unlink(tmp_file_path)
            except Exception as e:
                logger.warning(f"Could not delete temporary file {tmp_file_path}: {e}")

