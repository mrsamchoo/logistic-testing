from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from database import (
    init_db, add_customer, get_customer_by_code, get_all_customers,
    get_shipments_by_customer, get_shipment_by_tracking,
    get_all_shipments, update_shipment_status, bulk_update_shipment_status,
    get_stats, seed_mock_shipments, STATUS_MAP, PORTS, TIERS,
    get_admin_by_credentials, get_admin_by_id, get_all_admins,
    add_admin, delete_admin, update_customer_tier,
    load_rates, save_rates, get_customer_rate,
    add_rate_request, get_pending_requests, get_all_rate_requests, review_rate_request,
    get_customer_by_credentials, get_customer_by_email,
    create_reset_token, verify_reset_token, reset_customer_password,
)

app = Flask(__name__)
app.secret_key = "shipping-secret-key-change-in-production"


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
        fields = [
            "sender_first_name", "sender_last_name", "sender_address", "sender_phone",
            "receiver_first_name", "receiver_last_name", "receiver_address", "receiver_phone",
        ]
        data = {f: request.form.get(f, "").strip() for f in fields}

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not all(data.values()) or not email or not password:
            flash("กรุณากรอกข้อมูลให้ครบทุกช่อง", "error")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("รหัสผ่านไม่ตรงกัน กรุณาลองใหม่", "error")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร", "error")
            return redirect(url_for("register"))

        # Check duplicate email
        existing = get_customer_by_email(email)
        if existing:
            flash("อีเมลนี้ถูกใช้งานแล้ว", "error")
            return redirect(url_for("register"))

        success, result = add_customer(**data, email=email, password=password)
        if success:
            customer_code = result
            seed_mock_shipments(customer_code)
            session["customer_code"] = customer_code
            return redirect(url_for("register_success", code=customer_code))
        else:
            flash(result, "error")
            return redirect(url_for("register"))

    return render_template("register.html")


@app.route("/register/success/<code>")
def register_success(code):
    customer = get_customer_by_code(code)
    if not customer:
        flash("ไม่พบรหัสลูกค้า", "error")
        return redirect(url_for("register"))
    return render_template("register_success.html", customer=customer)


# ============================================================
# Customer
# ============================================================


@app.route("/customer", methods=["GET", "POST"])
def customer_login():
    if request.method == "POST":
        code = request.form.get("customer_code", "").strip().upper()
        password = request.form.get("password", "").strip()
        customer = get_customer_by_credentials(code, password)
        if customer:
            air_code = customer["customer_code"]
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
    shipments = get_shipments_by_customer(customer["customer_code"], limit=5)
    tier, tier_rate, effective_rate = get_customer_rate(customer["customer_code"])
    rates = load_rates()
    return render_template("customer_portal.html", customer=customer, shipments=shipments,
                           STATUS_MAP=STATUS_MAP, tier=tier, effective_rate=effective_rate, rates=rates)


@app.route("/customer/logout")
def customer_logout():
    session.pop("customer_code", None)
    return redirect(url_for("home"))


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
    stats = get_stats()
    customers = get_all_customers(search=search)
    return render_template("admin_dashboard.html", stats=stats, customers=customers,
                           search=search, STATUS_MAP=STATUS_MAP, active_tab="customers")


# ============================================================
# Admin Shipments
# ============================================================


@app.route("/admin/shipments")
@admin_required
def admin_shipments():
    search = request.args.get("search", "").strip() or None
    status_filter = request.args.get("status", "all")
    shipments = get_all_shipments(search=search, status_filter=status_filter)
    return render_template("admin_shipments.html", shipments=shipments, status_filter=status_filter,
                           search=search, STATUS_MAP=STATUS_MAP, PORTS=PORTS, active_tab="shipments")


@app.route("/admin/shipments/update", methods=["POST"])
@admin_required
def admin_update_shipment():
    shipment_id = request.form.get("shipment_id")
    new_status = request.form.get("status")
    if shipment_id and new_status:
        update_shipment_status(shipment_id, new_status)
        flash("อัพเดทสถานะสำเร็จ", "success")
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


if __name__ == "__main__":
    init_db()
    print("=" * 50)
    print("  US-TH Shipping Tracker is running!")
    print("  Homepage:    http://localhost:8080/")
    print("  Calculator:  http://localhost:8080/calculator")
    print("  Register:    http://localhost:8080/register")
    print("  Customer:    http://localhost:8080/customer")
    print("  Admin:       http://localhost:8080/admin")
    print("  Default admin: admin / admin123 (super_admin)")
    print("=" * 50)
    app.run(debug=True, host="0.0.0.0", port=8080)
