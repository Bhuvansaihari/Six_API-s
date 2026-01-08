"""
Standalone test script for resume parsing.
Tests resume parsing without database operations.

Usage:
    python test_resume_parser.py <resume_file_path>

Example:
    python test_resume_parser.py resume.pdf
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from typing import Dict, Any

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables (config.py does this, but ensure it's loaded)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.api.resume_intake.logic import structure_resume_data, convert_json_to_text
from app.services.resume_intake.resume_parser import ResumeParser


def print_section(title: str, char: str = "=", width: int = 80):
    """Print a formatted section header."""
    print("\n" + char * width)
    print(f"  {title}")
    print(char * width + "\n")


def print_json_pretty(data: Dict[str, Any], title: str = "Parsed Data"):
    """Print JSON data in a formatted way."""
    print_section(title)
    print(json.dumps(data, indent=2, ensure_ascii=False))


def print_field_summary(data: Dict[str, Any]):
    """Print a summary of extracted fields."""
    print_section("Field Summary")
    
    # Basic Information
    basic = data.get('basic_information', {})
    print("📋 BASIC INFORMATION:")
    print(f"  First Name: {basic.get('first_name') or 'N/A'}")
    print(f"  Last Name: {basic.get('last_name') or 'N/A'}")
    print(f"  Email: {basic.get('email') or 'N/A'}")
    print(f"  Mobile Phone: {basic.get('mobile_phone') or 'N/A'}")
    print(f"  Birth Date: {basic.get('birth_date') or 'N/A'}")
    print()
    
    # Location Information
    location = data.get('location_information', {})
    print("📍 LOCATION INFORMATION:")
    print(f"  Address: {location.get('address') or 'N/A'}")
    print(f"  City: {location.get('city') or 'N/A'}")
    print(f"  Country: {location.get('country') or 'N/A'}")
    print(f"  Zipcode: {location.get('zipcode') or 'N/A'}")
    print()
    
    # Skills & Expertise
    skills = data.get('skills_expertise', {})
    print("💼 SKILLS & EXPERTISE:")
    print(f"  Total Experience Years: {skills.get('total_experience_years') or 'N/A'}")
    tech_skills = skills.get('technical_skills', [])
    print(f"  Technical Skills ({len(tech_skills)}): {', '.join(tech_skills) if tech_skills else 'N/A'}")
    soft_skills = skills.get('soft_skills', [])
    print(f"  Soft Skills ({len(soft_skills)}): {', '.join(soft_skills) if soft_skills else 'N/A'}")
    languages = skills.get('languages', [])
    print(f"  Languages ({len(languages)}): {', '.join(languages) if languages else 'N/A'}")
    print()
    
    # Professional Summary
    summary = data.get('professional_summary')
    print("📝 PROFESSIONAL SUMMARY:")
    if summary:
        # Truncate if too long
        summary_display = summary[:200] + "..." if len(summary) > 200 else summary
        print(f"  {summary_display}")
    else:
        print("  N/A")
    print()
    
    # Education
    education = data.get('education', [])
    print(f"🎓 EDUCATION ({len(education)} entries):")
    for i, edu in enumerate(education, 1):
        print(f"  {i}. {edu.get('degree') or 'N/A'} in {edu.get('field_of_study') or 'N/A'}")
        print(f"     School: {edu.get('school') or 'N/A'}, Year: {edu.get('year') or 'N/A'}, GPA: {edu.get('gpa') or 'N/A'}")
    if not education:
        print("  N/A")
    print()
    
    # Work Experience
    work_exp = data.get('work_experience', [])
    print(f"💼 WORK EXPERIENCE ({len(work_exp)} entries):")
    for i, exp in enumerate(work_exp, 1):
        print(f"  {i}. {exp.get('job_title') or 'N/A'} at {exp.get('company') or 'N/A'}")
        start = exp.get('start_date') or 'N/A'
        end = exp.get('end_date') or ('Present' if exp.get('currently_working') else 'N/A')
        print(f"     Duration: {start} to {end}")
        print(f"     Location: {exp.get('location') or 'N/A'}")
        desc = exp.get('job_description', '')
        if desc:
            desc_display = desc[:100] + "..." if len(desc) > 100 else desc
            print(f"     Description: {desc_display}")
    if not work_exp:
        print("  N/A")
    print()
    
    # Certifications
    certs = data.get('certifications', [])
    print(f"🏆 CERTIFICATIONS ({len(certs)} entries):")
    for i, cert in enumerate(certs, 1):
        print(f"  {i}. {cert.get('name') or 'N/A'}")
        print(f"     Organization: {cert.get('issuing_organization') or 'N/A'}")
        print(f"     Issue Date: {cert.get('issue_date') or 'N/A'}, Expiry: {cert.get('expiry_date') or 'N/A'}")
    if not certs:
        print("  N/A")
    print()
    
    # Projects
    projects = data.get('projects', [])
    print(f"🚀 PROJECTS ({len(projects)} entries):")
    for i, proj in enumerate(projects, 1):
        print(f"  {i}. {proj.get('name') or 'N/A'}")
        desc = proj.get('description', '')
        if desc:
            desc_display = desc[:100] + "..." if len(desc) > 100 else desc
            print(f"     Description: {desc_display}")
        tech = proj.get('technologies_used', [])
        if tech:
            print(f"     Technologies: {', '.join(tech)}")
    if not projects:
        print("  N/A")
    print()
    
    # Achievements
    achievements = data.get('achievements', [])
    print(f"⭐ ACHIEVEMENTS ({len(achievements)} entries):")
    for i, achievement in enumerate(achievements, 1):
        print(f"  {i}. {achievement}")
    if not achievements:
        print("  N/A")
    print()


async def test_resume_parsing(file_path: str):
    """
    Test resume parsing without database operations.
    
    Args:
        file_path: Path to the resume file
    """
    try:
        print_section("RESUME PARSING TEST", "=", 80)
        print(f"File: {file_path}")
        print(f"File exists: {os.path.exists(file_path)}")
        
        if not os.path.exists(file_path):
            print(f"❌ Error: File not found at {file_path}")
            return
        
        # Step 1: Parse resume file
        print_section("Step 1: Extracting Text from Resume", "-", 80)
        parser = ResumeParser()
        try:
            text = parser.parse(file_path)
            print(f"✅ Text extracted successfully")
            print(f"   Text length: {len(text)} characters")
            print(f"   Preview (first 500 chars):")
            print(f"   {'-' * 78}")
            print(f"   {text[:500]}...")
            print(f"   {'-' * 78}")
        except Exception as e:
            print(f"❌ Error extracting text: {str(e)}")
            return
        
        # Step 2: Structure data using GPT-4o
        print_section("Step 2: Structuring Data with GPT-4o", "-", 80)
        print("⏳ Calling OpenAI API... (this may take a few seconds)")
        try:
            structured_data = await structure_resume_data(text)
            print("✅ Data structured successfully")
        except ValueError as e:
            print(f"❌ Configuration Error: {str(e)}")
            print("   Make sure OPENAI_API_KEY is set in your .env file")
            return
        except Exception as e:
            print(f"❌ Error structuring data: {str(e)}")
            import traceback
            traceback.print_exc()
            return
        
        # Step 3: Display results
        print_section("Step 3: Parsed Results", "-", 80)
        
        # Print field summary
        print_field_summary(structured_data)
        
        # Print full JSON
        print_json_pretty(structured_data, "Complete JSON Output")
        
        # Step 4: Show text representation (for embeddings)
        print_section("Step 4: Text Representation (for Embeddings)", "-", 80)
        resume_text = convert_json_to_text(structured_data)
        print(resume_text)
        
        # Step 5: Save to file (optional)
        output_file = f"{Path(file_path).stem}_parsed.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(structured_data, f, indent=2, ensure_ascii=False)
        print_section("Step 5: Output Saved", "-", 80)
        print(f"✅ Parsed data saved to: {output_file}")
        
        print_section("TEST COMPLETED SUCCESSFULLY", "=", 80)
        
    except Exception as e:
        print_section("ERROR", "=", 80)
        print(f"❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python test_resume_parser.py <resume_file_path>")
        print("\nExample:")
        print("  python test_resume_parser.py resume.pdf")
        print("  python test_resume_parser.py resume.docx")
        print("  python test_resume_parser.py resume.txt")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"❌ Error: File not found: {file_path}")
        sys.exit(1)
    
    # Check if it's a valid file type
    allowed_extensions = {'.pdf', '.docx', '.doc', '.txt'}
    file_extension = Path(file_path).suffix.lower()
    if file_extension not in allowed_extensions:
        print(f"❌ Error: Unsupported file type: {file_extension}")
        print(f"   Supported types: {', '.join(allowed_extensions)}")
        sys.exit(1)
    
    # Run the async test
    asyncio.run(test_resume_parsing(file_path))


if __name__ == "__main__":
    main()

