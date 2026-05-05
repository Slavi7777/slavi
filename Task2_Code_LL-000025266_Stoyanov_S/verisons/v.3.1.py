from flask import Flask, render_template, request, redirect, session
import sqlite3
import hashlib
import re
import requests

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


# ---------------- WEATHER ----------------
def get_weather():
    try:
        api_key = "your_api_key"
        url = f"http://api.weatherapi.com/v1/current.json?key={api_key}&q=London"
        response = requests.get(url).json()

        return {
            "temp": round(response["current"]["temp_c"]),
            "desc": response["current"]["condition"]["text"]
        }
    except:
        return {"temp": "--", "desc": "Unavailable"}


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

    c.execute("""
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT,
        total REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS order_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        product_name TEXT,
        quantity INTEGER,
        price REAL
    )
    """)

    # Default users
    users = [
        ("Admin", "User", "admin@glhadmin.com", hash_password("Admin12$"), "admin"),
        ("Farmer", "User", "farmer@farmer.com", hash_password("Farmer13*"), "producer")
    ]

    for u in users:
        c.execute("SELECT * FROM users WHERE email=?", (u[2],))
        if not c.fetchone():
            c.execute("INSERT INTO users VALUES(NULL,?,?,?,?,?,0)", u)

    # Default categories
    c.execute("SELECT * FROM categories")
    if not c.fetchall():
        c.executemany("INSERT INTO categories(name) VALUES(?)",
                      [("Fruit",), ("Dairy",), ("Bakery",), ("Vegetables",)])

    conn.commit()
    conn.close()


init_db()


# ---------------- ROUTES ----------------

@app.route("/")
def home():
    if not login_required():
        return redirect("/login")

    conn = connect_db()
    items = conn.execute("SELECT * FROM products LIMIT 3").fetchall()
    conn.close()

    weather = get_weather()

    return render_template("home.html", items=items, weather=weather)


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

            # 🔥 Admin redirect
            if user["role"] == "admin":
                return redirect("/admin")

            return redirect("/")

        return render_template("login.html", error="❌ Invalid email or password")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        if not is_valid_email(email):
            return "Invalid email"

        if not is_strong_password(password):
            return "Weak password"

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
            return render_template("register.html", error="❌ Email already exists")
        finally:
            conn.close()

        return render_template("login.html", success="✅ Account created")

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

    if product["stock"] <= 0:
        return "❌ Out of stock"

    if "cart" not in session:
        session["cart"] = []

    for item in session["cart"]:
        if item["id"] == id:
            if item["quantity"] >= product["stock"]:
                return "❌ Not enough stock"
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

    return render_template(
        "cart.html",
        cart=session.get("cart", []),
        total=calculate_cart_total()
    )


# -------- CHECKOUT --------
@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if not login_required():
        return redirect("/login")

    if request.method == "POST":
        fullname = request.form.get("fullname", "").strip()
        card = request.form.get("card", "")

        if len(fullname.split()) < 2:
            return render_template("checkout.html", error="❌ Enter full name", total=calculate_cart_total())

        if not card.isdigit() or len(card) != 16:
            return render_template("checkout.html", error="❌ Invalid card", total=calculate_cart_total())

        cart_items = session.get("cart", [])
        total = calculate_cart_total()

        conn = connect_db()
        cursor = conn.cursor()

        # STOCK CHECK
        for item in cart_items:
            product = conn.execute("SELECT stock FROM products WHERE id=?", (item["id"],)).fetchone()
            if not product or product["stock"] < item["quantity"]:
                conn.close()
                return render_template("checkout.html", error="❌ Not enough stock", total=total)

        # SAVE ORDER
        cursor.execute("INSERT INTO orders(user_email, total) VALUES (?, ?)", (session["user"], total))
        order_id = cursor.lastrowid

        for item in cart_items:
            cursor.execute("""
                INSERT INTO order_items(order_id, product_name, quantity, price)
                VALUES (?, ?, ?, ?)
            """, (order_id, item["name"], item["quantity"], item["price"]))

        # REDUCE STOCK
        for item in cart_items:
            conn.execute("UPDATE products SET stock = stock - ? WHERE id=?",
                         (item["quantity"], item["id"]))

        conn.commit()
        conn.close()

        session["cart"] = []

        return redirect("/orders")

    return render_template("checkout.html", total=calculate_cart_total())


# -------- ORDERS --------
@app.route("/orders")
def orders():
    if not login_required():
        return redirect("/login")

    conn = connect_db()
    orders = conn.execute(
        "SELECT * FROM orders WHERE user_email=? ORDER BY created_at DESC",
        (session["user"],)
    ).fetchall()

    order_data = []

    for order in orders:
        items = conn.execute(
            "SELECT * FROM order_items WHERE order_id=?",
            (order["id"],)
        ).fetchall()

        order_data.append({"order": order, "items": items})

    conn.close()

    return render_template("orders.html", orders=order_data)


# -------- ADMIN DASHBOARD (NEW) --------
@app.route("/admin")
def admin():
    if not login_required() or session.get("role") != "admin":
        return "❌ Access Denied"

    conn = connect_db()

    users = conn.execute("SELECT * FROM users").fetchall()
    products = conn.execute("SELECT * FROM products").fetchall()
    orders = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        users=users,
        products=products,
        orders=orders
    )


# -------- LOGOUT --------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)