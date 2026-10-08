# ============================================================
# INVOICE ENGINE
# UNIVERSAL INVOICE VALIDATOR
# ============================================================


def is_number(value):
    """
    Return True if value is a real number.
    """

    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
    )


def validate_invoice(invoice):
    """
    Validate an extracted and normalized invoice.

    The validator checks:

        1. Mathematical validity
        2. Line-item consistency
        3. Core-field completeness
        4. Confidence
        5. Review requirements
    """

    if not invoice:

        return {
            "status": "Invalid",
            "confidence": 0,
            "review_required": True,
            "errors": [
                "No invoice data could be extracted."
            ],
            "warnings": [],
            "field_flags": {},
            "data_quality": {
                "total_fields": 0,
                "valid_fields": 0,
                "warning_fields": 0,
                "unknown_fields": 0,
                "completeness": 0
            }
        }


    errors = []
    warnings = []
    field_flags = {}


    ignored_fields = {
        "file_name",
        "errors",
        "warnings",
        "status",
        "confidence",
        "review_required",
        "field_flags",
        "data_quality"
    }


    # ========================================================
    # FIELD STATUS
    # ========================================================

    for field, value in invoice.items():

        if field in ignored_fields:
            continue

        if value is None or value == "":
            field_flags[field] = "UNKNOWN"

        else:
            field_flags[field] = "OK"


    # ========================================================
    # IMPORTANT FIELD WEIGHTS
    # ========================================================

    important_fields = {
        "invoice_number": 30,
        "invoice_date": 20,
        "total_amount": 30,
        "currency": 10,
        "seller_gstin": 5,
        "buyer_gstin": 5
    }


    # ========================================================
    # TOTAL VALIDATION
    # ========================================================

    if (
        is_number(invoice.get("taxable_amount"))
        and is_number(invoice.get("tax_amount"))
        and is_number(invoice.get("total_amount"))
    ):

        expected_total = (
            invoice["taxable_amount"]
            + invoice["tax_amount"]
        )

        difference = abs(
            expected_total
            - invoice["total_amount"]
        )

        if difference > 1.00:

            warnings.append(
                "Taxable amount plus tax does not "
                "match the invoice total."
            )

            field_flags["total_amount"] = "WARNING"


    elif (
        is_number(invoice.get("subtotal"))
        and is_number(invoice.get("tax_amount"))
        and is_number(invoice.get("total_amount"))
    ):

        expected_total = (
            invoice["subtotal"]
            + invoice["tax_amount"]
        )

        difference = abs(
            expected_total
            - invoice["total_amount"]
        )

        if difference > 1.00:

            warnings.append(
                "Subtotal plus tax does not "
                "match the invoice total."
            )

            field_flags["total_amount"] = "WARNING"


    # ========================================================
    # TAX VALIDATION
    # ========================================================

    if (
        is_number(invoice.get("taxable_amount"))
        and is_number(invoice.get("tax_rate"))
        and is_number(invoice.get("tax_amount"))
    ):

        expected_tax = (
            invoice["taxable_amount"]
            * invoice["tax_rate"]
            / 100
        )

        difference = abs(
            expected_tax
            - invoice["tax_amount"]
        )

        if difference > 1.00:

            warnings.append(
                "Tax amount does not match "
                "the taxable amount and tax rate."
            )

            field_flags["tax_amount"] = "WARNING"


    # ========================================================
    # IGST VALIDATION
    # ========================================================

    if (
        is_number(invoice.get("taxable_amount"))
        and is_number(invoice.get("igst"))
        and is_number(invoice.get("total_amount"))
        and invoice.get("tax_amount") is None
    ):

        expected_total = (
            invoice["taxable_amount"]
            + invoice["igst"]
        )

        difference = abs(
            expected_total
            - invoice["total_amount"]
        )

        if difference > 1.00:

            warnings.append(
                "Taxable amount plus IGST does not "
                "match the invoice total."
            )

            field_flags["total_amount"] = "WARNING"


    # ========================================================
    # LINE ITEM VALIDATION
    # ========================================================

    line_items = invoice.get(
        "line_items"
    )


    if isinstance(line_items, list) and line_items:

        line_amounts = []

        for item in line_items:

            if not isinstance(item, dict):
                continue

            amount = item.get(
                "amount"
            )

            if is_number(amount):

                line_amounts.append(
                    amount
                )


        # ----------------------------------------------------
        # Line items vs subtotal
        # ----------------------------------------------------

        if (
            line_amounts
            and is_number(
                invoice.get("subtotal")
            )
        ):

            line_items_total = sum(
                line_amounts
            )

            difference = abs(
                line_items_total
                - invoice["subtotal"]
            )

            if difference > 1.00:

                warnings.append(
                    "Line item amounts do not "
                    "match the invoice subtotal."
                )

                field_flags[
                    "line_items"
                ] = "WARNING"


        # ----------------------------------------------------
        # Quantity × unit price vs amount
        # ----------------------------------------------------

        for item in line_items:

            if not isinstance(item, dict):
                continue

            quantity = item.get(
                "quantity"
            )

            unit_price = item.get(
                "unit_price"
            )

            amount = item.get(
                "amount"
            )

            if not (
                is_number(quantity)
                and is_number(unit_price)
                and is_number(amount)
            ):
                continue

            expected_amount = (
                quantity
                * unit_price
            )

            difference = abs(
                expected_amount
                - amount
            )

            if difference > 1.00:

                warnings.append(
                    "A line item quantity multiplied "
                    "by unit price does not match "
                    "its amount."
                )

                field_flags[
                    "line_items"
                ] = "WARNING"


    warnings = list(
        dict.fromkeys(
            warnings
        )
    )


    # ========================================================
    # DATA QUALITY
    # ========================================================

    total_fields = len(
        field_flags
    )

    valid_fields = sum(
        1
        for flag in field_flags.values()
        if flag == "OK"
    )

    warning_fields = sum(
        1
        for flag in field_flags.values()
        if flag == "WARNING"
    )

    unknown_fields = sum(
        1
        for flag in field_flags.values()
        if flag == "UNKNOWN"
    )


    # ========================================================
    # MEANINGFUL COMPLETENESS
    # ========================================================

    core_fields = {
        "invoice_number",
        "invoice_date",
        "total_amount",
        "currency"
    }


    core_fields_found = sum(
        1
        for field in core_fields
        if field_flags.get(field) == "OK"
    )


    completeness = round(
        (
            core_fields_found
            / len(core_fields)
        ) * 100
    )


    # ========================================================
    # STATUS
    # ========================================================

    if errors:

        status = "Invalid"

    elif warnings:

        status = "Warning"

    else:

        status = "Valid"


    # ========================================================
    # CONFIDENCE
    # ========================================================

    confidence = 0


    for field, weight in important_fields.items():

        if field_flags.get(field) == "OK":

            confidence += weight

        elif field_flags.get(field) == "WARNING":

            confidence += weight * 0.5


    confidence = round(
        confidence
    )


    if warnings:

        confidence = max(
            30,
            confidence - 20
        )


    # ========================================================
    # CRITICAL FIELDS
    # ========================================================

    critical_fields = {
        "invoice_number",
        "invoice_date",
        "total_amount"
    }


    missing_critical_fields = [
        field
        for field in critical_fields
        if field_flags.get(field)
        == "UNKNOWN"
    ]


    # ========================================================
    # REVIEW REQUIREMENT
    # ========================================================

    review_required = False


    if missing_critical_fields:

        review_required = True


    if warnings:

        review_required = True


    if confidence < 80:

        review_required = True


    # ========================================================
    # FINAL RESULT
    # ========================================================

    return {
        "status": status,
        "confidence": confidence,
        "review_required": review_required,
        "errors": errors,
        "warnings": warnings,
        "field_flags": field_flags,
        "data_quality": {
            "total_fields": total_fields,
            "valid_fields": valid_fields,
            "warning_fields": warning_fields,
            "unknown_fields": unknown_fields,
            "completeness": completeness
        }
    }