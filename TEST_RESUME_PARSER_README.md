# Resume Parser Test Script

This standalone test script allows you to test resume parsing without requiring database access.

## Prerequisites

1. **Python Environment**: Make sure you have all dependencies installed:
   ```bash
   pip install -r requirements.txt
   ```

2. **OpenAI API Key**: Set your OpenAI API key in `.env` file:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

## Usage

### Basic Usage

```bash
python test_resume_parser.py <resume_file_path>
```

### Examples

```bash
# Test with PDF resume
python test_resume_parser.py resume.pdf

# Test with DOCX resume
python test_resume_parser.py resume.docx

# Test with TXT resume
python test_resume_parser.py resume.txt
```

## Supported File Types

- `.pdf` - PDF files
- `.docx` - Microsoft Word documents
- `.doc` - Legacy Word documents
- `.txt` - Plain text files

## What the Script Does

1. **Extracts Text**: Parses the resume file and extracts raw text
2. **Structures Data**: Uses GPT-4o to structure the text into the canonical JSON schema
3. **Displays Results**: Shows:
   - Field summary (human-readable format)
   - Complete JSON output (formatted)
   - Text representation (for embeddings)
4. **Saves Output**: Saves the parsed JSON to `<filename>_parsed.json`

## Output

The script will display:

1. **Field Summary**: A human-readable summary of all extracted fields
2. **Complete JSON**: The full parsed JSON matching the canonical schema
3. **Text Representation**: The text format used for generating embeddings
4. **Saved File**: A JSON file with the parsed data

## Example Output Structure

The parsed JSON will match this canonical schema:

```json
{
  "basic_information": {
    "first_name": "...",
    "last_name": "...",
    "email": "...",
    "mobile_phone": "...",
    ...
  },
  "location_information": {
    "address": "...",
    "city": "...",
    "country": "...",
    "zipcode": "..."
  },
  "skills_expertise": {
    "total_experience_years": 5,
    "technical_skills": [...],
    "soft_skills": [...],
    "languages": [...]
  },
  "professional_summary": "...",
  "education": [...],
  "certifications": [...],
  "work_experience": [...],
  "projects": [...],
  "achievements": [...]
}
```

## Troubleshooting

### Error: "OpenAI API key not configured"
- Make sure `OPENAI_API_KEY` is set in your `.env` file
- Check that the `.env` file is in the project root directory

### Error: "File not found"
- Check that the file path is correct
- Use absolute path if relative path doesn't work

### Error: "Unsupported file type"
- Make sure the file has one of these extensions: `.pdf`, `.docx`, `.doc`, `.txt`

### Error: "Module not found"
- Make sure you're running from the project root directory
- Install dependencies: `pip install -r requirements.txt`

## Notes

- This script does **NOT** connect to the database
- This script does **NOT** generate embeddings or store in Qdrant
- This script is for **testing the parsing logic only**
- The output JSON file can be used to verify the schema matches your expectations

