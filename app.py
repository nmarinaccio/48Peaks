from flask import Flask, g, render_template, request, redirect, url_for, flash, session
from flask_session import Session
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from helpers import login_required

DATABASE = "48peaks.db"

# Configure application
app = Flask(__name__)

# Function to get the database connection
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row  # Allows dict-like access to rows
    return g.db

# Close the database connection when the app context ends
@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

# Configure session to use filesystem (instead of signed cookies)
app.secret_key = os.urandom(24)  # Generates a secure random key
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.route('/')
@login_required
def home():
    return render_template("home.html")

@app.route('/session_test')
def session_test():
    return str(session.get("user_id", "No session data"))

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "GET":
        session.clear()
        return render_template("login.html")

    # Retrieve form inputs
    username = request.form.get("username")
    password = request.form.get("password")

    # Check if username exists in the database
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    # Validate username and password
    if user and check_password_hash(user["hash"], password):
        # Successful login: Create a session key
        session["user_id"] = user["id"]
        flash("Login successful!", "success")
        return redirect(url_for("home"))
    else:
        # Invalid login: Show a generic error message
        flash("Username and Password do not match any existing account.", "error")
        return render_template("login.html")

    
@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    
    # Retrieve form inputs
    username = request.form.get("username")
    password = request.form.get("password")
    check_pw = request.form.get("check_password")
    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    email = request.form.get("email")
    
    # 1. Check that all fields are filled out
    if not username or not password or not check_pw or not first_name or not last_name or not email:
        flash("All fields are required. Please fill out the form completely.", "error")
        return render_template("register.html")
    
    # 2. Confirm that the username is not already in the users table
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if user:
        flash("Username already exists. Please choose a different username.", "error")
        return render_template("register.html")
    
    # 3. Confirm that both passwords match
    if password != check_pw:
        flash("Passwords do not match. Please try again.", "error")
        return render_template("register.html")
    
    # 4. Add the user to the database
    hashed_password = generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)
    try:
        db.execute(
            """
            INSERT INTO users (username, hash, first_name, last_name, email, created_date) 
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (username, hashed_password, first_name, last_name, email),
        )
        db.commit()
    except sqlite3.IntegrityError:
        flash("An error occurred while registering. Please try again.", "error")
        return render_template("register.html")
    
    # 5. Redirect to the login page
    flash("Registration successful! Please log in.", "success")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)