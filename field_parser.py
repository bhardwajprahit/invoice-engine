
import re


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text):
    """
    Clean common OCR formatting problems while preserving
    line structure.
    """

    if not text:
        return ""

    text = text.replace("\r", "\n")
    text = text.replace("\xa0", " ")

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def get_lines(text):
    """
    Return non-empty cleaned OCR lines.
    """

    return [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]


# ============================================================
# AMOUNT CLEANING
# ============================================================

def clean_amount(value):
    """
    Convert a monetary string into a float.
    """

    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    value = value.replace(",", "")
    value = value.replace("$", "")
    value = value.replace("₹", "")
    value = value.replace("€", "")
    value = value.replace("£", "")

    value = re.sub(
        r"\b(?:Rs|INR|USD|AUD|CAD|NZD|SGD|EUR|GBP|JPY|CNY|AED|SAR)\.?",
        "",
        value,
        flags=re.IGNORECASE
    )

    value = re.sub(r"[^\d.]", "", value)

    if not value:
        return None

    try:
        return float(value)
    except ValueError:
        return None


# ============================================================
# INVOICE NUMBER
# ============================================================

def extract_invoice_number(text):
    """
    Extract an invoice number using strong invoice labels.
    """

    patterns = [

        r"\bInvoice\s*(?:No\.?|Number|#)\s*[:\-]?\s*"
        r"([A-Z0-9][A-Z0-9\-\/]*)",

        r"\bInv\.?\s*(?:No\.?|Number|#)\s*[:\-]?\s*"
        r"([A-Z0-9][A-Z0-9\-\/]*)",

        r"\bInvoice\s+"
        r"([A-Z0-9][A-Z0-9\-\/]{2,})",
    ]

    ignored_values = {
        "DATE",
        "NUMBER",
        "NO",
        "TOTAL",
        "DUE",
        "TAX",
        "ISSUE",
        "INVOICE",
    }

    for pattern in patterns:

        for match in re.finditer(
            pattern,
            text,
            re.IGNORECASE
        ):

            value = match.group(1).strip()

            if value.upper() in ignored_values:
                continue

            if not re.search(r"\d", value):
                continue

            return value

    return None


# ============================================================
# DATE
# ============================================================

DATE_PATTERN = (
    r"\d{1,2}\s*[/\-]\s*\d{1,2}\s*[/\-]\s*\d{2,4}"
    r"|"
    r"\d{1,2}\s*[-/]\s*[A-Za-z]{3,9}\s*[-/]\s*\d{4}"
    r"|"
    r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}"
)


def extract_labeled_date(text):
    """
    Extract an invoice/issue date only when associated with
    an appropriate date label.
    """

    labels = (
        r"Invoice\s*Date"
        r"|Issue\s*Date"
        r"|Date\s*Issued"
    )

    pattern = (
        rf"(?:{labels})"
        rf"[^\n]{{0,80}}?"
        rf"({DATE_PATTERN})"
    )

    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )

    if not match:
        return None

    return re.sub(
        r"\s+",
        "",
        match.group(1)
    )


# ============================================================
# GSTIN
# ============================================================

def extract_gstin(text, buyer=False):
    """
    Extract a GSTIN when an explicit GSTIN label exists.
    """

    if buyer:

        pattern = (
            r"(?:BUYER|CONSIGNEE|CUSTOMER|BILL\s*TO)"
            r".{0,500}?"
            r"GSTIN\s*[:\-]?\s*"
            r"([0-9A-ZO]{15})"
        )

    else:

        pattern = (
            r"\bGSTIN\s*[:\-]?\s*"
            r"([0-9A-ZO]{15})"
        )

    match = re.search(
        pattern,
        text,
        re.IGNORECASE | re.DOTALL
    )

    if not match:
        return None

    return match.group(1).upper()


# ============================================================
# LABELED AMOUNT
# ============================================================

def extract_labeled_amount(text, labels):
    """
    Extract an amount from a line containing a strong label.

    The amount must occur after the label.
    """

    lines = get_lines(text)

    label_pattern = "|".join(
        re.escape(label)
        for label in labels
    )

    pattern = (
        rf"(?:{label_pattern})"
        rf".{{0,80}}?"
        rf"(?:₹|Rs\.?|INR|USD|AUD|CAD|NZD|SGD|EUR|GBP|JPY|CNY|AED|SAR|\$|€|£)?"
        rf"\s*"
        rf"(\d[\d,]*(?:\.\d{{1,2}})?)"
    )

    candidates = []

    for line in lines:

        match = re.search(
            pattern,
            line,
            re.IGNORECASE
        )

        if not match:
            continue

        value = clean_amount(match.group(1))

        if value is not None:
            candidates.append(value)

    if not candidates:
        return None

    return candidates[-1]


# ============================================================
# TAX RATE EXTRACTION
# ============================================================

def extract_tax_rates(text):
    """
    Extract all clearly labelled tax rates.

    Multiple rates are supported.
    """

    lines = get_lines(text)

    rates = []

    pattern = (
        r"\b(?:GST|IGST|CGST|SGST|VAT|Sales\s*Tax|Tax)"
        r"[^\n%]{0,40}?"
        r"(\d+(?:\.\d+)?)\s*%"
    )

    for line in lines:

        matches = re.findall(
            pattern,
            line,
            re.IGNORECASE
        )

        for match in matches:

            try:
                rate = float(match)

                if 0 <= rate <= 100:
                    rates.append(rate)

            except ValueError:
                continue

    unique_rates = []

    for rate in rates:

        if rate not in unique_rates:
            unique_rates.append(rate)

    return unique_rates


def extract_tax_rate(text):
    """
    Return a single tax rate only when exactly one unique
    tax rate exists.
    """

    rates = extract_tax_rates(text)

    if len(rates) == 1:
        return rates[0]

    return None


# ============================================================
# TAX AMOUNT EXTRACTION
# ============================================================

def extract_tax_amounts(text):
    """
    Extract tax amounts from tax-labelled lines.

    Important:
    A tax line can contain several monetary values.

    Example:

        GST 10% from $700.00 $10.00

    Here:
        $700.00 = taxable base
        $10.00 = actual tax

    Therefore the LAST monetary value is treated as
    the tax amount.
    """

    lines = get_lines(text)

    tax_amounts = []

    tax_pattern = (
        r"\b(?:GST|IGST|CGST|SGST|VAT|Sales\s*Tax)"
    )

    amount_pattern = (
        r"(?:₹|Rs\.?|INR|USD|AUD|CAD|NZD|SGD|EUR|GBP|JPY|CNY|AED|SAR|\$|€|£)?"
        r"\s*"
        r"\d[\d,]*(?:\.\d{1,2})?"
    )

    for line in lines:

        if not re.search(
            tax_pattern,
            line,
            re.IGNORECASE
        ):
            continue

        amounts = re.findall(
            amount_pattern,
            line,
            re.IGNORECASE
        )

        cleaned_amounts = []

        for amount in amounts:

            value = clean_amount(amount)

            if value is not None:
                cleaned_amounts.append(value)

        if not cleaned_amounts:
            continue

        # Remove percentages from monetary candidates.
        rate_matches = re.findall(
            r"(\d+(?:\.\d+)?)\s*%",
            line
        )

        rates = []

        for rate in rate_matches:

            try:
                rates.append(float(rate))
            except ValueError:
                pass

        filtered_amounts = [
            value
            for value in cleaned_amounts
            if value not in rates
        ]

        if not filtered_amounts:
            continue

        # The last monetary value on a tax line is the
        # actual tax amount.
        tax_amounts.append(
            filtered_amounts[-1]
        )

    return tax_amounts


def extract_tax_amount(text):
    """
    Return the combined tax amount from all tax lines.
    """

    amounts = extract_tax_amounts(text)

    if not amounts:
        return None

    return round(sum(amounts), 2)


# ============================================================
# CURRENCY
# ============================================================

def detect_currency(text):
    """
    Detect currency using explicit currency identifiers.

    Currency codes are preferred over symbols because
    symbols such as '$' can represent multiple currencies.
    """

    upper_text = text.upper()

    # Strong currency codes first.
    indicators = [
        ("INR", ["INR"]),
        ("USD", ["USD"]),
        ("AUD", ["AUD"]),
        ("CAD", ["CAD"]),
        ("NZD", ["NZD"]),
        ("SGD", ["SGD"]),
        ("EUR", ["EUR"]),
        ("GBP", ["GBP"]),
        ("JPY", ["JPY"]),
        ("CNY", ["CNY", "RMB"]),
        ("AED", ["AED"]),
        ("SAR", ["SAR"]),
    ]

    for currency, values in indicators:

        for value in values:

            if value in upper_text:
                return currency

    # Symbols are weaker evidence.
    #
    # '$' is deliberately treated as USD only when no
    # stronger currency identifier exists.
    if "€" in text:
        return "EUR"

    if "£" in text:
        return "GBP"

    if "₹" in text:
        return "INR"

    if re.search(r"\bRS\.?\b", upper_text):
        return "INR"

    if "$" in text:
        return "USD"

    return "UNKNOWN"


# ============================================================
# MAIN PARSER
# ============================================================

def parse_invoice(text):
    """
    Convert OCR text into structured invoice data.

    This parser is concept-based and does not contain
    company-specific invoice logic.
    """

    invoice = {}

    text = clean_text(text)

    # --------------------------------------------------------
    # Invoice number
    # --------------------------------------------------------

    invoice_number = extract_invoice_number(text)

    if invoice_number:
        invoice["invoice_number"] = invoice_number

    # --------------------------------------------------------
    # Invoice date
    # --------------------------------------------------------

    invoice_date = extract_labeled_date(text)

    if invoice_date:
        invoice["invoice_date"] = invoice_date

    # --------------------------------------------------------
    # Currency
    # --------------------------------------------------------

    invoice["currency"] = detect_currency(text)

    # --------------------------------------------------------
    # Seller GSTIN
    # --------------------------------------------------------

    seller_gstin = extract_gstin(
        text,
        buyer=False
    )

    if seller_gstin:
        invoice["seller_gstin"] = seller_gstin

    # --------------------------------------------------------
    # Buyer GSTIN
    # --------------------------------------------------------

    buyer_gstin = extract_gstin(
        text,
        buyer=True
    )

    if buyer_gstin:
        invoice["buyer_gstin"] = buyer_gstin

    # --------------------------------------------------------
    # Subtotal
    # --------------------------------------------------------

    subtotal = extract_labeled_amount(
        text,
        [
            "Subtotal",
            "Sub Total",
            "Net Amount",
            "Net Total",
        ]
    )

    if subtotal is not None:
        invoice["subtotal"] = subtotal

    # --------------------------------------------------------
    # Taxable amount
    # --------------------------------------------------------

    taxable_amount = extract_labeled_amount(
        text,
        [
            "Taxable Amount",
            "Taxable Value",
            "Taxable",
        ]
    )

    if taxable_amount is not None:
        invoice["taxable_amount"] = taxable_amount

    # --------------------------------------------------------
    # Tax rate
    # --------------------------------------------------------

    tax_rate = extract_tax_rate(text)

    if tax_rate is not None:
        invoice["tax_rate"] = tax_rate

    # --------------------------------------------------------
    # Tax amount
    # --------------------------------------------------------

    tax_amount = extract_tax_amount(text)

    if tax_amount is not None:
        invoice["tax_amount"] = tax_amount

    # --------------------------------------------------------
    # IGST
    # --------------------------------------------------------

    if re.search(
        r"\bIGST\b",
        text,
        re.IGNORECASE
    ):

        igst = extract_labeled_amount(
            text,
            ["IGST"]
        )

        if igst is not None:
            invoice["igst"] = igst

    # --------------------------------------------------------
    # Total amount
    # --------------------------------------------------------

    total_amount = extract_labeled_amount(
        text,
        [
            "Total Due",
            "Total Payable",
            "Amount Due",
            "Grand Total",
            "Total Amount",
            "Total Price Inclusive",
        ]
    )

    if total_amount is None:

        total_amount = extract_labeled_amount(
            text,
            ["Total"]
        )

    if total_amount is not None:
        invoice["total_amount"] = total_amount

    return invoice
