"""Resume parser service for extracting text from resume files."""

import PyPDF2
import docx
import os


class ResumeParser:
    """Extracts text content from resume files (PDF, DOCX, TXT)."""
    
    def parse(self, file_path: str) -> str:
        """
        Extract text content from resume file.
        
        Args:
            file_path: Path to the resume file
            
        Returns:
            Extracted text content
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is unsupported
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found at {file_path}")
        
        file_extension = os.path.splitext(file_path)[1].lower()
        
        # Extract text based on file type
        if file_extension == '.pdf':
            return self._parse_pdf(file_path)
        elif file_extension in ['.docx', '.doc']:
            return self._parse_docx(file_path)
        elif file_extension == '.txt':
            return self._parse_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
    
    def _parse_pdf(self, file_path: str) -> str:
        """Parse PDF file and extract text."""
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text()
        return text
    
    def _parse_docx(self, file_path: str) -> str:
        """Parse DOCX file and extract text."""
        doc = docx.Document(file_path)
        return "\n".join([paragraph.text for paragraph in doc.paragraphs])
    
    def _parse_txt(self, file_path: str) -> str:
        """Parse TXT file and extract text."""
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()

