
from datetime import datetime


EXPECTED_FIELDS = [
    "invoice_number",
    "invoice_date",
    "portal_invoice_number",
    "portal_invoice_date",
    "currency",
    "seller_name",
    "seller_address",
    "seller_gstin",
    "buyer_name",
    "buyer_address",
    "buyer_gstin",
    "subtotal",
    "taxable_amount",
    "tax_rate",
    "tax_amount",
    "cgst",
    "sgst",
    "igst",
    "total_amount",
    "line_items",
]


NUMERIC_INVOICE_FIELDS = {
    "subtotal",
    "taxable_amount",
    "tax_rate",
    "tax_amount",
    "cgst",
    "sgst",
    "igst",
    "total_amount",
}


NUMERIC_ITEM_FIELDS = {
    "quantity",
    "unit_price",
    "amount",
    "free_quantity",
    "gross_amount",
    "discount",
    "discount_percent",
    "taxable_amount",
    "gst_rate",
    "cgst",
    "sgst",
    "igst",
    "cess",
}


def normalize_number(value):
    """Convert common numeric representations to floats safely."""

    if value is None or value == "":
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        value = value.strip()
        value = value.replace(",", "")
        value = value.replace("₹", "")
        value = value.replace("Rs.", "")
        value = value.replace("Rs", "")
        value = value.replace("$", "")
        value = value.replace("€", "")
        value = value.replace("£", "")
        value = value.strip()

        try:
            return float(value)
        except ValueError:
            return None

    return None


def normalize_currency(value):
    """Standardize common currency representations."""

    if value is None:
        return None

    value = str(value).strip().upper()

    currency_map = {
        "RS": "INR",
        "RS.": "INR",
        "₹": "INR",
        "INR": "INR",
        "RUPEE": "INR",
        "RUPEES": "INR",
        "$": "USD",
        "US$": "USD",
        "USD": "USD",
        "A$": "AUD",
        "AUD": "AUD",
        "€": "EUR",
        "EUR": "EUR",
        "£": "GBP",
        "GBP": "GBP",
    }

    return currency_map.get(value, value)


def normalize_gstin(value):
    """Normalize GSTIN formatting without inventing a value."""

    if value is None:
        return None

    value = str(value).strip().upper()
    value = "".join(value.split())

    return value or None


def normalize_text(value):
    """Normalize optional text while preserving its actual content."""

    if value is None:
        return None

    value = str(value).strip()
    return value or None


def normalize_date(value):
    """Convert recognized invoice dates to YYYY-MM-DD."""

    if value is None or value == "":
        return None

    value = str(value).strip()

    date_formats = [
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
    ]

    for date_format in date_formats:
        try:
            parsed_date = datetime.strptime(value, date_format)
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Preserve an unrecognized date instead of guessing its meaning.
    return value


def normalize_line_items(line_items):
    """Normalize line items while retaining product and tax details."""

    if not isinstance(line_items, list):
        return []

    normalized_items = []

    for item in line_items:
        if not isinstance(item, dict):
            continue

        # Accept alternative field names from older or different extractors.
        aliases = {
            "product_name": ("product_name", "item_name", "name"),
            "model": ("model", "model_number", "model_no"),
            "sku": ("sku", "item_code", "product_code"),
            "hsn_sac": ("hsn_sac", "hsn_code", "sac_code", "hsn", "sac"),
            "uom": ("uom", "unit", "unit_of_measure"),
            "gst_rate": ("gst_rate", "tax_rate"),
            "igst": ("igst", "item_igst"),
        }

        normalized_item = {}

        # Keep the original four core fields supported by the existing app.
        normalized_item["description"] = normalize_text(
            item.get("description")
        )

        for field in (
            "product_name",
            "model",
            "sku",
            "hsn_sac",
            "uom",
        ):
            value = None

            for alias in aliases[field]:
                if item.get(alias) is not None:
                    value = item.get(alias)
                    break

            normalized_item[field] = normalize_text(value)

        # Preserve every numeric line-item field supported by the database.
        for field in NUMERIC_ITEM_FIELDS:
            value = None

            for alias in aliases.get(field, (field,)):
                if item.get(alias) is not None:
                    value = item.get(alias)
                    break

            normalized_item[field] = normalize_number(value)

        normalized_items.append(normalized_item)

    return normalized_items


def normalize_invoice(invoice):
    """Normalize invoice fields without discarding supported data."""

    if not isinstance(invoice, dict):
        return {}

    normalized = {}

    # Support common alternate names from extraction systems.
    aliases = {
        "seller_name": ("seller_name", "vendor_name", "supplier_name"),
        "seller_address": ("seller_address", "vendor_address", "supplier_address"),
        "seller_gstin": ("seller_gstin", "vendor_gstin", "supplier_gstin"),
        "buyer_name": ("buyer_name", "customer_name", "bill_to_name"),
        "buyer_address": ("buyer_address", "customer_address", "bill_to_address"),
        "buyer_gstin": ("buyer_gstin", "customer_gstin"),
    }

    for field in EXPECTED_FIELDS:
        value = None

        for alias in aliases.get(field, (field,)):
            if invoice.get(alias) is not None:
                value = invoice.get(alias)
                break

        if field in NUMERIC_INVOICE_FIELDS:
            normalized[field] = normalize_number(value)

        elif field == "currency":
            normalized[field] = normalize_currency(value)

        elif field in {"seller_gstin", "buyer_gstin"}:
            normalized[field] = normalize_gstin(value)

        elif field in {"invoice_date", "portal_invoice_date"}:
            normalized[field] = normalize_date(value)

        elif field == "line_items":
            normalized[field] = normalize_line_items(value)

        else:
            normalized[field] = normalize_text(value)

    # Preserve validation and application metadata if supplied by a caller.
    for field in (
        "file_name",
        "status",
        "confidence",
        "review_required",
        "completeness",
        "errors",
        "warnings",
        "field_flags",
        "data_quality",
    ):
        if field in invoice:
            normalized[field] = invoice[field]

    return normalized
