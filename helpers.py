import requests
from flask import redirect, render_template, session
from functools import wraps

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