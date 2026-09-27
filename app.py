import os
from functools import wraps
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

BASE = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", f"sqlite:///{os.path.join(BASE, 'mepconnect.db')}"
).replace("postgres://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "1") == "1"

# Render/reverse-proxy aware URL and HTTPS handling.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(180), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="buyer")
    verified = db.Column(db.Boolean, nullable=False, default=False)


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(220), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    specification = db.Column(db.Text, default="")
    unit = db.Column(db.String(30), default="pcs")
    price = db.Column(db.Float, default=0)
    stock = db.Column(db.Integer, default=0)
    verified = db.Column(db.Boolean, default=False)
    supplier = db.relationship("User", foreign_keys=[supplier_id])


class RFQ(db.Model):
    __tablename__ = "rfqs"
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    material = db.Column(db.String(220), nullable=False)
    specification = db.Column(db.Text, default="")
    quantity = db.Column(db.String(100), nullable=False)
    deadline = db.Column(db.String(20), default="")
    status = db.Column(db.String(30), default="Open")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    buyer = db.relationship("User", foreign_keys=[buyer_id])


class Quotation(db.Model):
    __tablename__ = "quotations"
    id = db.Column(db.Integer, primary_key=True)
    rfq_id = db.Column(db.Integer, db.ForeignKey("rfqs.id"), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    price = db.Column(db.Float, nullable=False)
    lead_time = db.Column(db.Integer, default=7)
    note = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    supplier = db.relationship("User", foreign_keys=[supplier_id])
    rfq = db.relationship("RFQ", foreign_keys=[rfq_id])


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(30), default="Processing")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    buyer = db.relationship("User", foreign_keys=[buyer_id])
    supplier = db.relationship("User", foreign_keys=[supplier_id])
    product = db.relationship("Product", foreign_keys=[product_id])


def seed_database():
    supplier = User.query.filter_by(email="supplier@mepconnect.local").first()
    if not supplier:
        supplier = User(
            company="PT MEP Supply Indonesia",
            email="supplier@mepconnect.local",
            password=generate_password_hash("supplier123"),
            role="supplier",
            verified=True,
        )
        db.session.add(supplier)

    buyer = User.query.filter_by(email="buyer@mepconnect.local").first()
    if not buyer:
        buyer = User(
            company="PT Contoh Konstruksi",
            email="buyer@mepconnect.local",
            password=generate_password_hash("buyer123"),
            role="buyer",
            verified=True,
        )
        db.session.add(buyer)

    db.session.commit()

    if Product.query.count() == 0:
        products = [
            ("Kabel NYY 4 × 10 mm²", "Electrical", "Copper; 0,6/1 kV; 4 core", "meter", 37900, 10000),
            ("Pipa PPR Ø25 mm", "Plumbing", "PPR; project supply", "meter", 28500, 5000),
            ('Sprinkler Head 1/2"', "Fire Protection", "Standard sprinkler head", "pcs", 85000, 1000),
            ("LED Panel 18 W", "Electrical", "LED; 18 W; indoor", "pcs", 125000, 2500),
            ("Exhaust Fan 12 inch", "Mechanical", "Ventilation; 12 inch", "pcs", 850000, 250),
            ('Ball Valve 1"', "Plumbing", "Brass; 1 inch", "pcs", 145000, 800),
        ]
        for name, category, spec, unit, price, stock in products:
            db.session.add(Product(
                supplier_id=supplier.id, name=name, category=category,
                specification=spec, unit=unit, price=price, stock=stock, verified=True
            ))
        db.session.commit()


@app.context_processor
def inject_app_info():
    return {"app_name": "MEPConnect"}


def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrap


def role_required(role):
    def decorator(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("login"))
            if session.get("role") != role:
                abort(403)
            return f(*args, **kwargs)
        return wrap
    return decorator


@app.route("/health")
def health():
    try:
        db.session.execute(db.text("SELECT 1"))
        return {"status": "ok", "database": "ok"}, 200
    except Exception:
        return {"status": "error", "database": "unavailable"}, 503


@app.route("/")
def home():
    products = Product.query.join(User, Product.supplier_id == User.id).order_by(Product.id.desc()).all()
    return render_template("home.html", products=products, user=session)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        company = request.form.get("company", "").strip()
        email = request.form.get("email", "").strip().lower()
        raw_password = request.form.get("password", "")
        role = request.form.get("role", "buyer")
        if role not in {"buyer", "supplier"}:
            role = "buyer"
        if not company or not email or len(raw_password) < 8:
            flash("Lengkapi data dan gunakan password minimal 8 karakter.", "error")
            return render_template("auth.html", mode="register")
        if User.query.filter_by(email=email).first():
            flash("Email sudah terdaftar.", "error")
            return render_template("auth.html", mode="register")
        db.session.add(User(
            company=company, email=email,
            password=generate_password_hash(raw_password), role=role, verified=False
        ))
        db.session.commit()
        flash("Akun berhasil dibuat. Silakan masuk.", "success")
        return redirect(url_for("login"))
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        raw_password = request.form.get("password", "")
        u = User.query.filter_by(email=email).first()
        if u and check_password_hash(u.password, raw_password):
            session.clear()
            session.update(user_id=u.id, company=u.company, role=u.role, verified=bool(u.verified))
            return redirect(url_for("dashboard"))
        flash("Email atau password salah.", "error")
    return render_template("auth.html", mode="login")


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    uid = session["user_id"]
    if session["role"] == "supplier":
        products = Product.query.filter_by(supplier_id=uid).order_by(Product.id.desc()).all()
        quotes = (Quotation.query.filter_by(supplier_id=uid)
                  .join(RFQ, Quotation.rfq_id == RFQ.id)
                  .order_by(Quotation.id.desc()).all())
        orders = Order.query.filter_by(supplier_id=uid).order_by(Order.id.desc()).all()
        return render_template("supplier_dashboard.html", products=products, quotes=quotes, orders=orders)
    rfqs = RFQ.query.filter_by(buyer_id=uid).order_by(RFQ.id.desc()).all()
    orders = Order.query.filter_by(buyer_id=uid).order_by(Order.id.desc()).all()
    return render_template("buyer_dashboard.html", rfqs=rfqs, orders=orders)


@app.route("/rfq", methods=["POST"])
@role_required("buyer")
def rfq():
    material = request.form.get("material", "").strip()
    quantity = request.form.get("quantity", "").strip()
    if not material or not quantity:
        flash("Material dan quantity wajib diisi.", "error")
        return redirect(url_for("dashboard"))
    db.session.add(RFQ(
        buyer_id=session["user_id"], material=material,
        specification=request.form.get("specification", "").strip(),
        quantity=quantity, deadline=request.form.get("deadline", "").strip()
    ))
    db.session.commit()
    flash("RFQ berhasil dikirim. Supplier dapat memberikan quotation.", "success")
    return redirect(url_for("dashboard"))


@app.route("/rfqs")
def rfqs():
    rows = RFQ.query.order_by(RFQ.id.desc()).all()
    quote_counts = {r.id: Quotation.query.filter_by(rfq_id=r.id).count() for r in rows}
    return render_template("rfqs.html", rfqs=rows, quote_counts=quote_counts)


@app.route("/quote/<int:rfq_id>", methods=["POST"])
@role_required("supplier")
def quote(rfq_id):
    rfq_obj = db.session.get(RFQ, rfq_id)
    if not rfq_obj:
        abort(404)
    try:
        price = float(request.form.get("price", 0))
        lead_time = int(request.form.get("lead_time", 7))
    except ValueError:
        flash("Harga dan lead time harus berupa angka.", "error")
        return redirect(url_for("rfqs"))
    if price <= 0 or lead_time < 0:
        flash("Harga harus lebih dari 0 dan lead time tidak boleh negatif.", "error")
        return redirect(url_for("rfqs"))
    db.session.add(Quotation(
        rfq_id=rfq_id, supplier_id=session["user_id"], price=price,
        lead_time=lead_time, note=request.form.get("note", "").strip()
    ))
    db.session.commit()
    flash("Quotation terkirim.", "success")
    return redirect(url_for("rfqs"))


@app.route("/buy/<int:product_id>", methods=["POST"])
@role_required("buyer")
def buy(product_id):
    try:
        qty = int(request.form.get("quantity", 0))
    except ValueError:
        qty = 0
    if qty < 1:
        flash("Quantity tidak valid.", "error")
        return redirect(url_for("home"))
    product = db.session.get(Product, product_id)
    if not product or product.stock < qty:
        flash("Stok tidak mencukupi.", "error")
        return redirect(url_for("home"))
    total = product.price * qty
    db.session.add(Order(
        buyer_id=session["user_id"], supplier_id=product.supplier_id,
        product_id=product.id, quantity=qty, total=total, status="Processing"
    ))
    product.stock -= qty
    db.session.commit()
    flash("Pesanan berhasil dibuat. Status: Processing.", "success")
    return redirect(url_for("dashboard"))


@app.route("/order/<int:order_id>/status", methods=["POST"])
@role_required("supplier")
def order_status(order_id):
    status = request.form.get("status", "")
    if status not in {"Processing", "Shipped", "Delivered"}:
        abort(400)
    order = Order.query.filter_by(id=order_id, supplier_id=session["user_id"]).first_or_404()
    order.status = status
    db.session.commit()
    flash("Status pesanan diperbarui.", "success")
    return redirect(url_for("dashboard"))


@app.route("/product", methods=["POST"])
@role_required("supplier")
def product():
    try:
        price = float(request.form.get("price", 0))
        stock = int(request.form.get("stock", 0))
    except ValueError:
        flash("Harga dan stok harus berupa angka.", "error")
        return redirect(url_for("dashboard"))
    if price < 0 or stock < 0:
        flash("Harga dan stok tidak boleh negatif.", "error")
        return redirect(url_for("dashboard"))
    category = request.form.get("category", "Electrical")
    if category not in {"Electrical", "Mechanical", "Plumbing", "Fire Protection"}:
        category = "Electrical"
    db.session.add(Product(
        supplier_id=session["user_id"], name=request.form.get("name", "").strip(),
        category=category, specification=request.form.get("specification", "").strip(),
        unit=request.form.get("unit", "pcs").strip() or "pcs", price=price, stock=stock,
        verified=bool(session.get("verified", False))
    ))
    db.session.commit()
    flash("Produk berhasil ditambahkan.", "success")
    return redirect(url_for("dashboard"))


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    pattern = f"%{q}%"
    rows = (Product.query.join(User, Product.supplier_id == User.id)
            .filter((Product.name.ilike(pattern)) | (Product.category.ilike(pattern)) | (Product.specification.ilike(pattern)))
            .limit(30).all())
    return jsonify([
        {
            "id": p.id, "name": p.name, "category": p.category,
            "specification": p.specification, "unit": p.unit,
            "price": p.price, "stock": p.stock, "supplier": p.supplier.company
        }
        for p in rows
    ])


@app.errorhandler(403)
def forbidden(_):
    return render_template("error.html", code=403, message="Anda tidak memiliki akses ke halaman ini."), 403


@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", code=404, message="Halaman yang Anda cari tidak ditemukan."), 404


with app.app_context():
    db.create_all()
    seed_database()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_DEBUG") == "1")
