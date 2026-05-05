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
    return sum(item["price"] * item["quantity"] for item in session.get("cart", []))


# ---------------- LOYALTY ----------------
def get_loyalty_tier(points):
    if points >= 300:
        return "Gold"
    elif points >= 100:
        return "Silver"
    return "Bronze"


def get_points_for_tier(points):
    if points >= 300:
        return 25
    elif points >= 100:
        return 15
    return 10


# ---------------- WEATHER ----------------
def get_weather():
    try:
        api_key = "your_api_key"
        url = f"http://api.weatherapi.com/v1/current.json?key={api_key}&q=London"
        data = requests.get(url).json()

        return {
            "temp": round(data["current"]["temp_c"]),
            "desc": data["current"]["condition"]["text"]
        }
    except Exception:
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
    user = conn.execute("SELECT points FROM users WHERE email=?", (session["user"],)).fetchone()
    conn.close()

    tier = get_loyalty_tier(user["points"])
    weather = get_weather()

    return render_template("home.html", items=items, weather=weather, tier=tier)


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
                INSERT INTO users(first_name,last_name,email,password,role)
                VALUES(?,?,?,?,?)
            """, (
                request.form["fname"],
                request.form["lname"],
                email,
                hash_password(password),
                "customer"
            ))
            conn.commit()
        except Exception:
            return render_template("register.html", error="❌ Email already exists")
        finally:
            conn.close()

        return render_template("login.html", success="✅ Account created")

    return render_template("register.html")


# -------- LOYALTY PAGE --------
@app.route("/loyalty")
def loyalty():
    if not login_required():
        return redirect("/login")

    conn = connect_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email=?",
        (session["user"],)
    ).fetchone()
    conn.close()

    tier = get_loyalty_tier(user["points"])

    return render_template("loyalty.html", user=user, tier=tier)


# -------- REDEEM --------
@app.route("/redeem/5off")
def redeem():
    if not login_required():
        return redirect("/login")

    conn = connect_db()
    user = conn.execute("SELECT points FROM users WHERE email=?", (session["user"],)).fetchone()

    if user["points"] < 100:
        conn.close()
        return render_template("loyalty.html", error="❌ Not enough points")

    conn.execute("UPDATE users SET points = points - 100 WHERE email=?", (session["user"],))
    conn.commit()
    conn.close()

    session["discount"] = 5

    return redirect("/cart")


# -------- CART --------
@app.route("/cart")
def cart():
    if not login_required():
        return redirect("/login")

    total = calculate_cart_total()
    discount = session.get("discount", 0)

    return render_template(
        "cart.html",
        cart=session.get("cart", []),
        total=total,
        discount=discount
    )


# -------- CHECKOUT --------
@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if not login_required():
        return redirect("/login")

    total = calculate_cart_total()
    discount = session.get("discount", 0)
    final_total = max(total - discount, 0)

    if request.method == "POST":

        fullname = request.form.get("fullname", "").strip()
        card = request.form.get("card", "")

        if len(fullname.split()) < 2:
            return render_template("checkout.html", error="❌ Enter full name", total=final_total)

        if not card.isdigit() or len(card) != 16:
            return render_template("checkout.html", error="❌ Invalid card", total=final_total)

        conn = connect_db()

        conn.execute(
            "INSERT INTO orders(user_email,total) VALUES(?,?)",
            (session["user"], final_total)
        )

        # Add loyalty points
        user = conn.execute(
            "SELECT points FROM users WHERE email=?",
            (session["user"],)
        ).fetchone()

        points = get_points_for_tier(user["points"])

        conn.execute(
            "UPDATE users SET points = points + ? WHERE email=?",
            (points, session["user"])
        )

        conn.commit()
        conn.close()

        session["cart"] = []
        session.pop("discount", None)

        return redirect("/thank_you")

    return render_template("checkout.html", total=final_total)


# -------- THANK YOU --------
@app.route("/thank_you")
def thank_you():
    return render_template("thank_you.html")


# -------- LOGOUT --------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)