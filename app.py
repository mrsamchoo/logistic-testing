import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_socketio import SocketIO
from dotenv import load_dotenv
from database import (
    init_db, add_customer, get_customer_by_code, get_all_customers,
    get_shipments_by_customer, get_shipment_by_tracking,
    get_all_shipments, update_shipment_status, bulk_update_shipment_status,
    get_stats, STATUS_MAP, PORTS, TIERS,
    get_admin_by_credentials, get_admin_by_id, get_all_admins,
    add_admin, delete_admin, update_customer_tier,
    load_rates, save_rates, get_customer_rate,
    add_rate_request, get_pending_requests, get_all_rate_requests, review_rate_request,
    get_customer_by_credentials, get_customer_by_email,
    create_reset_token, verify_reset_token, reset_customer_password,
    add_customer_address, get_customer_addresses, get_address_by_id,
    update_customer_address, delete_customer_address, get_address_count,
    set_shipment_destination, admin_set_shipment_destination,
    seed_mock_addresses, LOCATION_TYPES, US_CITIES, MAX_ADDRESSES,
    get_db,
    add_inbound_package, get_inbound_by_customer, get_inbound_by_id,
    delete_inbound_package, get_all_inbound_packages, update_inbound_status,
    INBOUND_CARRIERS, INBOUND_STATUS_MAP,
    update_customer_info, admin_reset_customer_password,
    deactivate_customer, activate_customer, add_shipment,
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "shipping-secret-key-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Register messaging blueprint
from messaging import messaging_bp
app.register_blueprint(messaging_bp)

# Register SocketIO events
from messaging.socketio_events import register_socketio_events
register_socketio_events(socketio)


# ============================================================
# JSON error handlers for API routes (prevent HTML error pages)
# ============================================================
from flask import jsonify as _jsonify


@app.errorhandler(413)
def request_entity_too_large(error):
    """Return JSON for file-too-large errors instead of HTML."""
    if request.path.startswith("/api/"):
        return _jsonify({"error": "File too large. Maximum 16 MB."}), 413
    return "File too large", 413


@app.errorhandler(500)
def internal_server_error(error):
    """Return JSON for API 500 errors instead of HTML."""
    if request.path.startswith("/api/"):
        return _jsonify({"error": "Internal server error"}), 500
    return "Internal server error", 500


# ============================================================
# Auth Decorators
# ============================================================


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


def super_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login"))
        if session.get("admin_role") != "super_admin":
            flash("คุณไม่มีสิทธิ์เข้าถึงหน้านี้", "error")
            return redirect(url_for("admin_dashboard"))
        return f(*args, **kwargs)
    return decorated


# ============================================================
# Context Processor — inject admin info into all templates
# ============================================================


@app.context_processor
def inject_admin_context():
    ctx = {}
    if session.get("admin_id"):
        ctx["admin_role"] = session.get("admin_role")
        ctx["admin_username"] = session.get("admin_username")
        ctx["pending_request_count"] = len(get_pending_requests())
    return ctx


# ============================================================
# Homepage
# ============================================================


@app.route("/")
def home():
    customer_code = session.get("customer_code")
    customer = None
    shipments = []
    if customer_code:
        customer = get_customer_by_code(customer_code)
        if customer:
            shipments = get_shipments_by_customer(customer_code)
    return render_template("home.html", customer=customer, shipments=shipments, STATUS_MAP=STATUS_MAP)


# ============================================================
# Registration
# ============================================================


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        location_type = request.form.get("location_type", "").strip()
        city = request.form.get("city", "").strip()

        if location_type not in ("us", "th"):
            flash("กรุณาเลือกว่าคุณอยู่ที่ไหน", "error")
            return redirect(url_for("register"))

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not email or not password:
            flash("กรุณากรอกอีเมลและรหัสผ่าน", "error")
            return redirect(url_for("register"))
        if password != confirm_password:
            flash("รหัสผ่านไม่ตรงกัน กรุณาลองใหม่", "error")
            return redirect(url_for("register"))
        if len(password) < 6:
            flash("รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร", "error")
            return redirect(url_for("register"))

        existing = get_customer_by_email(email)
        if existing:
            flash("อีเมลนี้ถูกใช้งานแล้ว", "error")
            return redirect(url_for("register"))

        # Sender info (US customers only)
        sender_first_name = ""
        sender_last_name = ""
        sender_address = ""
        sender_phone = ""
        if location_type == "us":
            if not city or city not in US_CITIES:
                flash("กรุณาเลือกเมืองที่คุณอยู่", "error")
                return redirect(url_for("register"))
            sender_first_name = request.form.get("sender_first_name", "").strip()
            sender_last_name = request.form.get("sender_last_name", "").strip()
            sender_address = request.form.get("sender_address", "").strip()
            sender_phone = request.form.get("sender_phone", "").strip()
            if not all([sender_first_name, sender_last_name, sender_address, sender_phone]):
                flash("กรุณากรอกข้อมูลผู้ส่งให้ครบ", "error")
                return redirect(url_for("register"))

        # At least one destination address required
        addr_nickname = request.form.get("addr_nickname_1", "").strip()
        addr_first = request.form.get("addr_first_name_1", "").strip()
        addr_last = request.form.get("addr_last_name_1", "").strip()
        addr_address = request.form.get("addr_address_1", "").strip()
        addr_phone = request.form.get("addr_phone_1", "").strip()

        if not all([addr_first, addr_last, addr_address, addr_phone]):
            flash("กรุณากรอกที่อยู่ปลายทางอย่างน้อย 1 รายการ", "error")
            return redirect(url_for("register"))

        success, result, customer_id = add_customer(
            location_type=location_type, city=city,
            sender_first_name=sender_first_name, sender_last_name=sender_last_name,
            sender_address=sender_address, sender_phone=sender_phone,
            email=email, password=password,
        )
        if success:
            customer_code = result
            add_customer_address(
                customer_id, addr_nickname or "ที่อยู่หลัก",
                addr_first, addr_last, addr_address, addr_phone, is_default=1,
            )
            for i in range(2, 4):
                extra_first = request.form.get(f"addr_first_name_{i}", "").strip()
                extra_last = request.form.get(f"addr_last_name_{i}", "").strip()
                extra_addr = request.form.get(f"addr_address_{i}", "").strip()
                extra_phone = request.form.get(f"addr_phone_{i}", "").strip()
                extra_nick = request.form.get(f"addr_nickname_{i}", "").strip()
                if all([extra_first, extra_last, extra_addr, extra_phone]):
                    add_customer_address(customer_id, extra_nick or f"ที่อยู่ {i}",
                                         extra_first, extra_last, extra_addr, extra_phone)

            session["customer_code"] = customer_code
            return redirect(url_for("register_success", code=customer_code))
        else:
            flash(result, "error")
            return redirect(url_for("register"))

    return render_template("register.html", US_CITIES=US_CITIES)


@app.route("/register/success/<code>")
def register_success(code):
    customer = get_customer_by_code(code)
    if not customer:
        flash("ไม่พบรหัสลูกค้า", "error")
        return redirect(url_for("register"))
    addresses = get_customer_addresses(customer["id"])
    return render_template("register_success.html", customer=customer, addresses=addresses,
                           US_CITIES=US_CITIES)


# ============================================================
# Customer
# ============================================================


@app.route("/customer", methods=["GET", "POST"])
def customer_login():
    if request.method == "POST":
        code = request.form.get("customer_code", "").strip().upper()
        password = request.form.get("password", "").strip()
        result = get_customer_by_credentials(code, password)
        if result == "inactive":
            flash("บัญชีของคุณถูกปิดใช้งาน กรุณาติดต่อแอดมิน", "error")
            return redirect(url_for("customer_login"))
        if result:
            air_code = result["customer_code"]
            # ล้าง admin session ออกเมื่อลูกค้าล็อกอิน
            session.pop("admin_id", None)
            session.pop("admin_role", None)
            session.pop("admin_username", None)
            session["customer_code"] = air_code
            return redirect(url_for("customer_portal", code=air_code))
        else:
            flash("รหัสลูกค้าหรือรหัสผ่านไม่ถูกต้อง", "error")
            return redirect(url_for("customer_login"))
    return render_template("customer_login.html")


@app.route("/customer/<code>")
def customer_portal(code):
    customer = get_customer_by_code(code)
    if not customer:
        flash("ไม่พบรหัสลูกค้า", "error")
        return redirect(url_for("customer_login"))
    shipments = get_shipments_by_customer(customer["customer_code"], limit=10)
    addresses = get_customer_addresses(customer["id"])
    inbound_packages = get_inbound_by_customer(customer["customer_code"])
    tier, tier_rate, effective_rate = get_customer_rate(customer["customer_code"])
    rates = load_rates()
    return render_template("customer_portal.html", customer=customer, shipments=shipments,
                           addresses=addresses, STATUS_MAP=STATUS_MAP,
                           inbound_packages=inbound_packages,
                           INBOUND_CARRIERS=INBOUND_CARRIERS,
                           INBOUND_STATUS_MAP=INBOUND_STATUS_MAP,
                           tier=tier, effective_rate=effective_rate, rates=rates,
                           US_CITIES=US_CITIES, MAX_ADDRESSES=MAX_ADDRESSES)


@app.route("/customer/logout")
def customer_logout():
    session.pop("customer_code", None)
    return redirect(url_for("home"))


# ============================================================
# Customer Address Management
# ============================================================


@app.route("/customer/<code>/address/add", methods=["POST"])
def customer_add_address(code):
    if session.get("customer_code") != code:
        flash("กรุณาเข้าสู่ระบบ", "error")
        return redirect(url_for("customer_login"))
    customer = get_customer_by_code(code)
    if not customer:
        return redirect(url_for("customer_login"))
    if get_address_count(customer["id"]) >= MAX_ADDRESSES:
        flash(f"ที่อยู่ครบ {MAX_ADDRESSES} รายการแล้ว", "error")
        return redirect(url_for("customer_portal", code=code))
    nickname = request.form.get("nickname", "").strip()
    first_name = request.form.get("receiver_first_name", "").strip()
    last_name = request.form.get("receiver_last_name", "").strip()
    address = request.form.get("receiver_address", "").strip()
    phone = request.form.get("receiver_phone", "").strip()
    if not all([first_name, last_name, address, phone]):
        flash("กรุณากรอกข้อมูลที่อยู่ให้ครบ", "error")
        return redirect(url_for("customer_portal", code=code))
    add_customer_address(customer["id"], nickname or "ที่อยู่ใหม่", first_name, last_name, address, phone)
    flash("เพิ่มที่อยู่ปลายทางสำเร็จ", "success")
    return redirect(url_for("customer_portal", code=code))


@app.route("/customer/<code>/address/<int:address_id>/edit", methods=["POST"])
def customer_edit_address(code, address_id):
    if session.get("customer_code") != code:
        return redirect(url_for("customer_login"))
    customer = get_customer_by_code(code)
    addr = get_address_by_id(address_id)
    if not customer or not addr or addr["customer_id"] != customer["id"]:
        flash("ไม่พบที่อยู่", "error")
        return redirect(url_for("customer_portal", code=code))
    nickname = request.form.get("nickname", "").strip()
    first_name = request.form.get("receiver_first_name", "").strip()
    last_name = request.form.get("receiver_last_name", "").strip()
    address = request.form.get("receiver_address", "").strip()
    phone = request.form.get("receiver_phone", "").strip()
    if not all([first_name, last_name, address, phone]):
        flash("กรุณากรอกข้อมูลให้ครบ", "error")
        return redirect(url_for("customer_portal", code=code))
    update_customer_address(address_id, nickname, first_name, last_name, address, phone)
    flash("แก้ไขที่อยู่สำเร็จ", "success")
    return redirect(url_for("customer_portal", code=code))


@app.route("/customer/<code>/address/<int:address_id>/delete", methods=["POST"])
def customer_delete_address(code, address_id):
    if session.get("customer_code") != code:
        return redirect(url_for("customer_login"))
    customer = get_customer_by_code(code)
    addr = get_address_by_id(address_id)
    if not customer or not addr or addr["customer_id"] != customer["id"]:
        flash("ไม่พบที่อยู่", "error")
        return redirect(url_for("customer_portal", code=code))
    if get_address_count(customer["id"]) <= 1:
        flash("ต้องมีที่อยู่ปลายทางอย่างน้อย 1 รายการ", "error")
        return redirect(url_for("customer_portal", code=code))
    delete_customer_address(address_id)
    flash("ลบที่อยู่สำเร็จ", "success")
    return redirect(url_for("customer_portal", code=code))


@app.route("/customer/<code>/shipment/<int:shipment_id>/set-address", methods=["POST"])
def customer_set_shipment_address(code, shipment_id):
    if session.get("customer_code") != code:
        return redirect(url_for("customer_login"))
    customer = get_customer_by_code(code)
    if not customer:
        return redirect(url_for("customer_login"))
    conn = get_db()
    shipment = conn.execute("SELECT * FROM shipments WHERE id = ? AND customer_code = ?",
                            (shipment_id, customer["customer_code"])).fetchone()
    conn.close()
    if not shipment:
        flash("ไม่พบพัสดุ", "error")
        return redirect(url_for("customer_portal", code=code))
    if shipment["address_locked_by_customer"]:
        flash("คุณเลือกที่อยู่ปลายทางแล้ว ไม่สามารถเปลี่ยนได้ กรุณาติดต่อแอดมิน", "error")
        return redirect(url_for("customer_portal", code=code))
    address_id = request.form.get("address_id")
    if not address_id:
        flash("กรุณาเลือกที่อยู่ปลายทาง", "error")
        return redirect(url_for("customer_portal", code=code))
    addr = get_address_by_id(int(address_id))
    if not addr or addr["customer_id"] != customer["id"]:
        flash("ที่อยู่ไม่ถูกต้อง", "error")
        return redirect(url_for("customer_portal", code=code))
    set_shipment_destination(shipment_id, int(address_id), locked_by_customer=True)
    flash("เลือกที่อยู่ปลายทางสำเร็จ", "success")
    return redirect(url_for("customer_portal", code=code))


# ============================================================
# Customer Inbound Packages
# ============================================================


@app.route("/customer/<code>/inbound/add", methods=["POST"])
def customer_add_inbound(code):
    if session.get("customer_code") != code:
        flash("กรุณาเข้าสู่ระบบ", "error")
        return redirect(url_for("customer_login"))
    customer = get_customer_by_code(code)
    if not customer:
        return redirect(url_for("customer_login"))
    carrier = request.form.get("carrier", "").strip()
    tracking = request.form.get("carrier_tracking_number", "").strip()
    description = request.form.get("description", "").strip()
    if not carrier or not tracking:
        flash("กรุณากรอกข้อมูลให้ครบ", "error")
        return redirect(url_for("customer_portal", code=code))
    if carrier not in INBOUND_CARRIERS:
        flash("กรุณาเลือกขนส่งที่ถูกต้อง", "error")
        return redirect(url_for("customer_portal", code=code))
    add_inbound_package(customer["customer_code"], carrier, tracking, description)
    flash("แจ้งพัสดุขาเข้าสำเร็จ", "success")
    return redirect(url_for("customer_portal", code=code))


@app.route("/customer/<code>/inbound/<int:inbound_id>/delete", methods=["POST"])
def customer_delete_inbound(code, inbound_id):
    if session.get("customer_code") != code:
        return redirect(url_for("customer_login"))
    customer = get_customer_by_code(code)
    if not customer:
        return redirect(url_for("customer_login"))
    package = get_inbound_by_id(inbound_id)
    if not package or package["customer_code"] != customer["customer_code"]:
        flash("ไม่พบพัสดุ", "error")
        return redirect(url_for("customer_portal", code=code))
    if package["status"] in ("received", "processing"):
        flash("ไม่สามารถลบพัสดุที่รับแล้วได้", "error")
        return redirect(url_for("customer_portal", code=code))
    delete_inbound_package(inbound_id)
    flash("ลบพัสดุขาเข้าสำเร็จ", "success")
    return redirect(url_for("customer_portal", code=code))


# ============================================================
# Forgot / Reset Password
# ============================================================


@app.route("/customer/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if not email:
            flash("กรุณากรอกอีเมล", "error")
            return redirect(url_for("forgot_password"))

        token, customer = create_reset_token(email)
        if token:
            # In production: send email with reset link
            # For dev: show the link directly
            reset_url = url_for("reset_password", token=token, _external=True)
            flash(f"ลิงก์รีเซ็ตรหัสผ่านถูกส่งไปที่อีเมล {email} แล้ว (ใช้ได้ภายใน 1 ชม.)", "success")
            # DEV MODE: flash the link so user can test
            flash(f"[DEV] Reset link: {reset_url}", "info")
        else:
            flash("ไม่พบอีเมลนี้ในระบบ กรุณาตรวจสอบอีกครั้ง", "error")

        return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html")


@app.route("/customer/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    customer = verify_reset_token(token)
    if not customer:
        flash("ลิงก์รีเซ็ตไม่ถูกต้องหรือหมดอายุแล้ว", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()
        if not password or len(password) < 6:
            flash("รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร", "error")
            return redirect(url_for("reset_password", token=token))
        if password != confirm:
            flash("รหัสผ่านไม่ตรงกัน", "error")
            return redirect(url_for("reset_password", token=token))

        success = reset_customer_password(token, password)
        if success:
            flash("เปลี่ยนรหัสผ่านสำเร็จ! กรุณาเข้าสู่ระบบใหม่", "success")
            return redirect(url_for("customer_login"))
        else:
            flash("เกิดข้อผิดพลาด กรุณาลองใหม่", "error")
            return redirect(url_for("forgot_password"))

    return render_template("reset_password.html", token=token, customer=customer)


# ============================================================
# Tracking
# ============================================================


@app.route("/track", methods=["GET", "POST"])
def track_search():
    if request.method == "POST":
        tracking = request.form.get("tracking_number", "").strip().upper()
        if tracking:
            return redirect(url_for("track_result", tracking_number=tracking))
        flash("กรุณากรอกหมายเลขติดตาม", "error")
    return redirect(url_for("home"))


@app.route("/track/<tracking_number>")
def track_result(tracking_number):
    shipment = get_shipment_by_tracking(tracking_number)
    return render_template("track_result.html", shipment=shipment, tracking_number=tracking_number, STATUS_MAP=STATUS_MAP)


# ============================================================
# Price Calculator (Public)
# ============================================================


@app.route("/calculator")
def calculator():
    rates = load_rates()
    customer_tier = None
    customer_rate = None
    customer = None
    if session.get("customer_code"):
        customer = get_customer_by_code(session["customer_code"])
        if customer:
            tier, tier_rate, effective_rate = get_customer_rate(session["customer_code"])
            customer_tier = tier
            customer_rate = effective_rate
    return render_template("calculator.html", rates=rates, customer=customer,
                           customer_tier=customer_tier, customer_rate=customer_rate)


# ============================================================
# Admin Login / Logout
# ============================================================


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_id"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        admin = get_admin_by_credentials(username, password)
        if admin:
            # ล้าง customer session ออกเมื่อ admin ล็อกอิน
            session.pop("customer_code", None)
            session["admin_id"] = admin["id"]
            session["admin_role"] = admin["role"]
            session["admin_username"] = admin["username"]
            return redirect(url_for("admin_dashboard"))
        else:
            flash("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง", "error")
            return redirect(url_for("admin_login"))

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_role", None)
    session.pop("admin_username", None)
    return redirect(url_for("admin_login"))


# ============================================================
# Admin Dashboard
# ============================================================


@app.route("/admin")
@admin_required
def admin_dashboard():
    search = request.args.get("search", "").strip() or None
    show_inactive = request.args.get("show_inactive") == "1"
    stats = get_stats()
    customers = get_all_customers(search=search, show_inactive=show_inactive)
    return render_template("admin_dashboard.html", stats=stats, customers=customers,
                           search=search, show_inactive=show_inactive,
                           STATUS_MAP=STATUS_MAP, active_tab="customers",
                           LOCATION_TYPES=LOCATION_TYPES, US_CITIES=US_CITIES)


# ============================================================
# Admin — Customer Management
# ============================================================


@app.route("/admin/customer/add", methods=["GET", "POST"])
@admin_required
def admin_customer_add():
    if request.method == "POST":
        location_type = request.form.get("location_type", "").strip()
        city = request.form.get("city", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        if location_type not in ("us", "th"):
            flash("กรุณาเลือกประเภทลูกค้า", "error")
            return redirect(url_for("admin_customer_add"))
        if not email or not password:
            flash("กรุณากรอกอีเมลและรหัสผ่าน", "error")
            return redirect(url_for("admin_customer_add"))
        existing = get_customer_by_email(email)
        if existing:
            flash("อีเมลนี้ถูกใช้งานแล้ว", "error")
            return redirect(url_for("admin_customer_add"))
        sender_first_name = request.form.get("sender_first_name", "").strip()
        sender_last_name = request.form.get("sender_last_name", "").strip()
        sender_address = request.form.get("sender_address", "").strip()
        sender_phone = request.form.get("sender_phone", "").strip()
        if location_type == "us":
            if not city or city not in US_CITIES:
                flash("กรุณาเลือกเมือง", "error")
                return redirect(url_for("admin_customer_add"))
            if not all([sender_first_name, sender_last_name, sender_address, sender_phone]):
                flash("กรุณากรอกข้อมูลผู้ส่งให้ครบ", "error")
                return redirect(url_for("admin_customer_add"))
        addr_first = request.form.get("addr_first_name", "").strip()
        addr_last = request.form.get("addr_last_name", "").strip()
        addr_address = request.form.get("addr_address", "").strip()
        addr_phone = request.form.get("addr_phone", "").strip()
        addr_nickname = request.form.get("addr_nickname", "").strip()
        if not all([addr_first, addr_last, addr_address, addr_phone]):
            flash("กรุณากรอกที่อยู่ปลายทางให้ครบ", "error")
            return redirect(url_for("admin_customer_add"))
        success, result, customer_id = add_customer(
            location_type=location_type, city=city,
            sender_first_name=sender_first_name, sender_last_name=sender_last_name,
            sender_address=sender_address, sender_phone=sender_phone,
            email=email, password=password,
        )
        if success:
            add_customer_address(customer_id, addr_nickname or "ที่อยู่หลัก",
                                 addr_first, addr_last, addr_address, addr_phone, is_default=1)
            flash(f"เพิ่มลูกค้า {result} สำเร็จ", "success")
            return redirect(url_for("admin_customer_detail", code=result))
        else:
            flash(result, "error")
            return redirect(url_for("admin_customer_add"))
    return render_template("admin_customer_add.html", US_CITIES=US_CITIES,
                           LOCATION_TYPES=LOCATION_TYPES, active_tab="customers")


@app.route("/admin/customer/<code>")
@admin_required
def admin_customer_detail(code):
    customer = get_customer_by_code(code)
    if not customer:
        flash("ไม่พบลูกค้า", "error")
        return redirect(url_for("admin_dashboard"))
    addresses = get_customer_addresses(customer["id"])
    shipments = get_shipments_by_customer(customer["customer_code"], limit=20)
    inbound = get_inbound_by_customer(customer["customer_code"], limit=10)
    tier, tier_rate, effective_rate = get_customer_rate(customer["customer_code"])
    return render_template("admin_customer_detail.html", customer=customer,
                           addresses=addresses, shipments=shipments, inbound=inbound,
                           tier=tier, effective_rate=effective_rate,
                           STATUS_MAP=STATUS_MAP, INBOUND_STATUS_MAP=INBOUND_STATUS_MAP,
                           INBOUND_CARRIERS=INBOUND_CARRIERS,
                           US_CITIES=US_CITIES, LOCATION_TYPES=LOCATION_TYPES,
                           PORTS=PORTS, active_tab="customers")


@app.route("/admin/customer/<code>/edit", methods=["POST"])
@admin_required
def admin_customer_edit(code):
    customer = get_customer_by_code(code)
    if not customer:
        flash("ไม่พบลูกค้า", "error")
        return redirect(url_for("admin_dashboard"))
    update_customer_info(
        code,
        sender_first_name=request.form.get("sender_first_name", "").strip() or None,
        sender_last_name=request.form.get("sender_last_name", "").strip() or None,
        sender_address=request.form.get("sender_address", "").strip() or None,
        sender_phone=request.form.get("sender_phone", "").strip() or None,
        email=request.form.get("email", "").strip() or None,
        location_type=request.form.get("location_type", "").strip() or None,
        city=request.form.get("city", "").strip() or None,
    )
    flash("อัพเดทข้อมูลลูกค้าสำเร็จ", "success")
    return redirect(url_for("admin_customer_detail", code=code))


@app.route("/admin/customer/<code>/reset-password", methods=["POST"])
@admin_required
def admin_customer_reset_password(code):
    customer = get_customer_by_code(code)
    if not customer:
        flash("ไม่พบลูกค้า", "error")
        return redirect(url_for("admin_dashboard"))
    import secrets as sec
    temp_password = sec.token_urlsafe(8)
    admin_reset_customer_password(code, temp_password)
    flash(f"รีเซ็ตรหัสผ่านสำเร็จ — รหัสผ่านชั่วคราว: {temp_password}", "success")
    return redirect(url_for("admin_customer_detail", code=code))


@app.route("/admin/customer/<code>/deactivate", methods=["POST"])
@admin_required
def admin_customer_deactivate(code):
    deactivate_customer(code)
    flash(f"ปิดใช้งานลูกค้า {code} สำเร็จ", "success")
    return redirect(url_for("admin_customer_detail", code=code))


@app.route("/admin/customer/<code>/activate", methods=["POST"])
@admin_required
def admin_customer_activate(code):
    activate_customer(code)
    flash(f"เปิดใช้งานลูกค้า {code} สำเร็จ", "success")
    return redirect(url_for("admin_customer_detail", code=code))


@app.route("/admin/shipments/create", methods=["GET", "POST"])
@admin_required
def admin_shipment_create():
    if request.method == "POST":
        customer_code = request.form.get("customer_code", "").strip().upper()
        description = request.form.get("description", "").strip()
        weight = request.form.get("weight", "").strip()
        port = request.form.get("port", "").strip()
        address_id = request.form.get("address_id", "").strip()
        if not customer_code:
            flash("กรุณาเลือกลูกค้า", "error")
            return redirect(url_for("admin_shipment_create"))
        customer = get_customer_by_code(customer_code)
        if not customer:
            flash("ไม่พบรหัสลูกค้า", "error")
            return redirect(url_for("admin_shipment_create"))
        dest_id = int(address_id) if address_id else None
        tracking = add_shipment(customer_code, description, weight, port, dest_id)
        flash(f"สร้าง Shipment สำเร็จ — Tracking: {tracking}", "success")
        return redirect(url_for("admin_shipments"))
    customers = get_all_customers()
    return render_template("admin_shipment_create.html", customers=customers,
                           PORTS=PORTS, active_tab="shipments")


# ============================================================
# Admin Shipments
# ============================================================


@app.route("/admin/shipments")
@admin_required
def admin_shipments():
    search = request.args.get("search", "").strip() or None
    status_filter = request.args.get("status", "all")
    shipments = get_all_shipments(search=search, status_filter=status_filter)
    address_map = {}
    for s in shipments:
        cc = s["customer_code"]
        if cc not in address_map:
            cust = get_customer_by_code(cc)
            if cust:
                address_map[cc] = get_customer_addresses(cust["id"])
    return render_template("admin_shipments.html", shipments=shipments, status_filter=status_filter,
                           search=search, STATUS_MAP=STATUS_MAP, PORTS=PORTS, active_tab="shipments",
                           address_map=address_map)


@app.route("/admin/shipments/update", methods=["POST"])
@admin_required
def admin_update_shipment():
    shipment_id = request.form.get("shipment_id")
    new_status = request.form.get("status")
    if shipment_id and new_status:
        update_shipment_status(shipment_id, new_status)
        flash("อัพเดทสถานะสำเร็จ", "success")
    return redirect(url_for("admin_shipments"))


@app.route("/admin/shipments/<int:shipment_id>/set-address", methods=["POST"])
@admin_required
def admin_set_shipment_address(shipment_id):
    address_id = request.form.get("address_id")
    if not address_id:
        flash("กรุณาเลือกที่อยู่", "error")
        return redirect(url_for("admin_shipments"))
    admin_set_shipment_destination(shipment_id, int(address_id))
    flash("อัพเดทที่อยู่ปลายทางสำเร็จ", "success")
    return redirect(url_for("admin_shipments"))


@app.route("/admin/shipments/bulk-update", methods=["POST"])
@admin_required
def admin_bulk_update():
    ids = request.form.getlist("shipment_ids")
    new_status = request.form.get("bulk_status")
    if ids and new_status:
        bulk_update_shipment_status(ids, new_status)
        flash(f"อัพเดทสถานะ {len(ids)} รายการสำเร็จ", "success")
    else:
        flash("กรุณาเลือกพัสดุและสถานะ", "error")
    return redirect(url_for("admin_shipments"))


# ============================================================
# Admin — Inbound Packages
# ============================================================


@app.route("/admin/inbound")
@admin_required
def admin_inbound():
    search = request.args.get("search", "").strip() or None
    status_filter = request.args.get("status", "all")
    packages = get_all_inbound_packages(search=search, status_filter=status_filter)
    return render_template("admin_inbound.html", packages=packages,
                           status_filter=status_filter, search=search,
                           INBOUND_STATUS_MAP=INBOUND_STATUS_MAP,
                           INBOUND_CARRIERS=INBOUND_CARRIERS,
                           active_tab="inbound")


@app.route("/admin/inbound/<int:inbound_id>/update", methods=["POST"])
@admin_required
def admin_update_inbound(inbound_id):
    new_status = request.form.get("status")
    notes = request.form.get("notes", "").strip()
    if new_status:
        update_inbound_status(inbound_id, new_status, notes)
        flash("อัพเดทสถานะพัสดุขาเข้าสำเร็จ", "success")
    return redirect(url_for("admin_inbound"))


# ============================================================
# Admin — Rate Management
# ============================================================


@app.route("/admin/rates")
@admin_required
def admin_rates():
    rates = load_rates()
    customers = get_all_customers()
    is_super = session.get("admin_role") == "super_admin"
    return render_template("admin_rates.html", rates=rates, customers=customers,
                           is_super=is_super, active_tab="rates", TIERS=TIERS)


@app.route("/admin/rates/update", methods=["POST"])
@super_admin_required
def admin_rates_update():
    rates = load_rates()
    for tier_key in rates["tiers"]:
        new_rate = request.form.get(f"rate_{tier_key}")
        if new_rate:
            rates["tiers"][tier_key]["rate"] = float(new_rate)
    rates["updated_by"] = session.get("admin_username")
    save_rates(rates)
    flash("อัพเดทอัตราค่าขนส่งสำเร็จ", "success")
    return redirect(url_for("admin_rates"))


@app.route("/admin/rates/customer", methods=["POST"])
@super_admin_required
def admin_customer_rate():
    customer_code = request.form.get("customer_code")
    tier = request.form.get("tier")
    custom_rate = request.form.get("custom_rate", "").strip()
    custom_rate_val = float(custom_rate) if custom_rate else None
    update_customer_tier(customer_code, tier, custom_rate_val)
    flash(f"อัพเดทราคาลูกค้า {customer_code} สำเร็จ", "success")
    return redirect(url_for("admin_rates"))


# ============================================================
# Admin — Rate Requests
# ============================================================


@app.route("/admin/requests")
@admin_required
def admin_requests():
    is_super = session.get("admin_role") == "super_admin"
    requests_list = get_all_rate_requests()
    return render_template("admin_requests.html", requests=requests_list,
                           is_super=is_super, active_tab="requests",
                           customers=get_all_customers())


@app.route("/admin/requests/add", methods=["POST"])
@admin_required
def admin_request_add():
    customer_code = request.form.get("customer_code", "").strip()
    requested_rate = float(request.form.get("requested_rate", 0))
    reason = request.form.get("reason", "").strip()
    add_rate_request(session["admin_id"], customer_code, requested_rate, reason)
    flash("ส่งคำขอสำเร็จ รอ Super Admin อนุมัติ", "success")
    return redirect(url_for("admin_requests"))


@app.route("/admin/requests/review/<int:request_id>", methods=["POST"])
@super_admin_required
def admin_request_review(request_id):
    action = request.form.get("action")
    review_rate_request(request_id, session["admin_id"], action)
    flash(f"{'อนุมัติ' if action == 'approved' else 'ปฏิเสธ'}คำขอสำเร็จ", "success")
    return redirect(url_for("admin_requests"))


# ============================================================
# Admin — Manage Admins (Super Admin only)
# ============================================================


@app.route("/admin/manage")
@super_admin_required
def admin_manage():
    admins = get_all_admins()
    return render_template("admin_manage.html", admins=admins, active_tab="manage")


@app.route("/admin/manage/add", methods=["POST"])
@super_admin_required
def admin_manage_add():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "admin")
    if not username or not password:
        flash("กรุณากรอกข้อมูลให้ครบ", "error")
    else:
        success, msg = add_admin(username, password, role)
        flash(msg, "success" if success else "error")
    return redirect(url_for("admin_manage"))


@app.route("/admin/manage/delete/<int:admin_id>", methods=["POST"])
@super_admin_required
def admin_manage_delete(admin_id):
    if admin_id == session.get("admin_id"):
        flash("ไม่สามารถลบตัวเองได้", "error")
    else:
        delete_admin(admin_id)
        flash("ลบ admin สำเร็จ", "success")
    return redirect(url_for("admin_manage"))


# ============================================================
# Run
# ============================================================


# ============================================================
# Messaging SPA (React) — catch-all route
# ============================================================

MESSAGING_BUILD_DIR = os.path.join(os.path.dirname(__file__), "messaging-frontend", "build")


@app.route("/messaging/")
@app.route("/messaging/<path:path>")
@admin_required
def messaging_spa(path=""):
    # Serve static files from React build
    if path and os.path.exists(os.path.join(MESSAGING_BUILD_DIR, path)):
        return send_from_directory(MESSAGING_BUILD_DIR, path)
    # Fall back to index.html for client-side routing
    index_path = os.path.join(MESSAGING_BUILD_DIR, "index.html")
    if os.path.exists(index_path):
        return send_from_directory(MESSAGING_BUILD_DIR, "index.html")
    # Dev mode: redirect to React dev server
    return render_template("messaging_dev.html")


# ============================================================
# Serve media files from persistent disk (production)
# ============================================================

_DATA_DIR = os.environ.get("DATA_DIR", "")

if _DATA_DIR:
    # Production: serve /static/media/* from persistent disk /var/data/media/
    @app.route("/static/media/<path:filename>")
    def serve_media(filename):
        media_dir = os.path.join(_DATA_DIR, "media")
        return send_from_directory(media_dir, filename)


# ============================================================
# Ensure config dir exists for rates.json
# ============================================================

if _DATA_DIR:
    _config_dir = os.path.join(_DATA_DIR, "config")
    os.makedirs(_config_dir, exist_ok=True)
    # Copy default rates.json if not exists on persistent disk
    _rates_disk = os.path.join(_config_dir, "rates.json")
    _rates_local = os.path.join(os.path.dirname(__file__), "config", "rates.json")
    if not os.path.exists(_rates_disk) and os.path.exists(_rates_local):
        import shutil
        shutil.copy2(_rates_local, _rates_disk)


# ============================================================
# Run
# ============================================================


# Always init DB (needed for gunicorn in production)
init_db()

# Init messaging DB tables
from messaging_db import init_messaging_db
init_messaging_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    print("=" * 50)
    print("  US-TH Shipping Tracker is running!")
    print(f"  Homepage:    http://localhost:{port}/")
    print(f"  Calculator:  http://localhost:{port}/calculator")
    print(f"  Register:    http://localhost:{port}/register")
    print(f"  Customer:    http://localhost:{port}/customer")
    print(f"  Admin:       http://localhost:{port}/admin")
    print(f"  Messaging:   http://localhost:{port}/messaging/")
    print("  Default admin: admin / admin123 (super_admin)")
    print("=" * 50)
    socketio.run(app, debug=debug, host="0.0.0.0", port=port)
