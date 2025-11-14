import fitz  # PyMuPDF

def extract_text_from_pdf(uploaded_file):
    """Extract plain text from a PDF file stream."""
    text = ""
    try:
        with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
            for page in doc:
                text += page.get_text("text") + "\n"
    except Exception:
        text = ""
    return text.strip()
