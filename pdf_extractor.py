import os
import PyPDF2
from pdfminer.high_level import extract_text as pdfminer_extract
from pdfminer.layout import LAParams


def extract_text_from_pdf(pdf_path):
    """
    Extract text from a PDF file and save it as a transcript text file.
    
    Args:
        pdf_path (str): Full path to the PDF file
        
    Returns:
        str: Path to the saved transcript text file, or None if error
    """
    TRANSCRIPT_DIR = os.path.join("data", "transcripts")
    
    # Create transcript directory if it doesn't exist
    if not os.path.exists(TRANSCRIPT_DIR):
        os.makedirs(TRANSCRIPT_DIR)
    
    try:
        # Check if file exists
        if not os.path.exists(pdf_path):
            print(f"Error: PDF file not found: {pdf_path}")
            return None
        
        print(f"Extracting text from PDF: {pdf_path}...")
        
        # Try using pdfminer first (more reliable for text extraction)
        try:
            # Use pdfminer for better text extraction
            laparams = LAParams()
            text = pdfminer_extract(pdf_path, laparams=laparams)
        except Exception as e:
            print(f"pdfminer extraction failed, trying PyPDF2: {e}")
            # Fallback to PyPDF2
            text = ""
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text() + "\n"
        
        # Clean up the extracted text
        text = text.strip()
        
        if not text or len(text) < 10:
            print("Warning: Extracted text is very short or empty. PDF might be image-based or corrupted.")
            return None
        
        # Generate output filename based on input filename
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        out_file = os.path.join(TRANSCRIPT_DIR, f"{base_name}.txt")
        
        # Save transcript
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(text)
        
        print(f"Text extracted and saved to {out_file}")
        return out_file
        
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        import traceback
        traceback.print_exc()
        return None

