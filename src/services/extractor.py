import fitz  # PyMuPDF
import sys
import os
import re


def clean_cv_text(raw_text):
    """Clean extracted CV text by removing common PDF noise while preserving structure."""
    if not raw_text:
        return ""
    
    text = raw_text
    
    # Remove non-printable characters (keep newlines, tabs, spaces)
    text = re.sub(r'[^\x09\x0a\x0d\x20-\x7e\x80-\xff]', '', text)
    
    # Remove common page number patterns
    text = re.sub(r'\n\s*(?:Page|Halaman|Hal\.?)\s*\d+\s*(?:of|dari)?\s*\d*\s*\n', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'\n\s*-?\s*\d+\s*-?\s*\n', '\n', text)  # Standalone page numbers like "- 2 -"
    
    # Remove excessive decorators (repeated ===, ---, ***, ___)
    text = re.sub(r'[=]{4,}', '', text)
    text = re.sub(r'[-]{4,}', '', text)
    text = re.sub(r'[*]{4,}', '', text)
    text = re.sub(r'[_]{4,}', '', text)
    
    # Collapse 3+ blank lines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Strip trailing whitespace per line
    text = re.sub(r'[ \t]+\n', '\n', text)
    
    return text.strip()


def extract_text_from_pdf(uploaded_file, timeout_seconds=30):
    """Extract plain text from a PDF file stream with timeout.
    
    Args:
        uploaded_file: File-like object containing PDF data
        timeout_seconds: Maximum time to spend extracting (default 30s)
    
    Returns:
        str: Extracted text, or empty string on failure
    """
    text = ""
    
    # Suppress MuPDF errors by redirecting stderr at OS level
    old_stderr = os.dup(2)  # Save original stderr file descriptor
    devnull = os.open(os.devnull, os.O_WRONLY)
    
    try:
        # Redirect stderr to devnull (suppresses MuPDF warnings)
        os.dup2(devnull, 2)
        
        with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
            # Limit number of pages to prevent excessive processing
            max_pages = min(len(doc), 50)  # Process max 50 pages
            
            for page_num in range(max_pages):
                try:
                    page = doc[page_num]
                    text += page.get_text("text") + "\n"
                except Exception:
                    # Skip problematic pages
                    continue
                    
    except Exception:
        # Return whatever we managed to extract
        pass
    finally:
        # Restore original stderr
        os.dup2(old_stderr, 2)
        os.close(devnull)
        os.close(old_stderr)
    
    return clean_cv_text(text)
