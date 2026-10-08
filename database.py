import sqlite3

from pathlib import Path


# ============================================================
# DATABASE
# ============================================================

DATABASE_FILE = Path(
    "invoice_engine.db"
)


# ============================================================
# CONNECTION
# ============================================================

def get_connection():

    connection = sqlite3.connect(
        DATABASE_FILE,
        timeout=30
    )

    connection.row_factory = sqlite3.Row

    # Helps SQLite behave better when
    # the API and worker access the DB.
    connection.execute(
        "PRAGMA journal_mode=WAL"
    )

    connection.execute(
        "PRAGMA foreign_keys=ON"
    )

    return connection


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def initialize_database():

    connection = get_connection()

    cursor = connection.cursor()


    # --------------------------------------------------------
    # INVOICES
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            file_name TEXT NOT NULL,

            file_hash TEXT UNIQUE,

            invoice_number TEXT,

            invoice_date TEXT,

            portal_invoice_number TEXT,

            portal_invoice_date TEXT,

            currency TEXT,

            seller_gstin TEXT,

            buyer_gstin TEXT,

            subtotal REAL,

            taxable_amount REAL,

            tax_rate REAL,

            tax_amount REAL,

            igst REAL,

            total_amount REAL,

            status TEXT,

            confidence REAL,

            review_required INTEGER,

            completeness REAL,

            errors TEXT,

            warnings TEXT,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


    # --------------------------------------------------------
    # LINE ITEMS
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS line_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            invoice_id INTEGER NOT NULL,

            description TEXT,

            quantity REAL,

            unit_price REAL,

            amount REAL,

            FOREIGN KEY (
                invoice_id
            )
            REFERENCES invoices(id)
            ON DELETE CASCADE
        )
        """
    )


    # --------------------------------------------------------
    # FUTURE-READY LINE ITEM FIELDS
    #
    # These fields are added now so the database can grow
    # without requiring another database redesign later.
    #
    # Existing invoices will simply contain NULL values
    # until the extractor starts filling them.
    # --------------------------------------------------------

    existing_columns = {
        row["name"]
        for row in cursor.execute(
            "PRAGMA table_info(line_items)"
        ).fetchall()
    }


    future_columns = {

        "product_name":
            "TEXT",

        "model":
            "TEXT",

        "sku":
            "TEXT",

        "hsn_sac":
            "TEXT",

        "uom":
            "TEXT",

        "free_quantity":
            "REAL",

        "gross_amount":
            "REAL",

        "discount":
            "REAL",

        "discount_percent":
            "REAL",

        "taxable_amount":
            "REAL",

        "gst_rate":
            "REAL",

        "cgst":
            "REAL",

        "sgst":
            "REAL",

        "item_igst":
            "REAL",

        "cess":
            "REAL"
    }


    for column_name, column_type in future_columns.items():

        if column_name not in existing_columns:

            cursor.execute(
                f"""
                ALTER TABLE line_items
                ADD COLUMN {column_name}
                {column_type}
                """
            )


    # --------------------------------------------------------
    # INDEXES
    #
    # These make searching much faster as the database grows.
    # --------------------------------------------------------

    indexes = [

        """
        CREATE INDEX IF NOT EXISTS
        idx_invoices_invoice_number
        ON invoices(invoice_number)
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_invoices_invoice_date
        ON invoices(invoice_date)
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_invoices_seller_gstin
        ON invoices(seller_gstin)
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_invoices_buyer_gstin
        ON invoices(buyer_gstin)
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_invoices_total_amount
        ON invoices(total_amount)
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_invoices_status
        ON invoices(status)
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_line_items_invoice_id
        ON line_items(invoice_id)
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_line_items_description
        ON line_items(description)
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_line_items_product_name
        ON line_items(product_name)
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_line_items_model
        ON line_items(model)
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_line_items_hsn
        ON line_items(hsn_sac)
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_line_items_sku
        ON line_items(sku)
        """
    ]


    for index_sql in indexes:

        cursor.execute(
            index_sql
        )


    connection.commit()

    connection.close()


# ============================================================
# DUPLICATE CHECK
# ============================================================

def invoice_exists(file_hash):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id
        FROM invoices
        WHERE file_hash = ?
        """,
        (file_hash,)
    )

    result = cursor.fetchone()

    connection.close()

    return result is not None


# ============================================================
# GET INVOICE BY HASH
# ============================================================

def get_invoice_by_hash(file_hash):

    connection = get_connection()

    cursor = connection.cursor()


    cursor.execute(
        """
        SELECT *
        FROM invoices
        WHERE file_hash = ?
        """,
        (file_hash,)
    )


    invoice_row = cursor.fetchone()


    if invoice_row is None:

        connection.close()

        return None


    invoice = dict(
        invoice_row
    )


    cursor.execute(
        """
        SELECT *
        FROM line_items
        WHERE invoice_id = ?
        ORDER BY id
        """,
        (
            invoice["id"],
        )
    )


    line_items = cursor.fetchall()


    invoice["line_items"] = [

        dict(item)

        for item in line_items

    ]


    connection.close()


    invoice.pop(
        "id",
        None
    )

    invoice.pop(
        "file_hash",
        None
    )

    invoice.pop(
        "created_at",
        None
    )


    invoice["review_required"] = bool(
        invoice.get(
            "review_required"
        )
    )


    return invoice


# ============================================================
# GET INVOICE BY ID
# ============================================================

def get_invoice_by_id(invoice_id):

    connection = get_connection()

    cursor = connection.cursor()


    cursor.execute(
        """
        SELECT *
        FROM invoices
        WHERE id = ?
        """,
        (
            invoice_id,
        )
    )


    invoice_row = cursor.fetchone()


    if invoice_row is None:

        connection.close()

        return None


    invoice = dict(
        invoice_row
    )


    cursor.execute(
        """
        SELECT *
        FROM line_items
        WHERE invoice_id = ?
        ORDER BY id
        """,
        (
            invoice_id,
        )
    )


    line_items = cursor.fetchall()


    invoice["line_items"] = [

        dict(item)

        for item in line_items

    ]


    connection.close()


    invoice["review_required"] = bool(
        invoice.get(
            "review_required"
        )
    )


    return invoice


# ============================================================
# SAVE INVOICE
# ============================================================

def save_invoice(
    invoice,
    file_hash
):

    connection = get_connection()

    cursor = connection.cursor()


    cursor.execute(
        """
        INSERT INTO invoices (
            file_name,
            file_hash,
            invoice_number,
            invoice_date,
            portal_invoice_number,
            portal_invoice_date,
            currency,
            seller_gstin,
            buyer_gstin,
            subtotal,
            taxable_amount,
            tax_rate,
            tax_amount,
            igst,
            total_amount,
            status,
            confidence,
            review_required,
            completeness,
            errors,
            warnings
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            invoice.get(
                "file_name"
            ),

            file_hash,

            invoice.get(
                "invoice_number"
            ),

            invoice.get(
                "invoice_date"
            ),

            invoice.get(
                "portal_invoice_number"
            ),

            invoice.get(
                "portal_invoice_date"
            ),

            invoice.get(
                "currency"
            ),

            invoice.get(
                "seller_gstin"
            ),

            invoice.get(
                "buyer_gstin"
            ),

            invoice.get(
                "subtotal"
            ),

            invoice.get(
                "taxable_amount"
            ),

            invoice.get(
                "tax_rate"
            ),

            invoice.get(
                "tax_amount"
            ),

            invoice.get(
                "igst"
            ),

            invoice.get(
                "total_amount"
            ),

            invoice.get(
                "status"
            ),

            invoice.get(
                "confidence"
            ),

            int(
                invoice.get(
                    "review_required",
                    False
                )
            ),

            invoice.get(
                "completeness"
            ),

            invoice.get(
                "errors"
            ),

            invoice.get(
                "warnings"
            )
        )
    )


    invoice_id = cursor.lastrowid


    # --------------------------------------------------------
    # LINE ITEMS
    # --------------------------------------------------------

    line_items = invoice.get(
        "line_items",
        []
    )


    for item in line_items:

        cursor.execute(
            """
            INSERT INTO line_items (
                invoice_id,

                description,
                quantity,
                unit_price,
                amount,

                product_name,
                model,
                sku,
                hsn_sac,
                uom,
                free_quantity,
                gross_amount,
                discount,
                discount_percent,
                taxable_amount,
                gst_rate,
                cgst,
                sgst,
                item_igst,
                cess
            )
            VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?
            )
            """,
            (

                invoice_id,

                item.get(
                    "description"
                ),

                item.get(
                    "quantity"
                ),

                item.get(
                    "unit_price"
                ),

                item.get(
                    "amount"
                ),

                item.get(
                    "product_name"
                ),

                item.get(
                    "model"
                ),

                item.get(
                    "sku"
                ),

                item.get(
                    "hsn_sac"
                ),

                item.get(
                    "uom"
                ),

                item.get(
                    "free_quantity"
                ),

                item.get(
                    "gross_amount"
                ),

                item.get(
                    "discount"
                ),

                item.get(
                    "discount_percent"
                ),

                item.get(
                    "taxable_amount"
                ),

                item.get(
                    "gst_rate"
                ),

                item.get(
                    "cgst"
                ),

                item.get(
                    "sgst"
                ),

                item.get(
                    "igst"
                ),

                item.get(
                    "cess"
                )
            )
        )


    connection.commit()

    connection.close()


    return invoice_id


# ============================================================
# SEARCH INVOICES
# ============================================================

def search_invoices(
    search_text=None,
    status=None,
    seller_gstin=None,
    buyer_gstin=None,
    min_amount=None,
    max_amount=None,
    date_from=None,
    date_to=None,
    page=1,
    page_size=50
):

    connection = get_connection()

    cursor = connection.cursor()


    conditions = []

    parameters = []


    # --------------------------------------------------------
    # TEXT SEARCH
    # --------------------------------------------------------

    if search_text:

        search_value = (
            f"%{search_text.strip()}%"
        )


        conditions.append(
            """
            (
                i.invoice_number LIKE ?
                OR i.portal_invoice_number LIKE ?
                OR i.seller_gstin LIKE ?
                OR i.buyer_gstin LIKE ?
                OR i.file_name LIKE ?

                OR li.description LIKE ?
                OR li.product_name LIKE ?
                OR li.model LIKE ?
                OR li.sku LIKE ?
                OR li.hsn_sac LIKE ?
            )
            """
        )


        parameters.extend(
            [search_value] * 10
        )


    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    if status:

        conditions.append(
            "i.status = ?"
        )

        parameters.append(
            status
        )


    # --------------------------------------------------------
    # SELLER GSTIN
    # --------------------------------------------------------

    if seller_gstin:

        conditions.append(
            "i.seller_gstin LIKE ?"
        )

        parameters.append(
            f"%{seller_gstin.strip()}%"
        )


    # --------------------------------------------------------
    # BUYER GSTIN
    # --------------------------------------------------------

    if buyer_gstin:

        conditions.append(
            "i.buyer_gstin LIKE ?"
        )

        parameters.append(
            f"%{buyer_gstin.strip()}%"
        )


    # --------------------------------------------------------
    # MINIMUM AMOUNT
    # --------------------------------------------------------

    if min_amount is not None:

        conditions.append(
            "i.total_amount >= ?"
        )

        parameters.append(
            min_amount
        )


    # --------------------------------------------------------
    # MAXIMUM AMOUNT
    # --------------------------------------------------------

    if max_amount is not None:

        conditions.append(
            "i.total_amount <= ?"
        )

        parameters.append(
            max_amount
        )


    # --------------------------------------------------------
    # DATE FROM
    # --------------------------------------------------------

    if date_from:

        conditions.append(
            "i.invoice_date >= ?"
        )

        parameters.append(
            date_from
        )


    # --------------------------------------------------------
    # DATE TO
    # --------------------------------------------------------

    if date_to:

        conditions.append(
            "i.invoice_date <= ?"
        )

        parameters.append(
            date_to
        )


    where_clause = ""


    if conditions:

        where_clause = (
            "WHERE "
            + " AND ".join(
                conditions
            )
        )


    # --------------------------------------------------------
    # COUNT
    # --------------------------------------------------------

    count_sql = f"""
        SELECT COUNT(
            DISTINCT i.id
        ) AS total

        FROM invoices i

        LEFT JOIN line_items li
            ON li.invoice_id = i.id

        {where_clause}
    """


    cursor.execute(
        count_sql,
        parameters
    )


    total_count = (
        cursor.fetchone()["total"]
    )


    # --------------------------------------------------------
    # PAGINATION
    # --------------------------------------------------------

    page = max(
        1,
        int(page)
    )


    page_size = min(
        200,
        max(
            1,
            int(page_size)
        )
    )


    offset = (
        page - 1
    ) * page_size


    # --------------------------------------------------------
    # RESULTS
    # --------------------------------------------------------

    result_sql = f"""
        SELECT DISTINCT
            i.id,
            i.file_name,
            i.invoice_number,
            i.invoice_date,
            i.portal_invoice_number,
            i.portal_invoice_date,
            i.currency,

            i.seller_gstin,
            i.buyer_gstin,

            i.subtotal,
            i.taxable_amount,
            i.tax_rate,
            i.tax_amount,
            i.igst,
            i.total_amount,

            i.status,
            i.confidence,
            i.review_required,
            i.completeness,

            i.errors,
            i.warnings,

            i.created_at

        FROM invoices i

        LEFT JOIN line_items li
            ON li.invoice_id = i.id

        {where_clause}

        ORDER BY
            i.invoice_date DESC,
            i.id DESC

        LIMIT ?
        OFFSET ?
    """


    result_parameters = (
        parameters
        + [
            page_size,
            offset
        ]
    )


    cursor.execute(
        result_sql,
        result_parameters
    )


    invoice_rows = cursor.fetchall()


    results = []


    for row in invoice_rows:

        invoice = dict(row)

        invoice["review_required"] = bool(
            invoice.get(
                "review_required"
            )
        )

        results.append(
            invoice
        )


    connection.close()


    total_pages = (
        (
            total_count
            + page_size
            - 1
        )
        // page_size
        if total_count
        else 0
    )


    return {

        "results":
            results,

        "total":
            total_count,

        "page":
            page,

        "page_size":
            page_size,

        "total_pages":
            total_pages

    }


# ============================================================
# DATABASE STATISTICS
# ============================================================

def get_database_stats():

    connection = get_connection()

    cursor = connection.cursor()


    cursor.execute(
        """
        SELECT
            COUNT(*) AS total_invoices,

            COALESCE(
                SUM(total_amount),
                0
            ) AS total_amount,

            COALESCE(
                SUM(taxable_amount),
                0
            ) AS taxable_amount,

            COALESCE(
                SUM(tax_amount),
                0
            ) AS tax_amount,

            COALESCE(
                SUM(igst),
                0
            ) AS igst,

            SUM(
                CASE
                    WHEN status = 'Valid'
                    THEN 1
                    ELSE 0
                END
            ) AS valid,

            SUM(
                CASE
                    WHEN status = 'Warning'
                    THEN 1
                    ELSE 0
                END
            ) AS warnings,

            SUM(
                CASE
                    WHEN status = 'Invalid'
                    THEN 1
                    ELSE 0
                END
            ) AS invalid

        FROM invoices
        """
    )


    invoice_stats = dict(
        cursor.fetchone()
    )


    cursor.execute(
        """
        SELECT
            COUNT(*) AS total_line_items,

            COALESCE(
                SUM(quantity),
                0
            ) AS total_quantity

        FROM line_items
        """
    )


    item_stats = dict(
        cursor.fetchone()
    )


    cursor.execute(
        """
        SELECT COUNT(
            DISTINCT seller_gstin
        ) AS unique_vendors

        FROM invoices

        WHERE seller_gstin IS NOT NULL

        AND TRIM(
            seller_gstin
        ) != ''
        """
    )


    vendor_stats = dict(
        cursor.fetchone()
    )


    connection.close()


    return {

        **invoice_stats,

        **item_stats,

        **vendor_stats

    }