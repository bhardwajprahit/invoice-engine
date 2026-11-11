
from pathlib import Path

from batch_processor import find_documents, process_document


files = find_documents(Path("samples"))

if not files:
    files = find_documents(Path("uploads"))

print(f"Documents found: {len(files)}")

if not files:
    print("No PDF or image found in samples or uploads.")
    raise SystemExit

file_path = next(
    (f for f in files if f.name == "invoice_test2.png"),
    None,
)

if file_path is None:
    print("invoice_test2.png not found")
    raise SystemExit

print(f"\nTesting file: {file_path.name}")
print("Processing invoice without saving it to the database...")

invoice = process_document(file_path)

fields = [
    "invoice_number",
    "invoice_date",
    "seller_name",
    "seller_address",
    "seller_gstin",
    "buyer_name",
    "buyer_address",
    "buyer_gstin",
    "subtotal",
    "taxable_amount",
    "tax_amount",
    "cgst",
    "sgst",
    "igst",
    "total_amount",
    "status",
]

print("\n--- EXTRACTION RESULTS ---")

for field in fields:
    print(f"{field}: {invoice.get(field)}")

print("\n--- LINE ITEMS ---")

for item in invoice.get("line_items", []):
    print(item)

print("\nTest complete. No database save was requested.")
