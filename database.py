import os
import sqlite3
from pathlib import Path

# Set DATABASE_PATH to a persistent location in production.
DATABASE_FILE = Path(os.environ.get("DATABASE_PATH", "invoice_engine.db"))


def get_connection():
    connection = sqlite3.connect(str(DATABASE_FILE), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


def _columns(cursor, table):
    return {
        row["name"]
        for row in cursor.execute(f"PRAGMA table_info({table})")
    }


def _add_missing_columns(cursor, table, definitions):
    existing = _columns(cursor, table)

    for name, sql_type in definitions.items():
        if name not in existing:
            cursor.execute(
                f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}"
            )


def initialize_database():
    """Create tables and safely add new columns to older databases."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                file_hash TEXT UNIQUE,
                invoice_number TEXT,
                invoice_date TEXT,
                portal_invoice_number TEXT,
                portal_invoice_date TEXT,
                currency TEXT,
                seller_name TEXT,
                seller_address TEXT,
                seller_gstin TEXT,
                buyer_name TEXT,
                buyer_address TEXT,
                buyer_gstin TEXT,
                subtotal REAL,
                taxable_amount REAL,
                tax_rate REAL,
                tax_amount REAL,
                cgst REAL,
                sgst REAL,
                igst REAL,
                total_amount REAL,
                status TEXT,
                confidence REAL,
                review_required INTEGER DEFAULT 0,
                completeness REAL,
                errors TEXT,
                warnings TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        _add_missing_columns(cursor, "invoices", {
            "seller_name": "TEXT",
            "seller_address": "TEXT",
            "buyer_name": "TEXT",
            "buyer_address": "TEXT",
            "cgst": "REAL",
            "sgst": "REAL",
        })

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS line_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                description TEXT,
                quantity REAL,
                unit_price REAL,
                amount REAL,
                product_name TEXT,
                model TEXT,
                sku TEXT,
                hsn_sac TEXT,
                uom TEXT,
                free_quantity REAL,
                gross_amount REAL,
                discount REAL,
                discount_percent REAL,
                taxable_amount REAL,
                gst_rate REAL,
                cgst REAL,
                sgst REAL,
                item_igst REAL,
                cess REAL,
                FOREIGN KEY (invoice_id)
                    REFERENCES invoices(id)
                    ON DELETE CASCADE
            )
        """)

        _add_missing_columns(cursor, "line_items", {
            "product_name": "TEXT",
            "model": "TEXT",
            "sku": "TEXT",
            "hsn_sac": "TEXT",
            "uom": "TEXT",
            "free_quantity": "REAL",
            "gross_amount": "REAL",
            "discount": "REAL",
            "discount_percent": "REAL",
            "taxable_amount": "REAL",
            "gst_rate": "REAL",
            "cgst": "REAL",
            "sgst": "REAL",
            "item_igst": "REAL",
            "cess": "REAL",
        })

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_invoices_invoice_number ON invoices(invoice_number)",
            "CREATE INDEX IF NOT EXISTS idx_invoices_invoice_date ON invoices(invoice_date)",
            "CREATE INDEX IF NOT EXISTS idx_invoices_seller_gstin ON invoices(seller_gstin)",
            "CREATE INDEX IF NOT EXISTS idx_invoices_buyer_gstin ON invoices(buyer_gstin)",
            "CREATE INDEX IF NOT EXISTS idx_invoices_seller_name ON invoices(seller_name)",
            "CREATE INDEX IF NOT EXISTS idx_invoices_buyer_name ON invoices(buyer_name)",
            "CREATE INDEX IF NOT EXISTS idx_invoices_total_amount ON invoices(total_amount)",
            "CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status)",
            "CREATE INDEX IF NOT EXISTS idx_line_items_invoice_id ON line_items(invoice_id)",
            "CREATE INDEX IF NOT EXISTS idx_line_items_description ON line_items(description)",
            "CREATE INDEX IF NOT EXISTS idx_line_items_product_name ON line_items(product_name)",
            "CREATE INDEX IF NOT EXISTS idx_line_items_model ON line_items(model)",
            "CREATE INDEX IF NOT EXISTS idx_line_items_hsn ON line_items(hsn_sac)",
            "CREATE INDEX IF NOT EXISTS idx_line_items_sku ON line_items(sku)",
        ]

        for statement in indexes:
            cursor.execute(statement)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def invoice_exists(file_hash):
    connection = get_connection()

    try:
        return connection.execute(
            "SELECT 1 FROM invoices WHERE file_hash = ? LIMIT 1",
            (file_hash,)
        ).fetchone() is not None

    finally:
        connection.close()


def _invoice_with_items(
    connection,
    row,
    remove_internal_fields=False
):
    if row is None:
        return None

    invoice = dict(row)

    items = connection.execute(
        "SELECT * FROM line_items WHERE invoice_id = ? ORDER BY id",
        (invoice["id"],)
    ).fetchall()

    invoice["line_items"] = [
        dict(item) for item in items
    ]

    invoice["review_required"] = bool(
        invoice.get("review_required")
    )

    if remove_internal_fields:
        for field in ("id", "file_hash", "created_at"):
            invoice.pop(field, None)

    return invoice


def get_invoice_by_hash(file_hash):
    connection = get_connection()

    try:
        row = connection.execute(
            "SELECT * FROM invoices WHERE file_hash = ?",
            (file_hash,)
        ).fetchone()

        return _invoice_with_items(
            connection,
            row,
            remove_internal_fields=True
        )

    finally:
        connection.close()


def get_invoice_by_id(invoice_id):
    connection = get_connection()

    try:
        row = connection.execute(
            "SELECT * FROM invoices WHERE id = ?",
            (invoice_id,)
        ).fetchone()

        return _invoice_with_items(connection, row)

    finally:
        connection.close()


def save_invoice(invoice, file_hash):
    """Save an invoice and its line items; return the database ID."""
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO invoices (
                file_name,
                file_hash,
                invoice_number,
                invoice_date,
                portal_invoice_number,
                portal_invoice_date,
                currency,
                seller_name,
                seller_address,
                seller_gstin,
                buyer_name,
                buyer_address,
                buyer_gstin,
                subtotal,
                taxable_amount,
                tax_rate,
                tax_amount,
                cgst,
                sgst,
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
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            invoice.get("file_name"),
            file_hash,
            invoice.get("invoice_number"),
            invoice.get("invoice_date"),
            invoice.get("portal_invoice_number"),
            invoice.get("portal_invoice_date"),
            invoice.get("currency"),
            invoice.get("seller_name") or invoice.get("vendor_name"),
            invoice.get("seller_address") or invoice.get("vendor_address"),
            invoice.get("seller_gstin") or invoice.get("vendor_gstin"),
            invoice.get("buyer_name") or invoice.get("customer_name"),
            invoice.get("buyer_address") or invoice.get("customer_address"),
            invoice.get("buyer_gstin") or invoice.get("customer_gstin"),
            invoice.get("subtotal"),
            invoice.get("taxable_amount"),
            invoice.get("tax_rate"),
            invoice.get("tax_amount"),
            invoice.get("cgst"),
            invoice.get("sgst"),
            invoice.get("igst"),
            invoice.get("total_amount"),
            invoice.get("status"),
            invoice.get("confidence"),
            int(bool(invoice.get("review_required", False))),
            invoice.get("completeness"),
            invoice.get("errors"),
            invoice.get("warnings"),
        ))

        invoice_id = cursor.lastrowid

        for item in invoice.get("line_items") or []:
            cursor.execute("""
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
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                invoice_id,
                item.get("description")
                    or item.get("product_name")
                    or item.get("item_name"),
                item.get("quantity"),
                item.get("unit_price"),
                item.get("amount"),
                item.get("product_name")
                    or item.get("item_name")
                    or item.get("description"),
                item.get("model") or item.get("model_number"),
                item.get("sku"),
                item.get("hsn_sac")
                    or item.get("hsn_code")
                    or item.get("sac_code"),
                item.get("uom") or item.get("unit"),
                item.get("free_quantity"),
                item.get("gross_amount"),
                item.get("discount"),
                item.get("discount_percent"),
                item.get("taxable_amount"),
                item.get("gst_rate") or item.get("tax_rate"),
                item.get("cgst"),
                item.get("sgst"),
                (
                    item.get("igst")
                    if item.get("igst") is not None
                    else item.get("item_igst")
                ),
                item.get("cess"),
            ))

        connection.commit()
        return invoice_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


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
    page_size=50,
    seller_name=None,
    buyer_name=None,
    product_name=None,
    model=None,
    hsn_sac=None,
):
    """Search invoices and product fields with pagination."""
    connection = get_connection()

    try:
        conditions = []
        parameters = []

        if search_text and search_text.strip():
            value = f"%{search_text.strip()}%"

            conditions.append("""
                (
                    i.invoice_number LIKE ?
                    OR i.portal_invoice_number LIKE ?
                    OR i.seller_name LIKE ?
                    OR i.buyer_name LIKE ?
                    OR i.seller_gstin LIKE ?
                    OR i.buyer_gstin LIKE ?
                    OR i.file_name LIKE ?
                    OR li.description LIKE ?
                    OR li.product_name LIKE ?
                    OR li.model LIKE ?
                    OR li.sku LIKE ?
                    OR li.hsn_sac LIKE ?
                )
            """)

            parameters.extend([value] * 12)

        for column, value in (
            ("i.status", status),
            ("i.seller_gstin", seller_gstin),
            ("i.buyer_gstin", buyer_gstin),
            ("i.seller_name", seller_name),
            ("i.buyer_name", buyer_name),
        ):
            if value:
                if column == "i.status":
                    conditions.append(f"{column} = ?")
                    parameters.append(value)
                else:
                    conditions.append(f"{column} LIKE ?")
                    parameters.append(f"%{value.strip()}%")

        for column, value in (
            ("li.product_name", product_name),
            ("li.model", model),
            ("li.hsn_sac", hsn_sac),
        ):
            if value:
                conditions.append(f"{column} LIKE ?")
                parameters.append(f"%{value.strip()}%")

        for column, value, operator in (
            ("i.total_amount", min_amount, ">="),
            ("i.total_amount", max_amount, "<="),
            ("i.invoice_date", date_from, ">="),
            ("i.invoice_date", date_to, "<="),
        ):
            if value is not None and value != "":
                conditions.append(f"{column} {operator} ?")
                parameters.append(value)

        where_clause = (
            " WHERE " + " AND ".join(conditions)
            if conditions else ""
        )

        total = connection.execute("""
            SELECT COUNT(DISTINCT i.id) AS total
            FROM invoices i
            LEFT JOIN line_items li ON li.invoice_id = i.id
        """ + where_clause, parameters).fetchone()["total"]

        page = max(1, int(page))
        page_size = min(200, max(1, int(page_size)))

        rows = connection.execute("""
            SELECT DISTINCT
                i.id,
                i.file_name,
                i.invoice_number,
                i.invoice_date,
                i.portal_invoice_number,
                i.portal_invoice_date,
                i.currency,
                i.seller_name,
                i.seller_address,
                i.seller_gstin,
                i.buyer_name,
                i.buyer_address,
                i.buyer_gstin,
                i.subtotal,
                i.taxable_amount,
                i.tax_rate,
                i.tax_amount,
                i.cgst,
                i.sgst,
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
            LEFT JOIN line_items li ON li.invoice_id = i.id
        """ + where_clause + """
            ORDER BY i.invoice_date DESC, i.id DESC
            LIMIT ? OFFSET ?
        """, parameters + [
            page_size,
            (page - 1) * page_size
        ]).fetchall()

        results = []

        for row in rows:
            result = dict(row)
            result["review_required"] = bool(
                result.get("review_required")
            )
            results.append(result)

        return {
            "results": results,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (
                (total + page_size - 1) // page_size
                if total else 0
            ),
        }

    finally:
        connection.close()


def search_line_items(
    search_text=None,
    page=1,
    page_size=200
):
    """Search products and return matching lines with invoice details."""
    connection = get_connection()

    try:
        conditions = []
        parameters = []

        if search_text and search_text.strip():
            value = f"%{search_text.strip()}%"

            conditions.append("""
                (
                    li.description LIKE ?
                    OR li.product_name LIKE ?
                    OR li.model LIKE ?
                    OR li.sku LIKE ?
                    OR li.hsn_sac LIKE ?
                )
            """)

            parameters.extend([value] * 5)

        where_clause = (
            " WHERE " + " AND ".join(conditions)
            if conditions else ""
        )

        total = connection.execute("""
            SELECT COUNT(*)
            FROM line_items li
            JOIN invoices i ON i.id = li.invoice_id
        """ + where_clause, parameters).fetchone()[0]

        page = max(1, int(page))
        page_size = min(1000, max(1, int(page_size)))

        rows = connection.execute("""
            SELECT
                li.*,
                i.file_name,
                i.invoice_number,
                i.invoice_date,
                i.seller_name,
                i.seller_gstin,
                i.buyer_name,
                i.buyer_gstin,
                i.tax_amount AS invoice_tax_amount,
                i.total_amount AS invoice_total_amount
            FROM line_items li
            JOIN invoices i ON i.id = li.invoice_id
        """ + where_clause + """
            ORDER BY i.invoice_date DESC, i.id DESC, li.id
            LIMIT ? OFFSET ?
        """, parameters + [
            page_size,
            (page - 1) * page_size
        ]).fetchall()

        return {
            "results": [dict(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (
                (total + page_size - 1) // page_size
                if total else 0
            ),
        }

    finally:
        connection.close()


def get_database_stats():
    connection = get_connection()

    try:
        invoice_stats = dict(connection.execute("""
            SELECT
                COUNT(*) AS total_invoices,
                COALESCE(SUM(total_amount), 0) AS total_amount,
                COALESCE(SUM(taxable_amount), 0) AS taxable_amount,
                COALESCE(SUM(tax_amount), 0) AS tax_amount,
                COALESCE(SUM(cgst), 0) AS cgst,
                COALESCE(SUM(sgst), 0) AS sgst,
                COALESCE(SUM(igst), 0) AS igst,
                SUM(
                    CASE WHEN status = 'Valid' THEN 1 ELSE 0 END
                ) AS valid,
                SUM(
                    CASE WHEN status = 'Warning' THEN 1 ELSE 0 END
                ) AS warnings,
                SUM(
                    CASE WHEN status = 'Invalid' THEN 1 ELSE 0 END
                ) AS invalid
            FROM invoices
        """).fetchone())

        item_stats = dict(connection.execute("""
            SELECT
                COUNT(*) AS total_line_items,
                COALESCE(SUM(quantity), 0) AS total_quantity
            FROM line_items
        """).fetchone())

        vendor_stats = dict(connection.execute("""
            SELECT COUNT(DISTINCT CASE
                WHEN seller_name IS NOT NULL
                    AND TRIM(seller_name) != ''
                    THEN LOWER(TRIM(seller_name))
                WHEN seller_gstin IS NOT NULL
                    AND TRIM(seller_gstin) != ''
                    THEN LOWER(TRIM(seller_gstin))
            END) AS unique_vendors
            FROM invoices
        """).fetchone())

        return {
            **invoice_stats,
            **item_stats,
            **vendor_stats
        }

    finally:
        connection.close()