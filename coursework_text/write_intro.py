import os  
from docx import Document  
from docx.shared import Pt, Cm  
from docx.enum.text import WD_ALIGN_PARAGRAPH  
doc = Document() 

docx_path = r"C:\Users\Danila\OneDrive\Desktop\agent\coursework_intro.docx"

for section in doc.sections:
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(1.5)

style = doc.styles["Normal"]
font = style.font
font.name = "Times New Roman"
font.size = Pt(14)
style.paragraph_format.line_spacing = 1.5
style.paragraph_format.space_after = Pt(0)
style.paragraph_format.space_before = Pt(0)
