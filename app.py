# Standard library imports
import os
import sqlite3
from datetime import datetime

# Third-party library imports
import pytz
from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# Local application/library-specific imports
from helpers import login_required

DATABASE = "48peaks.db"

est = pytz.timezone('US/Eastern')
utc = pytz.utc

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


ALLOWED_EXTENSIONS = {'jpg', 'jpeg'}
UPLOAD_FOLDER_PHOTO = 'static/images/user_photos/profile_photos'
UPLOAD_FOLDER_BANNER = 'static/images/user_photos/profile_page_background'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.context_processor
def inject_user():
    if "user_id" in session:
        user_id = session["user_id"]
        # Execute a query to fetch the profile_photo from the database
        db = get_db()
        user = db.execute("SELECT profile_photo FROM users WHERE id = ?", (user_id,)).fetchone()
        if user and user["profile_photo"]:
            return {"profile_photo": user["profile_photo"]}
    return {"profile_photo": None}  # Default if not logged in or no photo


@app.route('/')
@login_required
def home():
    return render_template("home.html")

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


@app.route('/logout')
@login_required
def logout():
    flash("Successfully logged out", "success")
    return redirect('login')

@app.route('/mountain/<int:mountain_id>', methods=["GET", "POST"])
@login_required
def mountain_page(mountain_id):
    # Get the database connection
    db = get_db()
    
    if request.method == "GET":
        # Fetch mountain details
        mountain = db.execute("SELECT * FROM mountains WHERE id = ?", (mountain_id,)).fetchone()
        
        # Handle case where the mountain is not found
        if not mountain:
            flash("Mountain not found.", "error")
            return redirect(url_for("home"))  # Redirect to the homepage or an appropriate page

        # Fetch comments for the mountain
        comments = db.execute("""
            SELECT comments.id, comments.timestamp, comments.message, 
                users.username, users.profile_photo, comments.user_id
            FROM comments
            JOIN users ON comments.user_id = users.id
            WHERE comments.mountain_id = ?
            ORDER BY comments.timestamp DESC
        """, (mountain_id,)).fetchall()

        # Format timestamps and convert to EST
        formatted_comments = []
        for comment in comments:
            # Parse the UTC timestamp string into a datetime object
            utc_time = datetime.strptime(comment['timestamp'], "%Y-%m-%d %H:%M:%S")
            utc_time = utc.localize(utc_time)  # Localize to UTC
            
            # Convert to EST
            est_time = utc_time.astimezone(est)
            
            # Format the time as a nice string
            formatted_time = est_time.strftime("%b %d, %Y, %I:%M %p EST")

            summit = db.execute("SELECT * FROM summits WHERE user_id = ? AND mountain_id = ?", (comment['user_id'], mountain_id)).fetchone()

            if summit:
                summitted = 1
            else:
                summitted = 0

            
            # Append the comment with the formatted timestamp
            formatted_comments.append({
                "id": comment['id'],
                "timestamp": formatted_time,
                "message": comment['message'],
                "username": comment['username'],
                "profile_photo": comment['profile_photo'],
                "summitted": summitted
            })

        return render_template("mountain_page.html", mountain=mountain, comments=formatted_comments)

    # Handle POST request to add a comment
    comment = request.form.get("comment")
    if comment:
        user_id = session.get("user_id")  # Get the user_id from the session
        
        if not user_id:
            flash("You must be logged in to post a comment.", "error")
            return redirect(url_for("login"))
        
        try:
            # Insert the comment into the database
            db.execute(
                """
                INSERT INTO comments (user_id, mountain_id, message)
                VALUES (?, ?, ?)
                """,
                (user_id, mountain_id, comment)
            )
            db.commit()
            flash("Comment posted successfully!", "success")
        except sqlite3.Error as e:
            flash("An error occurred while posting your comment. Please try again.", "error")
            print(f"Database error: {e}")
        
        # Redirect to the same mountain page to avoid duplicate form submission
        return redirect(url_for("mountain_page", mountain_id=mountain_id))    



@app.route('/profile', methods=["GET"])
@login_required
def profile_page():
    db = get_db()
    user_id = session.get("user_id")
    
    # Fetch user details
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("home"))

    # Fetch progress stats (already handled)
    peaks_summitted = db.execute("SELECT COUNT(DISTINCT mountain_id) FROM summits WHERE user_id = ?", (user_id,)).fetchone()[0] or 0
    days_hiked = db.execute("SELECT COUNT(DISTINCT date_hiked) FROM summits WHERE user_id = ?", (user_id,)).fetchone()[0] or 0
    elevation_hiked = db.execute("""
        SELECT SUM(m.elevation) 
        FROM mountains m 
        JOIN summits s ON m.id = s.mountain_id 
        WHERE s.user_id = ?
    """, (user_id,)).fetchone()[0] or 0
    last_hike = db.execute("""
        SELECT MAX(date_hiked) 
        FROM summits 
        WHERE user_id = ?
    """, (user_id,)).fetchone()[0]

    # Format last_hike date if it exists
    if last_hike:
        last_hike = datetime.strptime(last_hike, "%Y-%m-%d").strftime("%m/%d/%Y")
    else:
        last_hike = "No Hikes Logged"

    # Fetch recent summits
    recent_summits_query = db.execute("""
        SELECT 
            s.date_hiked, 
            COALESCE(s.notes, m.mountain_blurb) AS notes, 
            m.name AS mountain_name, 
            m.mountain_photo 
        FROM summits s
        JOIN mountains m ON s.mountain_id = m.id
        WHERE s.user_id = ?
        ORDER BY s.date_hiked DESC
        LIMIT 5
    """, (user_id,))
    recent_summits = recent_summits_query.fetchall()

    # Truncate notes or blurb to two lines in the backend and format dates
    def truncate_text(text, max_length=350):
        return text if len(text) <= max_length else text[:max_length].rsplit(' ', 1)[0] + '...'

    recent_summits = [
        {
            "date_hiked": datetime.strptime(summit["date_hiked"], "%Y-%m-%d").strftime("%m/%d/%Y"),
            "notes": truncate_text(summit["notes"]),
            "mountain_name": summit["mountain_name"],
            "mountain_photo": summit["mountain_photo"],
        }
        for summit in recent_summits
    ]

    # Calculate progress percentage
    summits_progress = round((peaks_summitted / 48) * 100, 2) if peaks_summitted else 0

    return render_template(
        "profile_page.html", 
        user=user,
        peaks_summitted=peaks_summitted,
        days_hiked=days_hiked,
        elevation_hiked=elevation_hiked,
        last_hike=last_hike,
        summits_progress=summits_progress,
        recent_summits=recent_summits
    )


@app.route('/edit-profile', methods=["GET", "POST"])
@login_required
def edit_profile():
    db = get_db()
    user_id = session.get("user_id")

    # Fetch user details for GET
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    if request.method == "POST":
        # Validate inputs
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")
        phone_number = request.form.get("phone_number")
        bio = request.form.get("bio")

        if not first_name or not last_name or not email:
            flash("First name, last name, and email are required.", "error")
            return redirect(url_for("edit_profile"))

        # Handle profile photo upload
        profile_photo = request.files.get("profile_photo")
        if profile_photo and allowed_file(profile_photo.filename):
            photo_filename = secure_filename(f"{user_id}.jpg")
            profile_photo.save(os.path.join(UPLOAD_FOLDER_PHOTO, photo_filename))

        # Handle profile banner upload
        profile_banner = request.files.get("profile_banner")
        if profile_banner and allowed_file(profile_banner.filename):
            banner_filename = secure_filename(f"{user_id}.jpg")
            profile_banner.save(os.path.join(UPLOAD_FOLDER_BANNER, banner_filename))

        # Update user in database
        try:
            db.execute("""
                UPDATE users 
                SET first_name = ?, last_name = ?, email = ?, phone_number = ?, bio = ?, profile_photo = ?, profile_banner = ?
                WHERE id = ?
            """, (
                first_name,
                last_name,
                email,
                phone_number,
                bio,
                f"{user_id}.jpg" if profile_photo else user["profile_photo"],
                f"{user_id}.jpg" if profile_banner else user["profile_banner"],
                user_id
            ))
            db.commit()
            flash("Profile updated successfully!", "success")
        except Exception as e:
            flash("An error occurred while updating your profile.", "error")
            print(e)
        return redirect(url_for("profile_page"))

    return render_template("edit_profile.html", user=user)


@app.route('/my-peaks', methods=["GET", "POST"])
@login_required
def my_peaks():
    db = get_db()
    user_id = session.get("user_id")

    if request.method == "POST":
        # Handle comment posting logic
        comment = request.form.get("comment")
        summit_id = request.form.get("summit_id")

        if not comment or not summit_id:
            flash("Comment and Summit ID are required.", "error")
            return redirect(url_for('my_peaks'))

        try:
            db.execute(
                """
                INSERT INTO summit_comments (user_id, summit_id, message)
                VALUES (?, ?, ?)
                """,
                (user_id, summit_id, comment)
            )
            db.commit()
            flash("Comment posted successfully!", "success")
        except Exception as e:
            flash("An error occurred while posting your comment.", "error")
            print(f"Database error: {e}")
        return redirect(url_for('my_peaks'))

    # Fetch all peaks logged by the user, order by most recent first
    peaks_query = db.execute("""
        SELECT 
            s.id AS summit_id,
            s.date_hiked,
            s.notes,
            m.name AS mountain_name,
            m.elevation,
            m.mountain_photo,
            s.summit_picture
        FROM summits s
        JOIN mountains m ON s.mountain_id = m.id
        WHERE s.user_id = ?
        ORDER BY s.date_hiked DESC
    """, (user_id,))
    peaks = peaks_query.fetchall()

    # Fetch all comments for user's summits
    comments_query = db.execute("""
        SELECT 
            c.summit_id,
            c.message,
            c.timestamp,
            c.edited,
            c.edited_at,
            u.username,
            u.profile_photo
        FROM summit_comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.summit_id IN (SELECT id FROM summits WHERE user_id = ?)
        ORDER BY c.timestamp ASC
    """, (user_id,))
    comments = comments_query.fetchall()

    # Format data for peaks and comments
    formatted_peaks = []
    formatted_comments = {}

    for index, peak in enumerate(reversed(peaks), start=1):  # Label oldest peak as 1
        formatted_peaks.append({
            "summit_id": peak["summit_id"],
            "peak_number": index,
            "date_hiked": datetime.strptime(peak["date_hiked"], "%Y-%m-%d").strftime("%m/%d/%Y"),
            "notes": peak["notes"],
            "mountain_name": peak["mountain_name"],
            "elevation": peak["elevation"],
            "mountain_photo": peak["mountain_photo"],
            "summit_picture": peak["summit_picture"] if peak["summit_picture"] else peak["mountain_photo"]
        })

    for comment in comments:
        summit_id = comment["summit_id"]
        if summit_id not in formatted_comments:
            formatted_comments[summit_id] = []
        formatted_comments[summit_id].append({
            "message": comment["message"],
            "timestamp": datetime.strptime(comment["timestamp"], "%Y-%m-%d %H:%M:%S").strftime("%b %d, %Y, %I:%M %p"),
            "edited": comment["edited"],
            "edited_at": comment["edited_at"],
            "username": comment["username"],
            "profile_photo": comment["profile_photo"] if comment["profile_photo"] else "default.jpg"
        })

    # Preload the most recent peak details
    recent_peak = formatted_peaks[0] if formatted_peaks else None

    num_of_peaks = len(formatted_peaks)

    # Render the template with peaks and comments
    return render_template(
        "my_peaks.html",
        peaks=formatted_peaks,
        comments=formatted_comments,
        recent_peak=recent_peak,
        num_of_peaks=num_of_peaks
    )


@app.route('/get-peak-details/<int:summit_id>', methods=['GET'])
@login_required
def get_peak_details(summit_id):
    db = get_db()
    user_id = session.get("user_id")

    # Query the summit details
    summit = db.execute("""
        SELECT s.id AS summit_id, s.date_hiked, s.notes, s.summit_picture,
               m.name AS mountain_name, m.elevation, m.mountain_photo, m.mountain_blurb
        FROM summits s
        JOIN mountains m ON s.mountain_id = m.id
        WHERE s.id = ? AND s.user_id = ?
    """, (summit_id, user_id)).fetchone()

    if not summit:
        return jsonify({"error": "Summit not found"}), 404

    # Query the comments for this summit
    comments_query = db.execute("""
        SELECT sc.message, sc.timestamp, sc.edited, u.username, u.profile_photo
        FROM summit_comments sc
        JOIN users u ON sc.user_id = u.id
        WHERE sc.summit_id = ?
        ORDER BY sc.timestamp ASC
    """, (summit_id,))
    comments = comments_query.fetchall()

    # Format comments
    formatted_comments = [
        {
            "message": comment["message"],
                    "timestamp": (
            utc.localize(datetime.strptime(comment["timestamp"], "%Y-%m-%d %H:%M:%S")).astimezone(est).strftime("%b %d, %Y, %I:%M %p %Z")),
            "edited": comment["edited"],
            "username": comment["username"],
            "profile_photo": comment["profile_photo"] if comment["profile_photo"] else "default.jpg"
        }
        for comment in comments
    ]

    # Prepare the JSON response
    response = {
        "summit_id": summit["summit_id"],
        "name": summit["mountain_name"],
        "date_hiked": datetime.strptime(summit["date_hiked"], "%Y-%m-%d").strftime("%m/%d/%Y"),
        "notes": summit["notes"],
        "blurb": summit["mountain_blurb"],
        "photo": summit["summit_picture"] if summit["summit_picture"] else f'/static/images/mountain_images/{summit["mountain_photo"]}',
        "image": f'/static/images/mountain_images/{summit["mountain_photo"]}',
        "comments": formatted_comments
    }

    return jsonify(response)


if __name__ == "__main__":
    app.run(debug=True)

