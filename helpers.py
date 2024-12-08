import requests
import os
import random
from flask import redirect, render_template, session
from functools import wraps
from PIL import Image

# Login required function from CS50's Finance
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function

def get_weather(latitude, longitude, api_key):
    
    base_url = "http://api.openweathermap.org/data/2.5/weather"
    complete_url = f"{base_url}?lat={latitude}&lon={longitude}&appid={api_key}&units=imperial"  # Using Fahrenheit for temperature

    try:
        response = requests.get(complete_url)
        data = response.json()
        
        if data["cod"] != "404":
            main_data = data["main"]
            weather_data = data["weather"][0]
            
            weather = {
                "temperature": main_data["temp"],
                "pressure": main_data["pressure"],
                "humidity": main_data["humidity"],
                "description": weather_data["description"],
                "icon": weather_data["icon"],  # Weather icon code
            }
            return weather
        else:
            return None
    except Exception as e:
        print(f"Error fetching weather data: {e}")
        return None

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