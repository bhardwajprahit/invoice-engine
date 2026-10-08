from datetime import datetime


EXPECTED_FIELDS = [
    "invoice_number",
    "invoice_date",
    "portal_invoice_number",
    "portal_invoice_date",
    "currency",
    "seller_gstin",
    "buyer_gstin",
    "subtotal",
    "taxable_amount",
    "tax_rate",
    "tax_amount",
    "igst",
    "total_amount",
    "line_items",
]


def normalize_number(value):
    """
    Convert a value into a float when possible.
    """

    if value is None or value == "":
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):

        value = value.strip()

        value = value.replace(",", "")
        value = value.replace("₹", "")
        value = value.replace("$", "")
        value = value.replace("€", "")
        value = value.replace("£", "")

        try:
            return float(value)

        except ValueError:
            return None

    return None


def normalize_currency(value):
    """
    Convert common currency representations
    into standard currency codes.
    """

    if value is None:
        return None

    value = str(value).strip().upper()

    currency_map = {
        "RS": "INR",
        "RS.": "INR",
        "₹": "INR",
        "INR": "INR",

        "USD": "USD",
        "$": "USD",
        "US$": "USD",

        "AUD": "AUD",
        "A$": "AUD",

        "EUR": "EUR",
        "€": "EUR",

        "GBP": "GBP",
        "£": "GBP",
    }

    return currency_map.get(
        value,
        value
    )


def normalize_gstin(value):
    """
    Normalize GSTIN formatting.
    """

    if value is None:
        return None

    value = str(value).strip().upper()

    value = value.replace(
        " ",
        ""
    )

    return value


def normalize_date(value):
    """
    Convert common invoice date formats
    into YYYY-MM-DD.
    """

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
    ]

    for date_format in date_formats:

        try:

            date = datetime.strptime(
                value,
                date_format
            )

            return date.strftime(
                "%Y-%m-%d"
            )

        except ValueError:

            continue

    return value


def normalize_line_items(line_items):
    """
    Normalize invoice line items.

    Each line item contains:

        description
        quantity
        unit_price
        amount
    """

    if not isinstance(
        line_items,
        list
    ):
        return []

    normalized_items = []

    for item in line_items:

        if not isinstance(
            item,
            dict
        ):
            continue

        normalized_item = {
            "description": None,
            "quantity": None,
            "unit_price": None,
            "amount": None
        }

        # Description
        description = item.get(
            "description"
        )

        if description is not None:

            normalized_item["description"] = (
                str(description).strip()
            )

        # Quantity
        normalized_item["quantity"] = (
            normalize_number(
                item.get("quantity")
            )
        )

        # Unit price
        normalized_item["unit_price"] = (
            normalize_number(
                item.get("unit_price")
            )
        )

        # Amount
        normalized_item["amount"] = (
            normalize_number(
                item.get("amount")
            )
        )

        normalized_items.append(
            normalized_item
        )

    return normalized_items


def normalize_invoice(invoice):
    """
    Normalize the complete AI invoice output.
    """

    normalized = {}

    for field in EXPECTED_FIELDS:

        value = invoice.get(
            field
        )

        # ----------------------------------------------------
        # NORMAL NUMERIC FIELDS
        # ----------------------------------------------------

        if field in {
            "subtotal",
            "taxable_amount",
            "tax_rate",
            "tax_amount",
            "igst",
            "total_amount"
        }:

            normalized[field] = (
                normalize_number(
                    value
                )
            )

        # ----------------------------------------------------
        # CURRENCY
        # ----------------------------------------------------

        elif field == "currency":

            normalized[field] = (
                normalize_currency(
                    value
                )
            )

        # ----------------------------------------------------
        # GSTIN
        # ----------------------------------------------------

        elif field in {
            "seller_gstin",
            "buyer_gstin"
        }:

            normalized[field] = (
                normalize_gstin(
                    value
                )
            )

        # ----------------------------------------------------
        # DATES
        # ----------------------------------------------------

        elif field in {
            "invoice_date",
            "portal_invoice_date"
        }:

            normalized[field] = (
                normalize_date(
                    value
                )
            )

        # ----------------------------------------------------
        # LINE ITEMS
        # ----------------------------------------------------

        elif field == "line_items":

            normalized[field] = (
                normalize_line_items(
                    value
                )
            )

        # ----------------------------------------------------
        # TEXT FIELDS
        # ----------------------------------------------------

        else:

            if value is None:

                normalized[field] = None

            else:

                normalized[field] = (
                    str(value).strip()
                )

    return normalized