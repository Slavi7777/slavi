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


# ---------------- HASHING USERS PASSWORDS ----------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def login_required():
    return "user" in session


def is_valid_email(email):
    return re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email)


def is_strong_password(password):
    return re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{6,}$", password)


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


# ---------------- WEATHER API ----------------
def get_weather():
    try:
        api_key = "fefb3cbd29144bfeacd161529262703"

        url = f"http://api.weatherapi.com/v1/current.json?key={api_key}&q=London"

        response = requests.get(url).json()

        return {
            "temp": round(response["current"]["temp_c"]),
            "desc": response["current"]["condition"]["text"]
        }

    except:
        return {
            "temp": "--",
            "desc": "Weather unavailable"
        }


# ---------------- CART FUNCTION FOR CALCULATING THE TOTAL ----------------
def calculate_cart_total():
    total = 0
    for item in session.get("cart", []):
        total += item["price"] * item["quantity"]
    return total


# ----------------DATABASE ----------------
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

    # DEFAULT USERS (ADMIN AND PRODUCER)
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

    # ORDERS
    c.execute("""
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT,
        total REAL,
        tracking_number TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ORDER ITEMS
    c.execute("""
    CREATE TABLE IF NOT EXISTS order_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        product_name TEXT,
        quantity INTEGER,
        price REAL
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
    conn.close()

    weather = get_weather()

    return render_template("home.html", items=items, weather=weather)


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

            if user["role"] == "admin":
                return redirect("/admin")
            elif user["role"] == "producer":
                return redirect("/producer")
            return redirect("/")

        return render_template("login.html", error="❌ Invalid email or password")

    return render_template("login.html")

# -------- REGISTER --------
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
            return render_template(
                "register.html",
                error="❌ Email already exists"
            )
        finally:
            conn.close()

        return render_template("login.html", success="✅ Account created successfully")

    return render_template("register.html")


# -------- PRODUCTS --------
@app.route("/products")
def products():
    if not login_required():
        return redirect("/login")

    search = request.args.get("search")
    category = request.args.get("category")

    conn = connect_db()

    query = """
        SELECT products.*, categories.name AS category
        FROM products
        LEFT JOIN categories ON products.category_id = categories.id
        WHERE 1=1
    """

    params = []

    if search:
        query += " AND products.name LIKE ?"
        params.append(f"%{search}%")

    if category:
        query += " AND products.category_id = ?"
        params.append(category)

    items = conn.execute(query, params).fetchall()
    categories = conn.execute("SELECT * FROM categories").fetchall()

    conn.close()

    return render_template("products.html",
                           items=items,
                           categories=categories,
                           search=search,
                           selected_category=category)


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
        "image": product["image"],
        "quantity": 1
    })

    session.modified = True
    return redirect("/cart")


@app.route("/cart")
def cart():
    # 🔐 Check login
    if not login_required():
        return redirect("/login")

    # 🛒 Get cart from session
    cart_items = session.get("cart", [])

    # 💰 Calculate total (rounded for safety)
    total = round(calculate_cart_total(), 2)

    # 🎯 Render page
    return render_template(
        "cart.html",
        cart=cart_items,
        total=total
    )

# -------- CART INCREASE--------

@app.route("/increase/<int:id>")
def increase(id):
    for item in session.get("cart", []):
        if item["id"] == id:
            item["quantity"] += 1
    session.modified = True
    return redirect("/cart")

# -------- CART DECREASE--------

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

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if not login_required():
        return redirect("/login?message=Please login to checkout&next=cart")

    conn = connect_db()

    if request.method == "POST":

        # GET FORM DATA
        fullname = request.form.get("fullname", "").strip()
        cardname = request.form.get("cardname", "").strip()
        card = request.form.get("card", "")
        postcode = request.form.get("postcode", "")
        city = request.form.get("city", "").strip()
        county = request.form.get("county", "").strip()

        # FULL NAME
        if len(fullname.split()) < 2 or not all(part.isalpha() for part in fullname.split()):
            conn.close()
            return "Invalid full name"

        # CITY (STRONG VALIDATION)
        import re

        # CITY VALIDATION (STRICT)
        if not city or not re.fullmatch(r"[A-Za-z]{3,}(?: [A-Za-z]{2,})*", city):
            conn.close()
            return "Invalid city"

        # COUNTY VALIDATION (STRICT)
        if not county or not re.fullmatch(r"[A-Za-z]{3,}(?: [A-Za-z]{2,})*", county):
            conn.close()
            return "Invalid county"

        # CARD NUMBER
        if not card.isdigit() or len(card) != 16:
            conn.close()
            return "Invalid card number"

        # POSTCODE
        if len(postcode) < 5:
            conn.close()
            return render_template(
                "checkout.html",
                error="❌ Invalid postcode",
                cart=session.get("cart", []),
                total=round(calculate_cart_total(), 2),
                discount=session.get("discount", 0),
                final_total=max(
                    calculate_cart_total() + 5 + (calculate_cart_total() * 0.1) - session.get("discount", 0), 0)
            )

        # MATCH CARD NAME
        user = conn.execute(
            "SELECT first_name, last_name FROM users WHERE email=?",
            (session["user"],)
        ).fetchone()

        expected_name = f"{user['first_name']} {user['last_name']}".lower()

        if cardname.lower() != expected_name:
            conn.close()
            return "Cardholder name must match your account name"

        # GET CART
        cart_items = session.get("cart", [])

        # CHECK STOCK
        for item in cart_items:
            product = conn.execute(
                "SELECT stock FROM products WHERE id=?",
                (item["id"],)
            ).fetchone()

            if not product or product["stock"] < item["quantity"]:
                conn.close()
                return "Not enough stock for one of the items"

        # UPDATE STOCK
        for item in cart_items:
            conn.execute("""
                UPDATE products
                SET stock = stock - ?
                WHERE id = ?
            """, (item["quantity"], item["id"]))

        # CALCULATE FINAL TOTAL AGAIN (FOR SAFETY)
        total = calculate_cart_total()
        discount = session.get("discount", 0)
        final_total = max(total + 5 + (total * 0.1) - discount, 0)

        # CREATE ORDER
        # CREATE ORDER WITH TRACKING NUMBER
        import random
        import string

        tracking_number = "GLH-" + ''.join(
            random.choices(string.ascii_uppercase + string.digits, k=8)
        )

        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO orders(user_email, total, tracking_number)
            VALUES (?, ?, ?)
        """, (session["user"], final_total, tracking_number))

        order_id = cursor.lastrowid

        # SAVE ORDER ITEMS
        for item in cart_items:
            cursor.execute("""
                INSERT INTO order_items(order_id, product_name, quantity, price)
                VALUES (?, ?, ?, ?)
            """, (
                order_id,
                item["name"],
                item["quantity"],
                item["price"]
            ))

        #ADD LOYALTY POINTS AFTER SUCCESSFUL ORDER
        user_points = conn.execute(
            "SELECT points FROM users WHERE email=?",
            (session["user"],)
        ).fetchone()

        points_to_add = get_points_for_tier(user_points["points"])

        conn.execute(
            "UPDATE users SET points = points + ? WHERE email=?",
            (points_to_add, session["user"])
        )
        conn.commit()
        conn.close()

        # CLEAR CART
        session["cart"] = []
        session.modified = True
        #REMOVE DISCOUNT AFTER USE
        session.pop("discount", None)

        return redirect("/thank_you")

    #GET REQUEST
    cart_items = session.get("cart", [])
    total = round(calculate_cart_total(), 2)

    #GET DISCOUNT FROM SESSION
    discount = session.get("discount", 0)

    #FINAL TOTAL WITH DISCOUNT
    final_total = max(total + 5 + (total * 0.1) - discount, 0)

    return render_template(
        "checkout.html",
        cart=cart_items,
        total=total,
        discount=discount,
        final_total=final_total
    )

@app.route("/orders")
def orders():
    if not login_required():
        return redirect("/login")

    conn = connect_db()

    orders = conn.execute("""
        SELECT * FROM orders
        WHERE user_email=?
        ORDER BY created_at DESC
    """, (session["user"],)).fetchall()

    order_data = []

    for order in orders:
        items = conn.execute("""
            SELECT * FROM order_items
            WHERE order_id=?
        """, (order["id"],)).fetchall()

        order_data.append({
            "order": order,
            "items": items
        })

    conn.close()

    return render_template("orders.html", orders=order_data)

@app.route("/about")
def about():
    if not login_required():
        return redirect("/login")

    return render_template("about.html")

# -------- PRODUCER --------
@app.route("/producer")
def producer():
    if not login_required() or session.get("role") not in ["producer", "admin"]:
        return "Access Denied"

    conn = connect_db()
    items = conn.execute("""
        SELECT products.*, categories.name AS category
        FROM products
        LEFT JOIN categories ON products.category_id = categories.id
    """).fetchall()
    categories = conn.execute("SELECT * FROM categories").fetchall()
    conn.close()

    return render_template("producer_dashboard.html", items=items, categories=categories)


# -------- STOCK --------
@app.route("/increase_stock/<int:id>")
def increase_stock(id):
    conn = connect_db()
    conn.execute("UPDATE products SET stock = stock + 1 WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/producer")


@app.route("/decrease_stock/<int:id>")
def decrease_stock(id):
    conn = connect_db()
    conn.execute("UPDATE products SET stock = stock - 1 WHERE id=? AND stock > 0", (id,))
    conn.commit()
    conn.close()
    return redirect("/producer")


# -------- PRODUCT MANAGEMENT --------
@app.route("/add_product", methods=["GET", "POST"])
def add_product():
    if not login_required() or session.get("role") != "producer":
        return "Access Denied"

    conn = connect_db()

    if request.method == "POST":
        conn.execute("""
            INSERT INTO products(name, price, stock, image, category_id, description)
            VALUES(?,?,?,?,?,?)
        """, (
            request.form["name"],
            request.form["price"],
            request.form["stock"],
            request.form["image"],
            request.form["category"],
            request.form["description"]
        ))
        conn.commit()
        conn.close()
        return redirect("/producer")

    categories = conn.execute("SELECT * FROM categories").fetchall()
    conn.close()

    return render_template("add_product.html", categories=categories)


@app.route("/edit_product/<int:id>", methods=["GET", "POST"])
def edit_product(id):
    if not login_required() or session.get("role") != "producer":
        return "Access Denied"

    conn = connect_db()

    if request.method == "POST":
        conn.execute("""
            UPDATE products
            SET name=?, price=?, stock=?, image=?, category_id=?, description=?
            WHERE id=?
        """, (
            request.form["name"],
            request.form["price"],
            request.form["stock"],
            request.form["image"],
            request.form["category"],
            request.form["description"],
            id
        ))
        conn.commit()
        conn.close()
        return redirect("/producer")

    product = conn.execute("SELECT * FROM products WHERE id=?", (id,)).fetchone()
    categories = conn.execute("SELECT * FROM categories").fetchall()
    conn.close()

    return render_template("edit_product.html", product=product, categories=categories)


@app.route("/delete_product/<int:id>")
def delete_product(id):
    if not login_required() or session.get("role") != "producer":
        return "Access Denied"

    conn = connect_db()
    conn.execute("DELETE FROM products WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect("/producer")


# -------- LOYALTY PROGRAM--------
@app.route("/loyalty")
def loyalty():
    if not login_required():
        return redirect("/login")

    conn = connect_db()
    user = conn.execute("SELECT * FROM users WHERE email=?", (session["user"],)).fetchone()
    conn.close()

    tier = get_loyalty_tier(user["points"])

    return render_template("loyalty.html", user=user, tier=tier)


#ROUTES
@app.route("/contact", methods=["GET", "POST"])
def contact():
    if not login_required():
        return redirect("/login?message=Please login to contact us")

    message = None

    if request.method == "POST":
        form_email = request.form["email"]
        user_email = session.get("user")

        #vALIDATION
        if form_email != user_email:
            message = "❌ Email must match your account email"
        else:
            message = "✅ Message sent successfully!"



    return render_template("contact.html", message=message)

@app.route("/account", methods=["GET", "POST"])
def account():
    if not login_required():
        return redirect("/login")

    conn = connect_db()

    user = conn.execute(
        "SELECT * FROM users WHERE email=?",
        (session["user"],)
    ).fetchone()

    if request.method == "POST":
        fname = request.form["fname"]
        lname = request.form["lname"]

        conn.execute("""
            UPDATE users
            SET first_name=?, last_name=?
            WHERE email=?
        """, (fname, lname, session["user"]))

        conn.commit()

        #reload updated user
        user = conn.execute(
            "SELECT * FROM users WHERE email=?",
            (session["user"],)
        ).fetchone()

    conn.close()

    return render_template("account.html", user=user)

@app.route("/admin")
def admin():
    if not login_required() or session.get("role") != "admin":
        return "Access Denied"

    conn = connect_db()

    users = conn.execute("SELECT * FROM users").fetchall()
    products = conn.execute("SELECT * FROM products").fetchall()
    orders = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()

    #GET ORDER ITEMS
    order_items = {}
    for order in orders:
        items = conn.execute("""
            SELECT * FROM order_items WHERE order_id=?
        """, (order["id"],)).fetchall()

        order_items[order["id"]] = items

    conn.close()

    return render_template(
        "admin_dashboard.html",
        users=users,
        products=products,
        orders=orders,
        order_items=order_items
    )

@app.route("/thank_you")
def thank_you():
    return render_template("thank_you.html")

# -------- ERROR HANDLERS --------

@app.errorhandler(404)
def not_found(e):
    return render_template(
        "error.html",
        code=404,
        message="Page Not Found"
    ), 404


@app.errorhandler(500)
def server_error(e):
    return render_template(
        "error.html",
        code=500,
        message="Internal Server Error"
    ), 500

@app.route("/redeem/5off")
def redeem_5off():
    if not login_required():
        return redirect("/login")

    conn = connect_db()
    user = conn.execute(
        "SELECT points FROM users WHERE email=?",
        (session["user"],)
    ).fetchone()

    #CHECK POINTS
    if user["points"] < 100:
        conn.close()
        return "Not enough points"

    #EDUCT POINTS
    conn.execute(
        "UPDATE users SET points = points - 100 WHERE email=?",
        (session["user"],)
    )
    conn.commit()
    conn.close()

    #STORE DISCOUNT
    if "discount" in session:
        return "You already have an active discount"

    session["discount"] = 5

    return redirect("/cart")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


#Run
if __name__ == "__main__":
    app.run(debug=True)