

import os
import json
import time

from dotenv import load_dotenv
from mistralai.client import Mistral

load_dotenv()

MODEL_NAME = "ministral-8b-2512"
MAX_RETRIES = 3
RETRY_DELAY = 3

client = Mistral(
    api_key=os.getenv("MISTRAL_API_KEY")
)



def extract_invoice(text):
    """
    Extract invoice header, company, tax, and line-item details
    using Mistral AI. Return structured JSON.
    """

    prompt = f"""
You are a highly accurate invoice understanding and data extraction system.

Read the ENTIRE invoice, including seller details, buyer details,
invoice metadata, product tables, tax tables, totals, and footnotes.

Return ONLY valid JSON using exactly this structure:

{{
    "invoice_number": null,
    "invoice_date": null,
    "portal_invoice_number": null,
    "portal_invoice_date": null,
    "currency": null,

    "seller_name": null,
    "seller_address": null,
    "seller_gstin": null,

    "buyer_name": null,
    "buyer_address": null,
    "buyer_gstin": null,

    "subtotal": null,
    "taxable_amount": null,
    "tax_rate": null,
    "tax_amount": null,
    "cgst": null,
    "sgst": null,
    "igst": null,
    "total_amount": null,

    "line_items": []
}}

Every line item must use exactly this structure:

{{
    "description": null,
    "product_name": null,
    "model": null,
    "sku": null,
    "hsn_sac": null,
    "uom": null,

    "quantity": null,
    "free_quantity": null,
    "unit_price": null,
    "gross_amount": null,
    "discount": null,
    "discount_percent": null,
    "taxable_amount": null,

    "gst_rate": null,
    "cgst": null,
    "sgst": null,
    "igst": null,
    "cess": null,
    "amount": null
}}

GENERAL RULES:

- Extract only information supported by the invoice text.
- Never invent company names, product names, codes, quantities, rates,
  addresses, tax amounts, or other values.
- Use null for unavailable or uncertain scalar values.
- Use numbers, not numeric strings, for quantities, prices, percentages,
  and monetary amounts.
- Keep identifiers such as invoice numbers, GSTINs, SKUs, model numbers,
  and HSN/SAC codes as strings.
- Preserve invoice numbers and identifiers exactly as printed.
- Preserve meaningful product descriptions.
- Correct obvious OCR spacing problems only when the intended value is clear.
- Return no commentary or Markdown. Return only JSON.
- line_items must always be an array.

SELLER AND BUYER:

- seller_name is the supplier or seller issuing the invoice.
- seller_address is the seller's printed address.
- seller_gstin is the seller's GSTIN.
- buyer_name is the customer, purchaser, consignee, or billed-to entity,
  using the entity clearly identified as the buyer.
- buyer_address is the buyer's printed address.
- buyer_gstin is the buyer's GSTIN.
- Do not confuse seller and buyer details.
- Do not treat a shipping address as the buyer's registered address unless
  the document clearly identifies it that way.
- Do not mistake a company logo, bank, transporter, or marketplace for
  the seller or buyer.

INVOICE NUMBERS AND DATES:

- Identify the actual seller tax invoice number and date.
- If a GeM, marketplace, portal, purchase-order, order, or reference
  number is also present, keep it separate.
- Use portal_invoice_number and portal_invoice_date for clearly identified
  portal invoice details.
- Do not substitute a purchase-order number for an invoice number.
- Do not associate a date with a number unless the document supports it.
- Preserve dates as printed. Do not guess ambiguous dates.

CURRENCY:

- ₹, Rs, Rs. and INR mean INR.
- $, US$ and USD mean USD when the context supports that currency.
- €, EUR mean EUR.
- £, GBP mean GBP.
- A$, AUD mean AUD.
- Return a standardized currency code when identifiable.
- Do not assume INR solely because the invoice contains GST.

INVOICE AMOUNTS:

- subtotal: the explicitly stated subtotal, before or after tax according
  to the invoice's own label and meaning.
- taxable_amount: the explicitly stated taxable value or taxable base.
- tax_rate: the clearly applicable invoice-level tax percentage.
- tax_amount: the total tax amount when explicitly stated as a total.
- cgst: the invoice-level Central GST amount when identifiable.
- sgst: the invoice-level State GST amount when identifiable.
- igst: the invoice-level Integrated GST amount when identifiable.
- total_amount: the final invoice amount payable, preferably the explicitly
  stated final total.

Taxable value and subtotal are not necessarily interchangeable.
Do not copy one into the other without clear evidence.

TAX RULES:

- Extract CGST, SGST, IGST, VAT, cess, and other clearly identified taxes.
- Do not confuse tax rates with tax amounts.
- Do not confuse invoice-level taxes with line-item taxes.
- Do not add CGST and SGST to the total again if the printed total already
  includes them.
- If an invoice has several tax rates, do not invent a single tax_rate.
  Use null when one invoice-level rate would be misleading.
- If a tax component is absent, use null rather than assuming it is zero.
- If the invoice explicitly shows zero tax, return numeric 0.
- Do not derive a tax amount from a percentage unless the requested amount
  is explicitly calculable from a clearly identified base and the invoice
  provides sufficient evidence. Prefer printed amounts.
- Do not force totals to reconcile when discounts, freight, rounding,
  multiple tax bases, or other charges explain the difference.

LINE ITEMS:

Extract every clearly identifiable billable product, service, fee, or charge.
Preserve the original logical invoice order.

For each item:

- description: the full printed item description.
- product_name: the identifiable product or service name, separated from
  unrelated notes where possible.
- model: the explicitly printed model or model number.
- sku: the explicitly printed SKU, product code, or item code.
- hsn_sac: the printed HSN or SAC classification code.
- uom: the unit of measurement, such as PCS, NOS, KG, or SET.
- quantity: the billed quantity.
- free_quantity: a separately stated free quantity, if any.
- unit_price: the per-unit price, not the line total.
- gross_amount: the explicitly stated gross line value before discounts,
  when identifiable.
- discount: the monetary discount for this item, when identifiable.
- discount_percent: the printed discount percentage, when identifiable.
- taxable_amount: the taxable value for this specific item.
- gst_rate: the applicable tax rate for this item.
- cgst: the CGST amount for this item.
- sgst: the SGST amount for this item.
- igst: the IGST amount for this item.
- cess: the cess amount for this item.
- amount: the printed line-item amount. Prefer the clearly identified
  final line amount, and do not substitute the invoice total.

Additional line-item rules:

- Do not invent model numbers or SKUs from product descriptions.
- Keep HSN/SAC codes as strings so leading zeros are preserved.
- Do not mistake a quantity for a price or tax percentage.
- Do not treat invoice totals, tax summaries, or subtotal rows as products.
- Do not create duplicate line items from repeated OCR text.
- If a field is not available for an item, use null.
- If no billable items can be identified, return [].
- Do not calculate an item tax from the invoice-wide tax unless the item
  tax is explicitly identifiable.

FINANCIAL CONSISTENCY:

Check whether the extracted amounts make sense together, but do not alter
printed values merely to make the arithmetic work.

Do not fabricate missing amounts to force:
taxable amount + taxes = total amount,
or quantity × unit price = line amount.

If the invoice contains ambiguous or conflicting values, prefer the clearly
labelled printed amount and leave uncertain fields null.

FINAL CHECK:

- All keys in the requested structure must be present.
- All unavailable scalar values must be null.
- All numeric values must be JSON numbers, not strings.
- Identifiers and codes must be strings.
- line_items must be an array of objects.
- Return valid JSON only.

INVOICE TEXT:

{text}
"""

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.complete(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                response_format={
                    "type": "json_object"
                },
                temperature=0,
            )

            result = response.choices[0].message.content

            if not isinstance(result, str) or not result.strip():
                raise ValueError("The AI returned an empty response.")

            invoice = json.loads(result)

            if not isinstance(invoice, dict):
                raise ValueError("The AI response was not a JSON object.")

            if not isinstance(invoice.get("line_items"), list):
                raise ValueError("The AI response did not contain a line_items array.")

            return invoice

        except Exception as error:
            last_error = error

            print(
                f"AI extraction attempt "
                f"{attempt}/{MAX_RETRIES} failed: {error}"
            )

            if attempt < MAX_RETRIES:
                wait_time = RETRY_DELAY * attempt

                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)

    raise RuntimeError(
        f"AI extraction failed after {MAX_RETRIES} attempts: {last_error}"
    )
