from ai_extractor import extract_invoice
from normalizer import normalize_invoice
from validator import validate_invoice
from batch_processor import extract_text

from pathlib import Path


FILE_PATH = Path("samples/test_invoice.pdf")


text = extract_text(FILE_PATH)

ai_invoice = extract_invoice(text)

print("\nAI EXTRACTED:")
print(ai_invoice)

normalized_invoice = normalize_invoice(ai_invoice)

print("\nNORMALIZED:")
print(normalized_invoice)

validation = validate_invoice(normalized_invoice)

print("\nVALIDATION:")
print(validation)