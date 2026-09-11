import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from app.core.config import SQLITE_DB_PATH
from app.core.security import hash_password, is_legacy_password_hash, verify_password

DB_PATH = Path(SQLITE_DB_PATH)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# DB schema/migrations/admin seed are idempotent but relatively expensive because
# admin password verification uses PBKDF2. Run them once per process/database file.
_DB_INITIALIZED = False

SCHEMAS = {
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            tax_type TEXT NOT NULL DEFAULT 'simple',
            tax_warning_confirmed_at TEXT,
            profit_tax_reserve_rate REAL NOT NULL DEFAULT 10,
            income_tax_reserve_rate REAL NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "products": """
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            supplier_id TEXT,
            sku TEXT,
            name TEXT NOT NULL,
            supply_price REAL NOT NULL DEFAULT 0,
            sale_price REAL NOT NULL DEFAULT 0,
            shipping_fee REAL NOT NULL DEFAULT 0,
            market_fee_rate REAL NOT NULL DEFAULT 0,
            purchase_price REAL NOT NULL DEFAULT 0,
            international_shipping REAL NOT NULL DEFAULT 0,
            domestic_shipping REAL NOT NULL DEFAULT 0,
            selling_price REAL NOT NULL DEFAULT 0,
            fee_rate REAL NOT NULL DEFAULT 0,
            vat_rate REAL NOT NULL DEFAULT 0.1,
            total_cost REAL NOT NULL DEFAULT 0,
            fee_amount REAL NOT NULL DEFAULT 0,
            vat_amount REAL NOT NULL DEFAULT 0,
            net_profit REAL NOT NULL DEFAULT 0,
            margin_rate REAL NOT NULL DEFAULT 0,
            main_image_url TEXT,
            detail_image_url TEXT,
            status TEXT NOT NULL DEFAULT 'STOP',
            status_reason TEXT NOT NULL DEFAULT '순이익 부족',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "suppliers": """
        CREATE TABLE IF NOT EXISTS suppliers (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            memo TEXT,
            source_platform TEXT,
            store_name TEXT,
            store_url TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "inventory": """
        CREATE TABLE IF NOT EXISTS inventory (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            minimum_quantity INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, product_id)
        )
    """,
    "inventory_history": """
        CREATE TABLE IF NOT EXISTS inventory_history (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "activity_logs": """
        CREATE TABLE IF NOT EXISTS activity_logs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            category TEXT NOT NULL,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT,
            entity_name TEXT,
            detail TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "product_recalculation_history": """
        CREATE TABLE IF NOT EXISTS product_recalculation_history (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            old_status TEXT,
            new_status TEXT NOT NULL,
            net_profit REAL NOT NULL DEFAULT 0,
            margin_rate REAL NOT NULL DEFAULT 0,
            reason TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "margin_calculations": """
        CREATE TABLE IF NOT EXISTS margin_calculations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            product_id TEXT,
            supply_price REAL NOT NULL DEFAULT 0,
            sale_price REAL NOT NULL DEFAULT 0,
            shipping_fee REAL NOT NULL DEFAULT 0,
            market_fee_rate REAL NOT NULL DEFAULT 0,
            vat_rate REAL NOT NULL DEFAULT 0.1,
            tax_type TEXT NOT NULL DEFAULT 'simple',
            market_fee REAL NOT NULL DEFAULT 0,
            vat_amount REAL NOT NULL DEFAULT 0,
            total_cost REAL NOT NULL DEFAULT 0,
            net_profit REAL NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "sell_stop_results": """
        CREATE TABLE IF NOT EXISTS sell_stop_results (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            product_id TEXT,
            margin_calculation_id TEXT,
            net_profit REAL NOT NULL DEFAULT 0,
            result TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "sourcing_items": """
        CREATE TABLE IF NOT EXISTS sourcing_items (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, supplier_id TEXT, product_name TEXT NOT NULL,
            source_url TEXT, purchase_price REAL NOT NULL DEFAULT 0, shipping_fee REAL NOT NULL DEFAULT 0,
            options_text TEXT, options_json TEXT, image_url TEXT, image_urls_json TEXT, availability TEXT NOT NULL DEFAULT 'AVAILABLE', memo TEXT,
            supplier_store_name TEXT, supplier_store_url TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT
        )
    """,
    "orders": """
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, channel TEXT NOT NULL DEFAULT 'MANUAL', order_no TEXT NOT NULL,
            product_name TEXT NOT NULL, option_text TEXT, quantity INTEGER NOT NULL DEFAULT 1, sale_price REAL NOT NULL DEFAULT 0,
            buyer_name TEXT, recipient TEXT, phone TEXT, address TEXT, detail_address TEXT, postal_code TEXT, delivery_memo TEXT,
            supplier_name TEXT, source_url TEXT, expected_profit REAL NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'NEW',
            app_order_id TEXT, product_id TEXT, customer_id TEXT, payment_status TEXT NOT NULL DEFAULT 'PAID',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT
        )
    """,
    "purchase_orders": """
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, order_id TEXT NOT NULL, supplier_name TEXT, supplier_url TEXT,
            amount REAL NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'READY', note TEXT, validation_status TEXT,
            prepared_payload TEXT, prepared_at TEXT, checkout_url TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT, UNIQUE(user_id, order_id)
        )
    """,
    "shipments": """
        CREATE TABLE IF NOT EXISTS shipments (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, order_id TEXT NOT NULL, carrier TEXT, tracking_no TEXT,
            status TEXT NOT NULL DEFAULT 'READY', expected_delivery TEXT, note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT, UNIQUE(user_id, order_id)
        )
    """,
    "price_trackers": """
        CREATE TABLE IF NOT EXISTS price_trackers (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, product_id TEXT NOT NULL, competitor_price REAL,
            tracking_enabled INTEGER NOT NULL DEFAULT 1, last_checked_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT,
            UNIQUE(user_id, product_id)
        )
    """,
    "ai_drafts": """
        CREATE TABLE IF NOT EXISTS ai_drafts (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, product_id TEXT, source_name TEXT NOT NULL, title TEXT NOT NULL,
            description TEXT, keywords TEXT, selling_points TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "price_automation_rules": """
        CREATE TABLE IF NOT EXISTS price_automation_rules (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, product_id TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
            undercut_amount REAL NOT NULL DEFAULT 100, auto_stop INTEGER NOT NULL DEFAULT 1, auto_resume INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, product_id)
        )
    """,
    "price_history": """
        CREATE TABLE IF NOT EXISTS price_history (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, product_id TEXT NOT NULL, competitor_price REAL, old_price REAL, new_price REAL,
            minimum_sellable_price REAL NOT NULL DEFAULT 0, action TEXT NOT NULL, reason TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "channel_connections": """
        CREATE TABLE IF NOT EXISTS channel_connections (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, channel TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 0,
            account_label TEXT, note TEXT, updated_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, channel)
        )
    """,
    "after_sales_requests": """
        CREATE TABLE IF NOT EXISTS after_sales_requests (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, order_id TEXT NOT NULL,
            request_type TEXT NOT NULL, reason TEXT, status TEXT NOT NULL DEFAULT 'REQUESTED',
            supplier_status TEXT NOT NULL DEFAULT 'NOT_REQUIRED', channel_status TEXT NOT NULL DEFAULT 'RECEIVED',
            refund_amount REAL NOT NULL DEFAULT 0, requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT, updated_at TEXT
        )
    """,
}


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    global _DB_INITIALIZED
    if _DB_INITIALIZED and DB_PATH.exists():
        return
    with _connect() as conn:
        for ddl in SCHEMAS.values():
            conn.execute(ddl)
        _migrate_users_plans(conn)
        _migrate_users_tax_reserve(conn)
        _migrate_one_click_purchase(conn)
        _migrate_sourcing_url_import(conn)
        _migrate_supplier_source_meta(conn)
        _migrate_products_v1_2(conn)
        _migrate_sell_stop_two_state(conn)
        _migrate_inventory_v1(conn)
        _migrate_query_indexes(conn)
        _seed_admin(conn)
    _DB_INITIALIZED = True


def _migrate_query_indexes(conn: sqlite3.Connection) -> None:
    """Read-heavy MVP screens are scoped by user_id; add safe non-destructive indexes."""
    indexes = (
        "CREATE INDEX IF NOT EXISTS idx_products_user ON products (user_id)",
        "CREATE INDEX IF NOT EXISTS idx_products_user_status ON products (user_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_products_user_supplier ON products (user_id, supplier_id)",
        "CREATE INDEX IF NOT EXISTS idx_suppliers_user ON suppliers (user_id)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_history_user_created ON inventory_history (user_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_activity_logs_user_created ON activity_logs (user_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_recalc_history_user_created ON product_recalculation_history (user_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_margin_calculations_user_created ON margin_calculations (user_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_sell_stop_results_user_created ON sell_stop_results (user_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_price_history_user_created ON price_history (user_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_automation_rules_user ON price_automation_rules (user_id, product_id)",
        "CREATE INDEX IF NOT EXISTS idx_sourcing_user_created ON sourcing_items (user_id, created_at)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_user_order_no ON orders (user_id, order_no)",
        "CREATE INDEX IF NOT EXISTS idx_orders_user_status ON orders (user_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_purchase_user_status ON purchase_orders (user_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_shipments_user_status ON shipments (user_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_ai_drafts_user_created ON ai_drafts (user_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_after_sales_user_created ON after_sales_requests (user_id, requested_at)",
        "CREATE INDEX IF NOT EXISTS idx_after_sales_order ON after_sales_requests (user_id, order_id)",
    )
    for ddl in indexes:
        conn.execute(ddl)


def _migrate_users_plans(conn: sqlite3.Connection) -> None:
    columns = _table_columns(conn, "users")
    if "plan" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN plan TEXT NOT NULL DEFAULT 'free'")


def _migrate_users_tax_reserve(conn: sqlite3.Connection) -> None:
    columns = _table_columns(conn, "users")
    if "profit_tax_reserve_rate" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN profit_tax_reserve_rate REAL NOT NULL DEFAULT 10")
    if "income_tax_reserve_rate" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN income_tax_reserve_rate REAL NOT NULL DEFAULT 0")


def _migrate_one_click_purchase(conn: sqlite3.Connection) -> None:
    order_columns = _table_columns(conn, "orders")
    order_migrations = {
        "app_order_id": "ALTER TABLE orders ADD COLUMN app_order_id TEXT",
        "product_id": "ALTER TABLE orders ADD COLUMN product_id TEXT",
        "customer_id": "ALTER TABLE orders ADD COLUMN customer_id TEXT",
        "payment_status": "ALTER TABLE orders ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'PAID'",
    }
    for column, ddl in order_migrations.items():
        if column not in order_columns:
            conn.execute(ddl)
    purchase_columns = _table_columns(conn, "purchase_orders")
    purchase_migrations = {
        "validation_status": "ALTER TABLE purchase_orders ADD COLUMN validation_status TEXT",
        "prepared_payload": "ALTER TABLE purchase_orders ADD COLUMN prepared_payload TEXT",
        "prepared_at": "ALTER TABLE purchase_orders ADD COLUMN prepared_at TEXT",
        "checkout_url": "ALTER TABLE purchase_orders ADD COLUMN checkout_url TEXT",
    }
    for column, ddl in purchase_migrations.items():
        if column not in purchase_columns:
            conn.execute(ddl)
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_user_app_order ON orders (user_id, app_order_id) WHERE app_order_id IS NOT NULL AND app_order_id != ''")


def _migrate_sourcing_url_import(conn: sqlite3.Connection) -> None:
    columns = _table_columns(conn, "sourcing_items")
    migrations = {
        "source_platform": "ALTER TABLE sourcing_items ADD COLUMN source_platform TEXT",
        "source_product_id": "ALTER TABLE sourcing_items ADD COLUMN source_product_id TEXT",
        "source_currency": "ALTER TABLE sourcing_items ADD COLUMN source_currency TEXT",
        "import_status": "ALTER TABLE sourcing_items ADD COLUMN import_status TEXT",
        "imported_at": "ALTER TABLE sourcing_items ADD COLUMN imported_at TEXT",
        "options_json": "ALTER TABLE sourcing_items ADD COLUMN options_json TEXT",
        "supplier_store_name": "ALTER TABLE sourcing_items ADD COLUMN supplier_store_name TEXT",
        "supplier_store_url": "ALTER TABLE sourcing_items ADD COLUMN supplier_store_url TEXT",
        "image_urls_json": "ALTER TABLE sourcing_items ADD COLUMN image_urls_json TEXT",
    }
    for column, ddl in migrations.items():
        if column not in columns:
            conn.execute(ddl)



def _migrate_supplier_source_meta(conn: sqlite3.Connection) -> None:
    columns = _table_columns(conn, "suppliers")
    migrations = {
        "source_platform": "ALTER TABLE suppliers ADD COLUMN source_platform TEXT",
        "store_name": "ALTER TABLE suppliers ADD COLUMN store_name TEXT",
        "store_url": "ALTER TABLE suppliers ADD COLUMN store_url TEXT",
    }
    for column, ddl in migrations.items():
        if column not in columns:
            conn.execute(ddl)

def _migrate_products_v1_2(conn: sqlite3.Connection) -> None:
    columns = _table_columns(conn, "products")
    migrations = {
        "sku": "ALTER TABLE products ADD COLUMN sku TEXT",
        "main_image_url": "ALTER TABLE products ADD COLUMN main_image_url TEXT",
        "detail_image_url": "ALTER TABLE products ADD COLUMN detail_image_url TEXT",
        "status": "ALTER TABLE products ADD COLUMN status TEXT NOT NULL DEFAULT 'STOP'",
        "status_reason": "ALTER TABLE products ADD COLUMN status_reason TEXT NOT NULL DEFAULT '순이익 부족'",
        "purchase_price": "ALTER TABLE products ADD COLUMN purchase_price REAL NOT NULL DEFAULT 0",
        "international_shipping": "ALTER TABLE products ADD COLUMN international_shipping REAL NOT NULL DEFAULT 0",
        "domestic_shipping": "ALTER TABLE products ADD COLUMN domestic_shipping REAL NOT NULL DEFAULT 0",
        "selling_price": "ALTER TABLE products ADD COLUMN selling_price REAL NOT NULL DEFAULT 0",
        "fee_rate": "ALTER TABLE products ADD COLUMN fee_rate REAL NOT NULL DEFAULT 0",
        "total_cost": "ALTER TABLE products ADD COLUMN total_cost REAL NOT NULL DEFAULT 0",
        "fee_amount": "ALTER TABLE products ADD COLUMN fee_amount REAL NOT NULL DEFAULT 0",
        "vat_amount": "ALTER TABLE products ADD COLUMN vat_amount REAL NOT NULL DEFAULT 0",
        "net_profit": "ALTER TABLE products ADD COLUMN net_profit REAL NOT NULL DEFAULT 0",
        "margin_rate": "ALTER TABLE products ADD COLUMN margin_rate REAL NOT NULL DEFAULT 0",
        "last_recalculated_at": "ALTER TABLE products ADD COLUMN last_recalculated_at TEXT",
    }
    for column, ddl in migrations.items():
        if column not in columns:
            conn.execute(ddl)

    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_products_user_sku
        ON products (user_id, sku)
        WHERE sku IS NOT NULL AND sku != ''
        """
    )




def _migrate_sell_stop_two_state(conn: sqlite3.Connection) -> None:
    """기존 3단계 판매판단 데이터를 2단계(SELL/STOP)로 일회성 정리합니다."""
    conn.execute(
        """
        UPDATE products
        SET status = CASE
            WHEN COALESCE(selling_price, 0) > 0 AND COALESCE(net_profit, 0) > 0 THEN 'SELL'
            ELSE 'STOP'
        END,
        status_reason = CASE
            WHEN COALESCE(selling_price, 0) <= 0 THEN '판매가 없음'
            WHEN COALESCE(net_profit, 0) <= 0 THEN '이익 없음'
            ELSE '판매 가능'
        END
        WHERE status NOT IN ('SELL', 'STOP')
        """
    )

def _migrate_inventory_v1(conn: sqlite3.Connection) -> None:
    inventory_columns = _table_columns(conn, "inventory")
    inventory_migrations = {
        "minimum_quantity": "ALTER TABLE inventory ADD COLUMN minimum_quantity INTEGER NOT NULL DEFAULT 0",
    }
    for column, ddl in inventory_migrations.items():
        if column not in inventory_columns:
            conn.execute(ddl)

    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_inventory_user_product
        ON inventory (user_id, product_id)
        """
    )


DEFAULT_ADMIN_EMAIL = "admin@b2b.local"
DEFAULT_ADMIN_PASSWORD = "admin123456"


def _seed_admin(conn: sqlite3.Connection) -> None:
    """앱 최초 실행/초기화 후 기본 관리자 계정을 보장합니다.

    이미 같은 이메일이 있으면 중복 생성하지 않고, V1 기본 관리자 계정으로
    로그인할 수 있도록 비밀번호/권한만 정상값으로 보정합니다.
    """
    exists = conn.execute(
        "SELECT id, password_hash, role, tax_type FROM users WHERE email = ? LIMIT 1",
        (DEFAULT_ADMIN_EMAIL,),
    ).fetchone()
    if exists:
        password_hash = exists["password_hash"]
        if not verify_password(DEFAULT_ADMIN_PASSWORD, password_hash) or is_legacy_password_hash(password_hash):
            password_hash = hash_password(DEFAULT_ADMIN_PASSWORD)
        conn.execute(
            """
            UPDATE users
            SET password_hash = ?, role = ?, tax_type = ?, plan = ?
            WHERE email = ?
            """,
            (password_hash, "admin", "general", "pro", DEFAULT_ADMIN_EMAIL),
        )
        return
    conn.execute(
        """
        INSERT INTO users (id, email, password_hash, role, tax_type, plan)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (str(uuid4()), DEFAULT_ADMIN_EMAIL, hash_password(DEFAULT_ADMIN_PASSWORD), "admin", "general", "pro"),
    )


def reset_test_data() -> None:
    """V1 테스트 데이터 초기화.

    삭제 순서:
    1) 재고 이력
    2) 재고
    3) 상품/계산/판매판단 데이터
    4) 기본 관리자 외 테스트 유저

    _connect 컨텍스트가 정상 종료 시 commit 하며, 마지막에 기본 관리자 계정을
    재생성/보정하여 admin@b2b.local 로그인을 보장합니다.
    """
    with _connect() as conn:
        for ddl in SCHEMAS.values():
            conn.execute(ddl)
        _migrate_products_v1_2(conn)
        _migrate_sell_stop_two_state(conn)
        _migrate_inventory_v1(conn)
        _migrate_query_indexes(conn)

        conn.execute("DELETE FROM inventory_history")
        conn.execute("DELETE FROM activity_logs")
        conn.execute("DELETE FROM product_recalculation_history")
        conn.execute("DELETE FROM inventory")
        conn.execute("DELETE FROM products")
        conn.execute("DELETE FROM suppliers")
        conn.execute("DELETE FROM margin_calculations")
        conn.execute("DELETE FROM sell_stop_results")
        conn.execute("DELETE FROM sourcing_items")
        conn.execute("DELETE FROM purchase_orders")
        conn.execute("DELETE FROM shipments")
        conn.execute("DELETE FROM price_trackers")
        conn.execute("DELETE FROM ai_drafts")
        conn.execute("DELETE FROM after_sales_requests")
        conn.execute("DELETE FROM orders")
        conn.execute("DELETE FROM users WHERE email != ?", (DEFAULT_ADMIN_EMAIL,))

        _seed_admin(conn)
        conn.commit()


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def _parse_filter(value: str):
    if isinstance(value, str) and value.startswith("eq."):
        return value[3:]
    return value


def _build_where(params: dict | None, columns: set[str]):
    where = []
    values = []
    if not params:
        return where, values
    for key, value in params.items():
        if key in {"limit", "order", "select"} or key not in columns:
            continue
        where.append(f"{key} = ?")
        values.append(_parse_filter(value))
    return where, values


async def select(table: str, params: dict | None = None):
    init_db()
    params = params or {}
    with _connect() as conn:
        columns = _table_columns(conn, table)
        where, values = _build_where(params, columns)
        query = f"SELECT * FROM {table}"
        if where:
            query += " WHERE " + " AND ".join(where)

        order = params.get("order")
        if order:
            pieces = str(order).split(".")
            col = pieces[0]
            direction = "DESC" if len(pieces) > 1 and pieces[1].lower() == "desc" else "ASC"
            if col in columns:
                query += f" ORDER BY {col} {direction}"

        limit = params.get("limit")
        if limit:
            query += " LIMIT ?"
            values.append(int(limit))

        rows = conn.execute(query, values).fetchall()
        return [_row_to_dict(row) for row in rows]


async def insert(table: str, data: dict):
    init_db()
    payload = dict(data)
    payload.setdefault("id", str(uuid4()))
    with _connect() as conn:
        columns = _table_columns(conn, table)
        payload = {key: value for key, value in payload.items() if key in columns}
        keys = list(payload.keys())
        placeholders = ", ".join(["?"] * len(keys))
        conn.execute(
            f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({placeholders})",
            [payload[key] for key in keys],
        )
        row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (payload["id"],)).fetchone()
        return [_row_to_dict(row)] if row else []


async def update(table: str, params: dict, data: dict):
    init_db()
    with _connect() as conn:
        columns = _table_columns(conn, table)
        payload = {key: value for key, value in data.items() if key in columns and key != "id"}
        if not payload:
            return []
        where, values = _build_where(params, columns)
        if not where:
            return []
        set_clause = ", ".join([f"{key} = ?" for key in payload])
        conn.execute(
            f"UPDATE {table} SET {set_clause} WHERE {' AND '.join(where)}",
            list(payload.values()) + values,
        )
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE {' AND '.join(where)}",
            values,
        ).fetchall()
        return [_row_to_dict(row) for row in rows]


async def delete(table: str, params: dict):
    init_db()
    with _connect() as conn:
        columns = _table_columns(conn, table)
        where, values = _build_where(params, columns)
        if not where:
            return []
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE {' AND '.join(where)}",
            values,
        ).fetchall()
        conn.execute(f"DELETE FROM {table} WHERE {' AND '.join(where)}", values)
        return [_row_to_dict(row) for row in rows]
