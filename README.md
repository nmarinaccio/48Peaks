# 48Peaks

## Project Overview

48Peaks allows users to track their hiking adventures in the 48 4,000+ footers of the White Mountains in New Hampshire. Users can create an account, post about their hikes, and follow/interact with others for inspiration and community building. The app also provides a platform for leaving comments on summits and mountains, making it easy to share experiences and tips with other hikers.

## Features
- User registration and login
- Post hike records with summit pictures and notes
- Comment on summits and mountains
- Follow other users and interact with their content
- User profiles with a customizable bio and profile picture

## Installation Instructions

1. Clone the repository:

    ```bash
    git clone <repository-url>
    cd <project-directory>
    ```

2. Set up a virtual environment (optional but recommended):

    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

4. Run the app:

    ```bash
    python3 app.py
    ```

5. Navigate to `http://127.0.0.1:5000` in your browser to access the app.

## Configuration

- Ensure that the app's configuration (e.g., database settings, secret key) is correctly set in `app.py`.
- Optionally, configure a session secret key for Flask to handle user sessions securely.

## Usage

After setting up the app and running it locally, you can:
- Register an account and log in.
- Create and edit posts for hikes, including summit photos and notes.
- Comment on summits and interact with other users' posts.
- Follow users to stay updated on their new posts and hikes.
- Search the mountain database to plan new hikes

## Presentation Video

-URL

## Testing

To run tests, use a testing framework like `pytest` or unit tests. Example:

```bash
pytest tests/

