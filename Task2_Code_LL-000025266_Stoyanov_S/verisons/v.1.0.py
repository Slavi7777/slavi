from flask import Flask, session
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