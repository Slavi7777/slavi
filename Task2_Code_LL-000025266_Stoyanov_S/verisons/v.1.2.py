# ================================
# VERSION 1.2 - PRODUCTS SYSTEM
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


# ---------------- INIT DATABASE ----------------
def init_db():
    conn = connect_db()
    c = conn.cursor()

    # USERS
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

    # CATEGORIES
    c.execute("""
    CREATE TABLE IF NOT EXISTS categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT
    )
    """)

    # PRODUCTS
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

    # DEFAULT USERS
    users = [
        ("Admin", "User", "admin@glhadmin.com", hash_password("Admin12$"), "admin"),
        ("Farmer", "User", "farmer@farmer.com", hash_password("Farmer13*"), "producer")
    ]

    for u in users:
        c.execute("SELECT * FROM users WHERE email=?", (u[2],))
        if not c.fetchone():
            c.execute("INSERT INTO users VALUES(NULL,?,?,?,?,?,0)", u)

    # DEFAULT CATEGORIES
    c.execute("SELECT * FROM categories")
    if not c.fetchall():
        c.executemany("INSERT INTO categories(name) VALUES(?)",
                      [("Fruit",), ("Dairy",), ("Bakery",), ("Vegetables",)])

    # ✅ SAMPLE PRODUCTS (NEW IN 1.2)
    c.execute("SELECT * FROM products")
    if not c.fetchall():
        c.executemany("""
            INSERT INTO products(name, price, stock, image, category_id, description)
            VALUES(?,?,?,?,?,?)
        """, [
            ("Apples", 1.99, 50, "apple.jpg", 1, "Fresh red apples"),
            ("Milk", 1.20, 30, "milk.jpg", 2, "Organic whole milk"),
            ("Bread", 1.50, 20, "bread.jpg", 3, "Fresh baked bread")
        ])

    conn.commit()
    conn.close()


init_db()


# ---------------- ROUTES ----------------

# HOME (UPDATED)
@app.route("/")
def home():
    if not login_required():
        return redirect("/login")

    conn = connect_db()
    items = conn.execute("SELECT * FROM products LIMIT 3").fetchall()
    conn.close()

    return render_template("home.html", items=items)


# -------- LOGIN --------
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

        return render_template("login.html",
                               error="❌ Invalid email or password")

    return render_template("login.html")


# -------- REGISTER --------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        if not is_valid_email(email):
            return render_template("register.html",
                                   error="❌ Invalid email")

        if not is_strong_password(password):
            return render_template("register.html",
                                   error="❌ Weak password")

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
            return render_template(
                "register.html",
                error="❌ Email already exists"
            )

        conn.close()

        return render_template(
            "login.html",
            success="✅ Account created successfully"
        )

    return render_template("register.html")


# -------- PRODUCTS PAGE (NEW) --------
@app.route("/products")
def products():
    if not login_required():
        return redirect("/login")

    conn = connect_db()
    items = conn.execute("SELECT * FROM products").fetchall()
    conn.close()

    return render_template("products.html", items=items)


# -------- LOGOUT --------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)