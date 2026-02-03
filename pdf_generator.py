import os
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def generate_pdf(summary_text, output_path, title="Meeting Summary"):
    """
    Generate a PDF file from summary text.
    
    Args:
        summary_text (str): The summary text to include in PDF
        output_path (str): Path where PDF should be saved
        title (str): Title for the PDF document
        
    Returns:
        str: Path to generated PDF, or None if error
    """
    try:
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Create PDF document
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        
        # Container for PDF elements
        story = []
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Define custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor='#1a1a1a',
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor='#333333',
            spaceAfter=12,
            spaceBefore=20,
            fontName='Helvetica-Bold'
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=12,
            textColor='#000000',
            spaceAfter=12,
            leading=18,
            alignment=TA_LEFT,
            fontName='Helvetica'
        )
        
        # Add title
        title_para = Paragraph(title, title_style)
        story.append(title_para)
        story.append(Spacer(1, 0.3*inch))
        
        # Add summary content
        # Split summary into paragraphs for better formatting
        paragraphs = summary_text.split('\n\n')
        
        for para in paragraphs:
            if para.strip():
                # Clean up the paragraph
                para = para.strip()
                # Replace multiple spaces with single space
                para = ' '.join(para.split())
                # Escape HTML special characters for ReportLab
                para = para.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                
                story.append(Paragraph(para, body_style))
                story.append(Spacer(1, 0.2*inch))
        
        # Build PDF
        doc.build(story)
        
        print(f"PDF saved to {output_path}")
        return output_path
        
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return None

