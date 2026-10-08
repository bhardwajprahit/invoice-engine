import pymupdf
import pytesseract

from field_parser import parse_invoice


# Tell Python where Tesseract is installed
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# Open the PDF
pdf = pymupdf.open("samples/test_invoice.pdf")

# Get the first page
page = pdf[0]

# Convert PDF page to image
pix = page.get_pixmap(dpi=300)

# Convert to PIL image
image = pix.pil_image()

# OCR
text = pytesseract.image_to_string(image)

print("RAW OCR TEXT:")
print(text)

# Send OCR text to the field parser
invoice = parse_invoice(text)


# Display structured result
print("PARSED INVOICE:")
print(invoice)
