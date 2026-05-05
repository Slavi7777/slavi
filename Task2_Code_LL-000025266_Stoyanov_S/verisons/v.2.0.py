# ================================
# VERSION 1.4 - CART SYSTEM
# ================================

from flask import Flask, render_template, request, redirect, session
import sqlite3
import hashlib
import re

app = Flask(__name__)
app.secret_key = "secretkey"


# ---------------- DATABASE ----------------
def connect_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- HELPERS ----------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def login_required():
    return "user" in session


def is_valid_email(email):
    return re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email)


def is_strong_password(password):
    return re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{6,}$", password)


def calculate_cart_total():
    total = 0
    for item in session.get("cart", []):
        total += item["price"] * item["quantity"]
    return total


# ---------------- INIT DATABASE ----------------
def init_db():
    conn = connect_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT,
        last_name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT,
        points INTEGER DEFAULT 0
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price REAL,
        stock INTEGER,
        image TEXT,
        category_id INTEGER,
        description TEXT
    )
    """)

    conn.commit()
    conn.close()


init_db()


# ---------------- ROUTES ----------------

@app.route("/")
def home():
    if not login_required():
        return redirect("/login")

    conn = connect_db()
    items = conn.execute("SELECT * FROM products").fetchall()
    conn.close()

    return render_template("home.html", items=items)


# -------- AUTH --------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = hash_password(request.form["password"])

        conn = connect_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, password)
        ).fetchone()
        conn.close()

        if user:
            session["user"] = user["email"]
            session["role"] = user["role"]
            return redirect("/")

        return render_template("login.html", error="❌ Invalid email or password")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        if not is_valid_email(email):
            return render_template("register.html", error="❌ Invalid email")

        if not is_strong_password(password):
            return render_template("register.html", error="❌ Weak password")

        conn = connect_db()
        try:
            conn.execute("""
                INSERT INTO users(first_name,last_name,email,password,role,points)
                VALUES(?,?,?,?,?,0)
            """, (
                request.form["fname"],
                request.form["lname"],
                email,
                hash_password(password),
                "customer"
            ))
            conn.commit()
        except:
            conn.close()
            return render_template("register.html", error="❌ Email already exists")

        conn.close()
        return render_template("login.html", success="✅ Account created successfully")

    return render_template("register.html")


# -------- PRODUCTS --------
@app.route("/products")
def products():
    if not login_required():
        return redirect("/login")

    conn = connect_db()
    items = conn.execute("SELECT * FROM products").fetchall()
    conn.close()

    return render_template("products.html", items=items)


# -------- CART --------
@app.route("/add_to_cart/<int:id>")
def add_to_cart(id):
    if not login_required():
        return redirect("/login")

    conn = connect_db()
    product = conn.execute("SELECT * FROM products WHERE id=?", (id,)).fetchone()
    conn.close()

    if "cart" not in session:
        session["cart"] = []

    for item in session["cart"]:
        if item["id"] == id:
            item["quantity"] += 1
            session.modified = True
            return redirect("/cart")

    session["cart"].append({
        "id": id,
        "name": product["name"],
        "price": product["price"],
        "quantity": 1
    })

    session.modified = True
    return redirect("/cart")


@app.route("/cart")
def cart():
    if not login_required():
        return redirect("/login")

    cart_items = session.get("cart", [])
    total = round(calculate_cart_total(), 2)

    return render_template("cart.html", cart=cart_items, total=total)


@app.route("/increase/<int:id>")
def increase(id):
    for item in session.get("cart", []):
        if item["id"] == id:
            item["quantity"] += 1
    session.modified = True
    return redirect("/cart")


@app.route("/decrease/<int:id>")
def decrease(id):
    for item in session.get("cart", []):
        if item["id"] == id:
            item["quantity"] -= 1
            if item["quantity"] <= 0:
                session["cart"].remove(item)
    session.modified = True
    return redirect("/cart")


@app.route("/remove/<int:id>")
def remove(id):
    session["cart"] = [
        item for item in session.get("cart", [])
        if item["id"] != id
    ]
    session.modified = True
    return redirect("/cart")


# -------- LOGOUT --------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)