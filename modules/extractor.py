import fitz  # PyMuPDF
import sys
import os
from contextlib import contextmanager

@contextmanager
def suppress_stderr():
    """Temporarily suppress stderr to hide MuPDF warnings."""
    try:
        # Save original stderr
        old_stderr = sys.stderr
        # Redirect stderr to devnull
        sys.stderr = open(os.devnull, 'w')
        yield
    finally:
        # Restore stderr
        sys.stderr.close()
        sys.stderr = old_stderr

def extract_text_from_pdf(uploaded_file, timeout_seconds=30):
    """Extract plain text from a PDF file stream with timeout.
    
    Args:
        uploaded_file: File-like object containing PDF data
        timeout_seconds: Maximum time to spend extracting (default 30s)
    
    Returns:
        str: Extracted text, or empty string on failure
    """
    text = ""
    try:
        # Suppress MuPDF error messages (e.g., "cannot find XObject resource")
        with suppress_stderr():
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
    
    return text.strip()
