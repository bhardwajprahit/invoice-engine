import os
import json
import time

from mistralai.client import Mistral


MODEL_NAME = "ministral-8b-2512"

MAX_RETRIES = 3

RETRY_DELAY = 3


client = Mistral(
    api_key=os.getenv(
        "MISTRAL_API_KEY"
    )
)


def extract_invoice(text):
    """
    Use the AI model to understand an invoice
    and extract structured invoice data.
    """

    prompt = f"""
You are a highly accurate invoice understanding and data extraction system.

Your job is to understand the ENTIRE invoice, not just find numbers.

Extract the invoice information below and return ONLY valid JSON.

Use exactly this structure:

{{
    "invoice_number": null,
    "invoice_date": null,
    "portal_invoice_number": null,
    "portal_invoice_date": null,
    "currency": null,
    "seller_gstin": null,
    "buyer_gstin": null,
    "subtotal": null,
    "taxable_amount": null,
    "tax_rate": null,
    "tax_amount": null,
    "igst": null,
    "total_amount": null,
    "line_items": []
}}

Each line item must use exactly this structure:

{{
    "description": null,
    "quantity": null,
    "unit_price": null,
    "amount": null
}}

GENERAL RULES:

- If a field is not clearly present, use null.
- Never invent information.
- Numbers must be numbers, not strings.
- Preserve invoice numbers exactly as they appear.
- Preserve dates exactly as they appear.
- Do not confuse labels, amounts, percentages, dates, or invoice numbers.
- Use the surrounding context of a value to determine what it represents.
- OCR may contain spelling mistakes, broken words, misplaced text, or formatting problems.
- Use the meaning and structure of the entire document to interpret OCR.
- Do not blindly trust OCR order.
- Return no explanation.
- Return only JSON.

INVOICE NUMBER AND DATE:

- Identify the actual invoice number and its corresponding invoice date.
- If there is a marketplace, portal, order, reference, or secondary number, do not automatically treat it as the main invoice number.
- If the document contains both seller/tax invoice information and portal invoice information, keep them separate.
- A date must only be assigned to an invoice number when the document clearly associates that date with that number.
- Never create a date-number pairing just because values appear nearby.

CURRENCY:

- ₹, Rs, Rs. -> INR
- $, USD -> USD
- €, EUR -> EUR
- £, GBP -> GBP
- A$, AUD -> AUD

If currency is clearly shown, return the standardized currency code.

AMOUNTS:

Understand the complete financial structure of the invoice.

Possible fields:

- subtotal
- taxable_amount
- tax_rate
- tax_amount
- igst
- total_amount

Do not assume every invoice uses the same structure.

SUBTOTAL:

- Extract a clearly stated subtotal.
- Do not confuse subtotal with taxable amount.

TAXABLE AMOUNT:

- Extract only an explicitly identified taxable amount.
- If it is not clearly present, use null.
- Do not invent it from subtotal.

TAX:

- tax_rate is the percentage.
- tax_amount is the monetary tax amount.
- Do not confuse percentages with monetary values.

MULTIPLE TAXES:

Invoices may contain:

- CGST
- SGST
- IGST
- GST
- VAT
- multiple tax rates
- taxes calculated on different bases

Understand the complete tax structure.

TOTAL:

- total_amount must be the final amount payable.
- Prefer the explicitly stated invoice total.

FINANCIAL CONSISTENCY:

Before returning JSON, mentally check relationships between:

subtotal
taxable_amount
tax_rate
tax_amount
total_amount

But do not force mathematical relationships when the invoice contains discounts, shipping, fees, multiple tax rates, rounding, or other structures.

If something cannot be determined reliably, return null.

LINE ITEMS:

Extract every clearly identifiable product, service, fee, or other billable item.

Each line item must contain:

- description
- quantity
- unit_price
- amount

Rules:

- Extract ALL clearly identifiable billable line items.
- Preserve their logical invoice order.
- Do not create fake line items.
- Do not treat tax, subtotal, discounts, shipping totals, or invoice totals as line items.
- Use null when a line-item field is unavailable.
- If there are no identifiable line items, return [].

GEМ / PORTAL INVOICES:

Some invoices may contain:

- GeM invoice number
- seller tax invoice number
- order number
- order date
- portal invoice date
- seller tax invoice date

Do not confuse these.

If the document clearly identifies both seller tax invoice information and portal invoice information, store them separately.

FINAL REQUIREMENTS:

- Return ONLY valid JSON.
- Use exactly the requested structure.
- Use null when information is unavailable.
- Never invent missing values.
- Numbers must be numeric.
- Dates and invoice numbers must be strings.
- line_items must always be an array.

INVOICE TEXT:

{text}
"""

    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1
    ):

        try:

            response = client.chat.complete(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={
                    "type": "json_object"
                },
                temperature=0
            )

            result = (
                response
                .choices[0]
                .message
                .content
            )

            return json.loads(result)

        except Exception as error:

            last_error = error

            print(
                f"AI extraction attempt "
                f"{attempt}/{MAX_RETRIES} failed: "
                f"{error}"
            )

            if attempt < MAX_RETRIES:

                wait_time = (
                    RETRY_DELAY * attempt
                )

                print(
                    f"Retrying in "
                    f"{wait_time} seconds..."
                )

                time.sleep(
                    wait_time
                )

    raise RuntimeError(
        "AI extraction failed after "
        f"{MAX_RETRIES} attempts: "
        f"{last_error}"
    )