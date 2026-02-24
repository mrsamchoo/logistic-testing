import sqlite3
import os
import json
import random
import string
import secrets
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "shipping.db")
RATES_PATH = os.path.join(os.path.dirname(__file__), "config", "rates.json")

STATUS_MAP = {
    "pending": "รอรับพัสดุ",
    "picked_up": "รับพัสดุแล้ว",
    "in_transit": "กำลังจัดส่ง",
    "customs": "ผ่านศุลกากร",
    "delivered": "จัดส่งสำเร็จ",
}

STATUS_ORDER = ["pending", "picked_up", "in_transit", "customs", "delivered"]

PORTS = ["LAX", "SEA", "JFK", "MIA"]

TIERS = ["bronze", "gold", "vip"]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    config_dir = os.path.dirname(RATES_PATH)
    os.makedirs(config_dir, exist_ok=True)
    if not os.path.exists(RATES_PATH):
        default_rates = {
            "tiers": {
                "bronze": {"rate": 700, "label": "Bronze", "label_th": "บรอนซ์"},
                "gold": {"rate": 675, "label": "Gold", "label_th": "โกลด์"},
                "vip": {"rate": 625, "label": "VIP", "label_th": "VIP"},
            },
            "currency": "THB",
            "unit": "kg",
            "updated_at": None,
            "updated_by": None,
        }
        with open(RATES_PATH, "w", encoding="utf-8") as f:
            json.dump(default_rates, f, indent=4, ensure_ascii=False)

    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_code TEXT UNIQUE NOT NULL,
            sea_code TEXT UNIQUE DEFAULT '',
            email TEXT DEFAULT '',
            password_hash TEXT DEFAULT '',
            tier TEXT DEFAULT 'bronze',
            custom_rate REAL DEFAULT NULL,
            sender_first_name TEXT NOT NULL,
            sender_last_name TEXT NOT NULL,
            sender_address TEXT NOT NULL,
            sender_phone TEXT NOT NULL,
            receiver_first_name TEXT NOT NULL,
            receiver_last_name TEXT NOT NULL,
            receiver_address TEXT NOT NULL,
            receiver_phone TEXT NOT NULL,
            reset_token TEXT DEFAULT NULL,
            reset_token_expiry TIMESTAMP DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS shipments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_number TEXT UNIQUE NOT NULL,
            customer_code TEXT NOT NULL,
            description TEXT DEFAULT '',
            weight TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            photos TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_code) REFERENCES customers(customer_code)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS rate_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            customer_code TEXT,
            requested_rate REAL NOT NULL,
            reason TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            reviewed_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP,
            FOREIGN KEY (admin_id) REFERENCES admins(id),
            FOREIGN KEY (reviewed_by) REFERENCES admins(id)
        )
    """)

    # --- Migrations ---
    cust_columns = [row[1] for row in conn.execute("PRAGMA table_info(customers)").fetchall()]
    for col, default in [("sea_code", "''"), ("tier", "'bronze'"), ("custom_rate", "NULL"),
                         ("email", "''"), ("password_hash", "''"),
                         ("reset_token", "NULL"), ("reset_token_expiry", "NULL")]:
        if col not in cust_columns:
            conn.execute(f"ALTER TABLE customers ADD COLUMN {col} TEXT DEFAULT {default}")

    ship_columns = [row[1] for row in conn.execute("PRAGMA table_info(shipments)").fetchall()]
    if "port" not in ship_columns:
        conn.execute("ALTER TABLE shipments ADD COLUMN port TEXT DEFAULT ''")
    if "photos" not in ship_columns:
        conn.execute("ALTER TABLE shipments ADD COLUMN photos TEXT DEFAULT ''")

    existing_admin = conn.execute("SELECT 1 FROM admins WHERE username = 'admin'").fetchone()
    if not existing_admin:
        conn.execute(
            "INSERT INTO admins (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", generate_password_hash("admin123"), "super_admin"),
        )

    conn.commit()
    conn.close()


# ============================================================
# Rate Configuration (JSON file)
# ============================================================


def load_rates():
    with open(RATES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_rates(rates_data):
    rates_data["updated_at"] = datetime.now().isoformat()
    with open(RATES_PATH, "w", encoding="utf-8") as f:
        json.dump(rates_data, f, indent=4, ensure_ascii=False)


def get_customer_rate(customer_code):
    conn = get_db()
    customer = conn.execute(
        "SELECT tier, custom_rate FROM customers WHERE customer_code = ? OR sea_code = ?",
        (customer_code, customer_code),
    ).fetchone()
    conn.close()
    if not customer:
        return None, None, None
    rates = load_rates()
    tier = customer["tier"] or "bronze"
    tier_rate = rates["tiers"].get(tier, {}).get("rate", 700)
    effective_rate = customer["custom_rate"] if customer["custom_rate"] is not None else tier_rate
    return tier, tier_rate, effective_rate


# ============================================================
# Admin Operations
# ============================================================


def get_admin_by_credentials(username, password):
    conn = get_db()
    admin = conn.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
    conn.close()
    if admin and check_password_hash(admin["password_hash"], password):
        return admin
    return None


def get_admin_by_id(admin_id):
    conn = get_db()
    admin = conn.execute("SELECT * FROM admins WHERE id = ?", (admin_id,)).fetchone()
    conn.close()
    return admin


def get_all_admins():
    conn = get_db()
    admins = conn.execute("SELECT id, username, role, created_at FROM admins ORDER BY created_at").fetchall()
    conn.close()
    return admins


def add_admin(username, password, role="admin"):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO admins (username, password_hash, role) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), role),
        )
        conn.commit()
        return True, f"เพิ่ม admin '{username}' สำเร็จ"
    except sqlite3.IntegrityError:
        return False, "Username นี้มีอยู่แล้ว"
    finally:
        conn.close()


def delete_admin(admin_id):
    conn = get_db()
    conn.execute("DELETE FROM admins WHERE id = ?", (admin_id,))
    conn.commit()
    conn.close()


# ============================================================
# Rate Requests
# ============================================================


def add_rate_request(admin_id, customer_code, requested_rate, reason=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO rate_requests (admin_id, customer_code, requested_rate, reason) VALUES (?, ?, ?, ?)",
        (admin_id, customer_code, requested_rate, reason),
    )
    conn.commit()
    conn.close()


def get_pending_requests():
    conn = get_db()
    reqs = conn.execute(
        """SELECT r.*, a.username AS requester_name
           FROM rate_requests r JOIN admins a ON r.admin_id = a.id
           WHERE r.status = 'pending' ORDER BY r.created_at DESC""",
    ).fetchall()
    conn.close()
    return reqs


def get_all_rate_requests():
    conn = get_db()
    reqs = conn.execute(
        """SELECT r.*, a.username AS requester_name
           FROM rate_requests r JOIN admins a ON r.admin_id = a.id
           ORDER BY r.created_at DESC""",
    ).fetchall()
    conn.close()
    return reqs


def review_rate_request(request_id, reviewer_id, action):
    conn = get_db()
    conn.execute(
        "UPDATE rate_requests SET status = ?, reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (action, reviewer_id, request_id),
    )
    if action == "approved":
        req = conn.execute("SELECT * FROM rate_requests WHERE id = ?", (request_id,)).fetchone()
        if req and req["customer_code"]:
            conn.execute(
                "UPDATE customers SET custom_rate = ? WHERE customer_code = ?",
                (req["requested_rate"], req["customer_code"]),
            )
    conn.commit()
    conn.close()


# ============================================================
# Code Generators
# ============================================================


def generate_customer_code():
    conn = get_db()
    while True:
        code = f"US{random.randint(10000, 99999)}"
        exists = conn.execute("SELECT 1 FROM customers WHERE customer_code = ?", (code,)).fetchone()
        if not exists:
            conn.close()
            return code


def generate_sea_code():
    conn = get_db()
    while True:
        code = f"USS{random.randint(10000, 99999)}"
        exists = conn.execute("SELECT 1 FROM customers WHERE sea_code = ?", (code,)).fetchone()
        if not exists:
            conn.close()
            return code


def generate_tracking_number():
    conn = get_db()
    while True:
        date_str = datetime.now().strftime("%Y%m%d")
        letter = random.choice(string.ascii_uppercase)
        digits = f"{random.randint(0, 999):03d}"
        tracking = f"TH{date_str}{letter}{digits}"
        exists = conn.execute("SELECT 1 FROM shipments WHERE tracking_number = ?", (tracking,)).fetchone()
        if not exists:
            conn.close()
            return tracking


# ============================================================
# Customer Operations
# ============================================================


def add_customer(sender_first_name, sender_last_name, sender_address, sender_phone,
                 receiver_first_name, receiver_last_name, receiver_address, receiver_phone,
                 email="", password=""):
    air_code = generate_customer_code()
    sea_code = generate_sea_code()
    pw_hash = generate_password_hash(password) if password else ""
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO customers
               (customer_code, sea_code, email, password_hash, tier,
                sender_first_name, sender_last_name, sender_address, sender_phone,
                receiver_first_name, receiver_last_name, receiver_address, receiver_phone)
               VALUES (?, ?, ?, ?, 'bronze', ?, ?, ?, ?, ?, ?, ?, ?)""",
            (air_code, sea_code, email, pw_hash,
             sender_first_name, sender_last_name, sender_address, sender_phone,
             receiver_first_name, receiver_last_name, receiver_address, receiver_phone),
        )
        conn.commit()
        return True, air_code
    except sqlite3.IntegrityError:
        return False, "เกิดข้อผิดพลาด กรุณาลองใหม่"
    finally:
        conn.close()


def get_customer_by_code(customer_code):
    conn = get_db()
    customer = conn.execute(
        "SELECT * FROM customers WHERE customer_code = ? OR sea_code = ?",
        (customer_code, customer_code),
    ).fetchone()
    conn.close()
    return customer


def get_customer_by_credentials(code, password):
    """Verify customer login: code + password."""
    conn = get_db()
    customer = conn.execute(
        "SELECT * FROM customers WHERE customer_code = ? OR sea_code = ?",
        (code, code),
    ).fetchone()
    conn.close()
    if customer and customer["password_hash"] and check_password_hash(customer["password_hash"], password):
        return customer
    return None


def get_customer_by_email(email):
    conn = get_db()
    customer = conn.execute("SELECT * FROM customers WHERE email = ?", (email,)).fetchone()
    conn.close()
    return customer


def create_reset_token(email):
    """Generate reset token, store it, return (token, customer) or (None, None)."""
    customer = get_customer_by_email(email)
    if not customer:
        return None, None
    token = secrets.token_urlsafe(32)
    expiry = (datetime.now() + timedelta(hours=1)).isoformat()
    conn = get_db()
    conn.execute(
        "UPDATE customers SET reset_token = ?, reset_token_expiry = ? WHERE id = ?",
        (token, expiry, customer["id"]),
    )
    conn.commit()
    conn.close()
    return token, customer


def verify_reset_token(token):
    conn = get_db()
    customer = conn.execute("SELECT * FROM customers WHERE reset_token = ?", (token,)).fetchone()
    conn.close()
    if not customer:
        return None
    expiry = customer["reset_token_expiry"]
    if expiry and datetime.fromisoformat(expiry) > datetime.now():
        return customer
    return None


def reset_customer_password(token, new_password):
    customer = verify_reset_token(token)
    if not customer:
        return False
    conn = get_db()
    conn.execute(
        "UPDATE customers SET password_hash = ?, reset_token = NULL, reset_token_expiry = NULL WHERE id = ?",
        (generate_password_hash(new_password), customer["id"]),
    )
    conn.commit()
    conn.close()
    return True


def get_all_customers(search=None):
    conn = get_db()
    query = "SELECT * FROM customers WHERE 1=1"
    params = []
    if search:
        term = f"%{search}%"
        query += " AND (customer_code LIKE ? OR sea_code LIKE ? OR sender_first_name LIKE ? OR sender_last_name LIKE ? OR receiver_first_name LIKE ? OR receiver_last_name LIKE ?)"
        params.extend([term, term, term, term, term, term])
    query += " ORDER BY created_at DESC"
    customers = conn.execute(query, params).fetchall()
    conn.close()
    return customers


def update_customer_tier(customer_code, tier, custom_rate=None):
    conn = get_db()
    conn.execute(
        "UPDATE customers SET tier = ?, custom_rate = ? WHERE customer_code = ?",
        (tier, custom_rate, customer_code),
    )
    conn.commit()
    conn.close()


# ============================================================
# Shipment Operations
# ============================================================


def add_shipment(customer_code, description="", weight=""):
    tracking = generate_tracking_number()
    conn = get_db()
    conn.execute(
        "INSERT INTO shipments (tracking_number, customer_code, description, weight) VALUES (?, ?, ?, ?)",
        (tracking, customer_code, description, weight),
    )
    conn.commit()
    conn.close()
    return tracking


def get_shipments_by_customer(customer_code, limit=5):
    conn = get_db()
    shipments = conn.execute(
        "SELECT * FROM shipments WHERE customer_code = ? ORDER BY created_at DESC LIMIT ?",
        (customer_code, limit),
    ).fetchall()
    conn.close()
    return shipments


def get_shipment_by_tracking(tracking_number):
    conn = get_db()
    shipment = conn.execute(
        """SELECT s.*, c.sender_first_name, c.sender_last_name,
                  c.receiver_first_name, c.receiver_last_name
           FROM shipments s
           JOIN customers c ON s.customer_code = c.customer_code
           WHERE s.tracking_number = ?""",
        (tracking_number,),
    ).fetchone()
    conn.close()
    return shipment


def get_all_shipments(search=None, status_filter=None):
    conn = get_db()
    query = """SELECT s.*, c.sender_first_name, c.sender_last_name,
                      c.receiver_first_name, c.receiver_last_name
               FROM shipments s
               JOIN customers c ON s.customer_code = c.customer_code
               WHERE 1=1"""
    params = []
    if status_filter and status_filter != "all":
        query += " AND s.status = ?"
        params.append(status_filter)
    if search:
        term = f"%{search}%"
        query += " AND (s.tracking_number LIKE ? OR s.customer_code LIKE ?)"
        params.extend([term, term])
    query += " ORDER BY s.updated_at DESC"
    shipments = conn.execute(query, params).fetchall()
    conn.close()
    return shipments


def update_shipment_status(shipment_id, new_status):
    conn = get_db()
    conn.execute(
        "UPDATE shipments SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_status, shipment_id),
    )
    conn.commit()
    conn.close()


def bulk_update_shipment_status(shipment_ids, new_status):
    if not shipment_ids:
        return
    conn = get_db()
    placeholders = ",".join("?" for _ in shipment_ids)
    conn.execute(
        f"UPDATE shipments SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
        [new_status] + list(shipment_ids),
    )
    conn.commit()
    conn.close()


# ============================================================
# Mock Data
# ============================================================


def seed_mock_shipments(customer_code):
    mock_data = [
        ("กล่องเสื้อผ้า", "delivered", "0.5 kg", -10, "LAX",
         "https://picsum.photos/seed/pkg1/400/300,https://picsum.photos/seed/pkg1b/400/300"),
        ("อุปกรณ์อิเล็กทรอนิกส์", "delivered", "1.2 kg", -7, "JFK",
         "https://picsum.photos/seed/pkg2/400/300,https://picsum.photos/seed/pkg2b/400/300,https://picsum.photos/seed/pkg2c/400/300"),
        ("เครื่องสำอาง", "customs", "0.3 kg", -4, "SEA",
         "https://picsum.photos/seed/pkg3/400/300"),
        ("หนังสือและของขวัญ", "in_transit", "2.0 kg", -2, "MIA", ""),
        ("อาหารแห้ง", "pending", "1.5 kg", 0, "LAX", ""),
    ]
    conn = get_db()
    for desc, status, weight, days_offset, port, photos in mock_data:
        tracking = generate_tracking_number()
        conn.execute(
            f"""INSERT INTO shipments
                (tracking_number, customer_code, description, status, weight, port, photos,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?,
                        datetime('now', '{days_offset} days'),
                        datetime('now', '{days_offset} days'))""",
            (tracking, customer_code, desc, status, weight, port, photos),
        )
    conn.commit()
    conn.close()


# ============================================================
# Stats
# ============================================================


def get_stats():
    conn = get_db()
    total_customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    total_shipments = conn.execute("SELECT COUNT(*) FROM shipments").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM shipments WHERE status = 'pending'").fetchone()[0]
    in_transit = conn.execute("SELECT COUNT(*) FROM shipments WHERE status IN ('picked_up', 'in_transit', 'customs')").fetchone()[0]
    delivered = conn.execute("SELECT COUNT(*) FROM shipments WHERE status = 'delivered'").fetchone()[0]
    conn.close()
    return {
        "total_customers": total_customers,
        "total_shipments": total_shipments,
        "pending": pending,
        "in_transit": in_transit,
        "delivered": delivered,
    }
