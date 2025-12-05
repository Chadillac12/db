from pypdf import PdfReader

reader = PdfReader("ARINC 629 Avionics Data Bus – Comprehensive Overview.pdf")
text = ""
for page in reader.pages[:5]: # Read first 5 pages for overview
    text += page.extract_text() + "\n"

print(text)
