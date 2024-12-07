# Standard library imports
from datetime import datetime
import json
import os
import random
import sqlite3

# Third-party library imports
from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from flask_session import Session
from PIL import Image
import pytz
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# Local application/library-specific imports
from helpers import login_required
from helpers import get_weather

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

# Function to return a random background
def get_bg():
    directory = "./static/images/background_images"
    try:
        # List all files in the directory
        files = os.listdir(directory)

        # Filter out non-files (e.g., directories)
        files = [f for f in files if os.path.isfile(os.path.join(directory, f))]

        if not files:
            raise ValueError("No files found in the specified directory.")

        # Randomly select a file
        random_file = random.choice(files)
        return random_file
    except FileNotFoundError:
        raise FileNotFoundError("The specified directory does not exist.")
    except Exception as e:
        raise RuntimeError(f"An error occurred: {e}")

def compress_image_to_limit(input_path, output_path=None, max_size_mb=1, initial_quality=85, step=5):
    max_size_bytes = max_size_mb * 1024 * 1024  # Convert MB to bytes
    if output_path is None:
        output_path = input_path  # Overwrite the original file

    try:
        with Image.open(input_path) as img:
            img = img.convert("RGB")  # Ensure compatibility
            quality = initial_quality

            # Save and check the size iteratively
            while True:
                img.save(output_path, optimize=True, quality=quality)
                if os.path.getsize(output_path) <= max_size_bytes or quality <= step:
                    break  # Stop if under size or quality is too low
                quality -= step  # Reduce quality further

            return output_path
    except Exception as e:
        print(f"Error compressing image: {e}")
        raise

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


ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'wpeb'}
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
    db = get_db()
    bg = get_bg()
    user_id = session.get("user_id")

    # Get following information
    following_unformatted = db.execute("SELECT f.followee_id AS user_id, u.username, u.profile_photo FROM followers f JOIN users u ON f.followee_id = u.id WHERE f.follower_id = ? ORDER BY u.username", (user_id,)).fetchall()
    following = []

    for user in following_unformatted:
        following.append({
            "user_id": user['user_id'],
            "username": user['username'],
            "pfp": user['profile_photo']
        })
    
    # Get recent post information
    recent_posts_unformatted = db.execute("""
        SELECT s.id, s.user_id, s.summit_picture, u.username, u.profile_photo
        FROM summits s
        JOIN users u
        ON s.user_id = u.id
        WHERE s.user_id IN (
            SELECT followee_id FROM followers WHERE follower_id = ?
        )
        ORDER BY date_hiked DESC
        LIMIT 4
    """, (user_id,))
    recent_posts = []

    for post in recent_posts_unformatted:
        recent_posts.append({
            "id": post['id'],
            "user_id": post['user_id'],
            "username": post['username'],
            "pfp": post['profile_photo'],
            "picture": post['summit_picture']
        })

    # Get suggested peaks information

    # First, fetch peaks the user hasn't hiked yet
    unhiked_peaks_unformatted = db.execute(
        """
        SELECT id, mountain_photo, name
        FROM mountains
        WHERE id NOT IN (
            SELECT mountain_id
            FROM summits
            WHERE user_id = ?
        )
        ORDER BY RANDOM()
        LIMIT 3
        """
        , (user_id,)
    ).fetchall()

    # If fewer than 3 peaks are found, fetch additional peaks the user has hiked
    if len(unhiked_peaks_unformatted) < 3:
        # Calculate how many more peaks are needed
        remaining_needed = 3 - len(unhiked_peaks_unformatted)

        # Fetch random peaks that the user has hiked
        hiked_peaks = db.execute(
            """
            SELECT id, mountain_photo, name
            FROM mountains
            WHERE id IN (
                SELECT mountain_id
                FROM summits
                WHERE user_id = ?
            )
            ORDER BY RANDOM()
            LIMIT ?
            """
            , (user_id, remaining_needed)
        ).fetchall()

        # Combine the two lists
        unhiked_peaks_unformatted.extend(hiked_peaks)

    # Create a list of dictionaries for the recommended peaks
    recommended_peaks = [
        {"id": peak["id"], "photo": peak["mountain_photo"], "name": peak["name"]}
        for peak in unhiked_peaks_unformatted
    ]

    return render_template("home.html",
        following=following,
        posts=recent_posts,
        recommended_peaks=recommended_peaks,
        background=bg
    )



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
    
    user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Directory to store user photos
    base_dir = "/static/images/user_photos/summit_photos/"
    user_folder = os.path.join(base_dir, str(user_id))

    # Create the user's folder
    os.makedirs(user_folder, exist_ok=True)

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

        long = mountain['longitude']
        lat = mountain['latitude']
        api_key = '80dd128965351d9428d255aa831259c0'
        
        weather = get_weather(lat, long, api_key)

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

        return render_template("mountain_page.html", mountain=mountain, weather=weather, comments=formatted_comments)

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
    peaks_summitted = db.execute("SELECT COUNT(DISTINCT mountain_id) FROM summits WHERE user_id = ? AND mountain_id != 0", (user_id,)).fetchone()[0] or 0
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
            s.id AS id,
            s.date_hiked, 
            COALESCE(s.notes, m.mountain_blurb) AS notes, 
            m.name AS mountain_name, 
            m.mountain_photo 
        FROM summits s
        JOIN mountains m ON s.mountain_id = m.id
        WHERE s.user_id = ?
        AND s.mountain_id != 0
        ORDER BY s.date_hiked DESC
        LIMIT 5
    """, (user_id,))
    recent_summits = recent_summits_query.fetchall()

    # Fetch follower count
    follower_count_query = db.execute("SELECT COUNT(*) AS count FROM followers WHERE followee_id = ?", (user_id,))

    # Fetch the count from the first (and only) row
    follower_count = follower_count_query.fetchone()[0]

    # Truncate notes or blurb to two lines in the backend and format dates
    def truncate_text(text, max_length=350):
        return text if len(text) <= max_length else text[:max_length].rsplit(' ', 1)[0] + '...'

    recent_summits = [
        {
            "post_id": summit["id"],
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
        recent_summits=recent_summits,
        followers=follower_count
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
        AND s.mountain_id != 0
        ORDER BY s.id
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

@app.route('/post', methods=['GET', 'POST'])
@login_required
def post():
    db = get_db()
    user_id = session.get("user_id")

    if request.method == 'POST':
        # Retrieve form inputs
        mountain_id = request.form.get('mountain_id')
        date_hiked = request.form.get('date_hiked')
        notes = request.form.get('notes')
        summit_picture = None

        # Retrieve friend IDs from the JSON string
        friends_json = request.form.get('friends', '[]')  # Default to an empty list if not provided
        try:
            friends = json.loads(friends_json)
        except json.JSONDecodeError:
            friends = []

        # Check required fields
        if not mountain_id or not date_hiked or not notes:
            flash("Mountain, date, caption are required fields.", "error")
            return redirect(url_for('post'))

        # Handle image upload
        if 'summit-photo' in request.files:
            file = request.files['summit-photo']
            if file and file.filename:
                filename = secure_filename(file.filename)
                summit_picture = f"/static/images/user_photos/summit_photos/{user_id}-{mountain_id}.jpg"
                file_path = os.path.join('static', 'images', 'user_photos', 'summit_photos')
                os.makedirs(file_path, exist_ok=True)  # Ensure directory exists
                full_file_path = os.path.join(file_path, f"{user_id}-{mountain_id}.jpg")
                file.save(full_file_path)

                if os.path.getsize(full_file_path) > 1 * 1024 * 1024:  # File size > 1MB
                    try:
                        compress_image_to_limit(full_file_path, max_size_mb=1)
                    except Exception as e:
                        flash("Error compressing image. Please try again.", "error")
                        return redirect(url_for('post'))

        # Fetch the latest post_id
        check_post_id = db.execute("SELECT post_id FROM summits ORDER BY post_id DESC LIMIT 1").fetchone()

        # Determine the new post_id
        if check_post_id and check_post_id['post_id'] is not None:
            new_post_id = check_post_id['post_id'] + 1
        else:
            new_post_id = 1  # Default to 1 if there are no existing rows

        try:
            # Insert the main user's hike
            db.execute("""
                INSERT INTO summits (user_id, mountain_id, date_hiked, notes, summit_picture, post_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, mountain_id, date_hiked, notes, summit_picture, new_post_id))
            db.commit()

            # Insert rows for friends
            for friend_id in friends:
                # Check if a row with the same friend_id and mountain_id already exists
                existing_entry = db.execute("""
                    SELECT 1 FROM summits 
                    WHERE user_id = ? AND mountain_id = ?
                    LIMIT 1
                """, (friend_id, mountain_id)).fetchone()

                if existing_entry:
                    # If a matching row exists, insert a new row with only friend_id, post_id, and mountain_id = 0
                    db.execute("""
                        INSERT INTO summits (user_id, mountain_id, date_hiked, notes, summit_picture, post_id)
                        VALUES (?, 0, ?, NULL, NULL, ?)
                    """, (friend_id, date_hiked, new_post_id))
                else:
                    # Otherwise, insert the full row
                    db.execute("""
                        INSERT INTO summits (user_id, mountain_id, date_hiked, notes, summit_picture, post_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (friend_id, mountain_id, date_hiked, notes, summit_picture, new_post_id))
                
                # Commit after each operation
                db.commit()


            flash("Post created successfully!", "success")
            return redirect(url_for('home', post_id=new_post_id))
        except Exception as e:
            flash(f"An error occurred: {e}", "error")

    # Populate mountains dropdown
    mountains = db.execute("""
        SELECT id, name FROM mountains 
        WHERE id NOT IN (SELECT mountain_id FROM summits WHERE user_id = ?)
    """, (user_id,)).fetchall()

    return render_template('post.html', mountains=mountains)


@app.route('/user/<int:user_id>', methods=["GET"])
@login_required
def user_page(user_id):
    db = get_db()
    viewer_id = session.get("user_id")

    if user_id == viewer_id:
        return redirect("/profile")
    
    # Fetch user details
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("home"))

    # Fetch progress stats
    peaks_summitted = db.execute("SELECT COUNT(DISTINCT mountain_id) FROM summits WHERE user_id = ? AND mountain_id != 0", (user_id,)).fetchone()[0] or 0
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
            s.id AS id,
            s.date_hiked, 
            COALESCE(s.notes, m.mountain_blurb) AS notes, 
            m.name AS mountain_name, 
            m.mountain_photo 
        FROM summits s
        JOIN mountains m ON s.mountain_id = m.id
        WHERE s.user_id = ?
        AND s.mountain_id != 0
        ORDER BY s.date_hiked DESC
        LIMIT 5
    """, (user_id,))
    recent_summits = recent_summits_query.fetchall()

    # Fetch follower count
    follower_count_query = db.execute("SELECT COUNT(*) AS count FROM followers WHERE followee_id = ?", (user_id,))
    follower_count = follower_count_query.fetchone()[0]

    following_query = db.execute(
        "SELECT id FROM followers WHERE followee_id = ? AND follower_id = ?", 
        (user_id, viewer_id)
    ).fetchone()

    if following_query:
        following = True  # If a record is found
    else:
        following = False  # If no record is found

    # Truncate notes or blurb and format dates
    def truncate_text(text, max_length=350):
        return text if len(text) <= max_length else text[:max_length].rsplit(' ', 1)[0] + '...'

    recent_summits = [
        {
            "post_id": summit["id"],
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
        "user_page.html", 
        user=user,
        peaks_summitted=peaks_summitted,
        days_hiked=days_hiked,
        elevation_hiked=elevation_hiked,
        last_hike=last_hike,
        summits_progress=summits_progress,
        recent_summits=recent_summits,
        followers=follower_count,
        following=following
    )



# Web service APIs

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


@app.route('/friend-search')
@login_required
def friend_search():
    db = get_db()
    user_id = session.get("user_id")
    query = request.args.get('query', '').strip()

    if not query:
        return jsonify([])  # Return empty array if no query is provided

    # Search for users whose names match the query (case-insensitive) and exclude the current user
    friends = db.execute("""
        SELECT id, first_name || ' ' || last_name AS name
        FROM users
        WHERE (first_name LIKE ? OR last_name LIKE ?) AND id != ?
        ORDER BY first_name ASC
    """, (f"%{query}%", f"%{query}%", user_id)).fetchall()

    # Convert query results to JSON
    friend_list = [{"id": friend["id"], "name": friend["name"]} for friend in friends]

    return jsonify(friend_list)


@app.route('/post-search')
@login_required
def post_search():
    db = get_db()
    current_user_id = session.get("user_id")
    post_id = request.args.get('post_id', '').strip()

    if not post_id:
        return jsonify({"code": 404, "message": "Post ID not provided", "data": {}})

    # Fetch the post information
    post_info = db.execute(
        """
        SELECT 
            s.id, 
            s.user_id, 
            s.date_hiked, 
            s.notes, 
            s.summit_picture,
            u.username AS poster_username,
            u.profile_photo AS poster_profile_photo
        FROM summits s
        JOIN users u ON s.user_id = u.id
        WHERE s.id = ? AND s.mountain_id != 0
        """,
        (post_id,)
    ).fetchone()

    if not post_info:
        return jsonify({"code": 404, "message": "Post not found", "data": {}})

    # Fetch the comments associated with the post
    comments = db.execute(
        """
        SELECT 
            u.id AS id,
            u.username, 
            u.profile_photo, 
            s.timestamp, 
            s.message 
        FROM summit_comments s
        JOIN users u ON s.user_id = u.id
        WHERE s.summit_id = ?
        ORDER BY s.timestamp ASC
        """,
        (post_info["id"],)
    ).fetchall()

    unformatted_likes = db.execute(
        """
        SELECT 
            COUNT(DISTINCT user_id) AS count, -- Total number of unique likes
            GROUP_CONCAT(user_id) AS user_ids -- Concatenate user IDs for checking
        FROM post_likes
        WHERE post_id = ?
        """,
        (post_info["id"],)
    ).fetchone()

    # Extract like count
    like_count = unformatted_likes["count"] if unformatted_likes and unformatted_likes["count"] else 0

    # Check if the current user has liked the post
    current_user_liked = 0
    if unformatted_likes and unformatted_likes["user_ids"]:
        liked_user_ids = unformatted_likes["user_ids"].split(",")  # Convert to list
        if str(current_user_id) in liked_user_ids:
            current_user_liked = 1

    # Format the comments
    formatted_comments = [
        {
            "user_id": comment["id"],
            "username": comment["username"],
            "profile_photo": comment["profile_photo"] if comment["profile_photo"] else "default.jpg",
            "timestamp": comment["timestamp"],
            "message": comment["message"]
        }
        for comment in comments
    ]

    # Prepare the response
    return_json = {
        "code": 200,
        "data": {
            "poster": {
                "user_id": post_info["user_id"],
                "username": post_info["poster_username"],
                "profile_photo": post_info["poster_profile_photo"] if post_info["poster_profile_photo"] else "default.jpg"
            },
            "date": post_info["date_hiked"],
            "likes": like_count,
            "user_liked": current_user_liked,
            "caption": post_info["notes"],
            "picture": post_info["summit_picture"],
            "comments": formatted_comments
        }
    }

    return jsonify(return_json)

@app.route('/toggle-like', methods=['POST'])
@login_required
def toggle_like():
    db = get_db()
    user_id = session["user_id"]
    post_id = request.json.get("post_id")

    if not post_id:
        return jsonify({"code": 400, "message": "Post ID is required"}), 400

    try:
        # Check if the user already liked the post
        existing_like = db.execute(
            "SELECT id FROM post_likes WHERE post_id = ? AND user_id = ?",
            (post_id, user_id)
        ).fetchone()

        if existing_like:
            # If already liked, remove the like
            db.execute("DELETE FROM post_likes WHERE id = ?", (existing_like["id"],))
            liked = False
        else:
            # If not liked, add a new like
            db.execute(
                "INSERT INTO post_likes (post_id, user_id) VALUES (?, ?)",
                (post_id, user_id)
            )
            liked = True

        db.commit()

        # Get the updated like count
        like_count = db.execute(
            "SELECT COUNT(*) AS count FROM post_likes WHERE post_id = ?",
            (post_id,)
        ).fetchone()["count"]

        return jsonify({"code": 200, "liked": liked, "like_count": like_count}), 200

    except Exception as e:
        print(f"Error toggling like: {e}")
        return jsonify({"code": 500, "message": "Internal Server Error"}), 500

@app.route('/post-comment', methods=['POST'])
@login_required
def post_comment():
    db = get_db()
    user_id = session["user_id"]

    try:
        # Ensure request is JSON
        if not request.is_json:
            return jsonify({"code": 400, "message": "Invalid request format. JSON expected."}), 400

        # Extract the required data
        post_id = request.json.get("post_id")
        message = request.json.get("message")

        if not post_id or not message:
            return jsonify({"code": 400, "message": "Post ID and message are required."}), 400

        # Insert the comment into the database
        db.execute(
            """
            INSERT INTO summit_comments (summit_id, user_id, message)
            VALUES (?, ?, ?)
            """,
            (post_id, user_id, message)
        )
        db.commit()

        # Get the user's username and profile photo for the comment
        user_info = db.execute(
            "SELECT username, profile_photo FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        return jsonify({
            "code": 200,
            "message": "Comment posted successfully.",
            "data": {
                "username": user_info["username"],
                "profile_photo": user_info["profile_photo"] if user_info["profile_photo"] else "default.jpg",
                "comment": message
            }
        }), 200

    except Exception as e:
        print(f"Error posting comment: {e}")
        return jsonify({"code": 500, "message": "Internal Server Error"}), 500

@app.route('/follow-toggle', methods=['POST'])
@login_required
def follow_toggle():
    db = get_db()
    user_id = session["user_id"]

    try:
        # Ensure request is JSON
        if not request.is_json:
            return jsonify({"code": 400, "message": "Invalid request format. JSON expected."}), 400

        followee_id = request.json.get("followee_id")
        
        if not followee_id:
            return jsonify({"code": 400, "message": "Post ID and message are required."}), 400
        
        existing_follow = db.execute("SELECT id FROM followers WHERE follower_id = ? AND followee_id = ?", (user_id, followee_id)).fetchone()

        if existing_follow:
            db.execute("DELETE FROM followers WHERE id = ?", (str(existing_follow['id']),))
            db.commit()
            following = False
        else:
            db.execute("INSERT INTO followers (follower_id, followee_id) VALUES (?,?)", (user_id, followee_id))
            db.commit()
            following = True

        follow_count = db.execute("SELECT COUNT(*) AS count FROM followers WHERE followee_id = ?", (followee_id)).fetchone()["count"]

        return jsonify({"code": 200, "follow": following, "follow_count": follow_count}), 200

    except Exception as e:
        print(f"Error following: {e}")
        return jsonify({"code": 500, "message": "Internal Server Error"}), 500

if __name__ == "__main__":
    app.run(debug=True)
