import time
import board
import adafruit_dht # Temporarily commented out to run in simulation mode
import pygame
import sys
import math
import os # Added for environment variables
import requests # Added for making HTTP requests to weather API
import datetime # Added for clock and calendar
from pygame.locals import * # Added for QUIT and KEYDOWN

# --- PYGAME SETUP ---
pygame.init()
pygame.mouse.set_visible(False) # Hide the mouse cursor

# Environment variables for Raspberry Pi framebuffer (Temporarily commented out)
os.environ['SDL_VIDEODRIVER'] = 'fbcon'
os.environ['SDL_FBDEV'] = '/dev/fb1'
os.environ['SDL_MOUSEDRV'] = 'TSLIB'
os.environ['SDL_MOUSEDEV'] = '/dev/input/touchscreen'

# Screen dimensions
info = pygame.display.Info()
SCREEN_WIDTH = info.current_w
SCREEN_HEIGHT = info.current_h
# Set the screen to half width for gauges, and leave the other half for clock/calendar
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN) # Re-enabled FULLSCREEN
pygame.display.set_caption("DHT11 Sensor Data")

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (214, 72, 54)   # A nice red for temperature
BLUE = (62, 142, 208)  # A nice blue for humidity
DARK_GREY = (50, 50, 50) # For gauge background
LIGHT_GREEN = (0, 200, 100) # For temperature gauge
LIGHT_BLUE = (0, 150, 255) # For humidity gauge

# Fonts
label_font_size = 40
value_font_size = 120 # Increased for larger numbers
min_max_font_size = 30
status_font_size = 30 # Re-added for status message

font_label = pygame.font.Font(None, label_font_size)
font_value = pygame.font.Font(None, value_font_size)
font_min_max = pygame.font.Font(None, min_max_font_size)
font_status = pygame.font.Font(None, status_font_size) # New font for status

# New fonts for clock and calendar
font_time = pygame.font.Font(None, 150)
font_date = pygame.font.Font(None, 60)

# --- SENSOR SETUP ---
# Set up DHT11 sensor on GPIO 4 (physical pin 7)
try:
    dht_device = adafruit_dht.DHT11(board.D4) # Temporarily commented out to run in simulation mode
    # dht_device = None # Force simulation mode for now
except Exception as e:
    print(f"Failed to initialize DHT11 sensor: {e}")
    print("This script will run in simulation mode.")
    dht_device = None # Set to None to handle simulation

# --- WEATHER API SETUP ---
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
WOLFSBURG_LAT = 52.427547
WOLFSBURG_LON = 10.780420

# Store last known good outside values
outdoor_temperature_c = None
outdoor_humidity = None
outdoor_wind_speed = None # New global variable for wind speed

# Function to fetch outside weather data
def get_outside_weather():
    global outdoor_temperature_c, outdoor_humidity, outdoor_wind_speed
    params = {
        "latitude": WOLFSBURG_LAT,
        "longitude": WOLFSBURG_LON,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m", # Added wind_speed_10m
        "temperature_unit": "celsius",
        # "timezone": "UTC" # Removed API timezone request
    }
    try:
        response = requests.get(WEATHER_API_URL, params=params, timeout=5)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        print(f"API Response: {data}") # Added for debugging
        if "current" in data:
            outdoor_temperature_c = data["current"]["temperature_2m"]
            outdoor_humidity = data["current"]["relative_humidity_2m"]
            # Convert wind speed from m/s to km/h (1 m/s = 3.6 km/h)
            outdoor_wind_speed = data["current"]["wind_speed_10m"] * 3.6 # Convert to km/h

            print(f"Outside Weather: Temp={outdoor_temperature_c}°C, Humidity={outdoor_humidity}%, Wind={outdoor_wind_speed:.1f} km/h")
        else:
            print("current data not found in API response.")
            outdoor_temperature_c = None
            outdoor_humidity = None
            outdoor_wind_speed = None

    except requests.exceptions.RequestException as e:
        print(f"Error fetching outside weather: {e}")
        outdoor_temperature_c = None
        outdoor_humidity = None
        outdoor_wind_speed = None

# --- MAIN LOOP VARIABLES ---
# Store last known good values
temperature_c = None
humidity = None

# New variables for smooth transitions
target_temperature_c = None
target_humidity = None
display_temperature_c = None
display_humidity = None
SMOOTHING_FACTOR = 0.2 # Increased for more visible transitions

# Simulation variables
sim_time = 0.0

# Timer for reading the sensor (in milliseconds)
# The DHT11 sensor is slow and should not be read more than once every 2 seconds.
READ_INTERVAL = 2000  # 2 seconds
last_read_time = 0

# Timer for fetching outside weather (e.g., every 5 minutes)
WEATHER_API_INTERVAL = 10 * 1000 # 10 seconds to stay within daily free tier limits
last_weather_api_read_time = 0

# Helper function to draw text
def draw_text(surface, text, font, color, x, y, align='center'):
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect()
    if align == 'center':
        text_rect.centerx = x
    elif align == 'right':
        text_rect.right = x
    else:
        text_rect.left = x
    text_rect.centery = y
    surface.blit(text_surface, text_rect)

# New function to draw a circular gauge
def draw_gauge(surface, center_x, center_y, radius, value, min_val, max_val, title, gauge_color, value_color, is_humidity):
    # Draw background circle
    pygame.draw.circle(surface, DARK_GREY, (center_x, center_y), radius, 10) # 10 is thickness

    # Draw the colored arc only if value is not None
    if value is not None:
        if max_val - min_val == 0:
            sweep_angle = 0
        else:
            normalized_value = (value - min_val) / (max_val - min_val)
            # Clamp normalized_value between 0 and 1
            normalized_value = max(0, min(1, normalized_value))

            # Arc goes from 135 degrees (start) to 45 degrees (end) clockwise, a 270 degree sweep
            start_angle_rad = math.radians(135)
            end_angle_rad = math.radians(135 + (normalized_value * 270)) # 270 degree sweep

            rect = pygame.Rect(center_x - radius, center_y - radius, radius * 2, radius * 2)
            pygame.draw.arc(surface, gauge_color, rect, start_angle_rad, end_angle_rad, 10)

    # Draw title (e.g., "Indoor Temp", "Outdoor Humid")
    draw_text(surface, title, font_label, WHITE, center_x, center_y - radius - 20)

    # Draw value in center
    if value is not None:
        display_value = f"{value:.1f}" if not is_humidity else f"{int(value)}"
        draw_text(surface, display_value, font_value, value_color, center_x, center_y + 10) # Adjusted Y for center
    else:
        draw_text(surface, "N/A", font_value, value_color, center_x, center_y)

# Function to draw the main screen
def draw_screen():
    screen.fill(BLACK)

    # Gauge dimensions and positions for the left half
    display_width = SCREEN_WIDTH // 2 # Only use half the window width for gauges
    gauge_radius = min(display_width, SCREEN_HEIGHT) // 4.5

    # Calculate padding to ensure elements are centered and spaced nicely within the display_width
    total_gauge_width = 2 * (gauge_radius * 2) # two gauges, twice the radius
    vertical_space_for_gauges = 2 * (gauge_radius * 2) # Total height occupied by two rows of gauges

    padding_x = (display_width - total_gauge_width) // 3 # Padding for horizontal alignment
    padding_y_between_rows = (SCREEN_HEIGHT - vertical_space_for_gauges) // 3 # More space between rows

    # X positions for left and right columns within the *display_width*
    x_col1 = padding_x + gauge_radius
    x_col2 = display_width - padding_x - gauge_radius

    # Y positions for top and bottom rows
    y_row1 = padding_y_between_rows + gauge_radius
    y_row2 = y_row1 + (gauge_radius * 2) + padding_y_between_rows

    # Indoor gauges (top row, left half)
    draw_gauge(screen, x_col1, y_row1,
               gauge_radius, display_temperature_c, 0, 50, "Indoor Temp", LIGHT_GREEN, WHITE, is_humidity=False)
    draw_gauge(screen, x_col2, y_row1,
               gauge_radius, display_humidity, 0, 100, "Indoor Humid", LIGHT_BLUE, WHITE, is_humidity=True)

    # Outdoor gauges (bottom row, left half)
    draw_gauge(screen, x_col1, y_row2,
               gauge_radius, outdoor_temperature_c, 0, 50, "Outside Temp", LIGHT_GREEN, WHITE, is_humidity=False)
    draw_gauge(screen, x_col2, y_row2,
               gauge_radius, outdoor_humidity, 0, 100, "Outside Humid", LIGHT_BLUE, WHITE, is_humidity=True)

    # Draw Clock and Calendar on the right half of the screen
    current_datetime = datetime.datetime.now()
    time_str = current_datetime.strftime("%H:%M")
    date_str = current_datetime.strftime("%A, %B %d")

    clock_calendar_center_x = SCREEN_WIDTH * 3 // 4 # Center of the right half

    # Adjusted Y positions to lift the display up
    draw_text(screen, time_str, font_time, WHITE, clock_calendar_center_x, SCREEN_HEIGHT // 2 - 100)
    draw_text(screen, date_str, font_date, WHITE, clock_calendar_center_x, SCREEN_HEIGHT // 2 + 10)

    # Draw Wind Speed below clock/calendar
    if outdoor_wind_speed is not None:
        wind_speed_text = f"Wind: {outdoor_wind_speed:.1f} km/h"
        draw_text(screen, wind_speed_text, font_date, WHITE, clock_calendar_center_x, SCREEN_HEIGHT // 2 + 100)

    pygame.display.flip()

# Function to smoothly update display values
def update_display_values():
    global display_temperature_c, display_humidity, target_temperature_c, target_humidity

    if target_temperature_c is not None and display_temperature_c is None:
        display_temperature_c = target_temperature_c
    elif target_temperature_c is not None:
        display_temperature_c += (target_temperature_c - display_temperature_c) * SMOOTHING_FACTOR

    if target_humidity is not None and display_humidity is None:
        display_humidity = target_humidity
    elif target_humidity is not None:
        display_humidity += (target_humidity - display_humidity) * SMOOTHING_FACTOR

# Function to read DHT11 sensor data
def read_sensor_data():
    global temperature_c, humidity, target_temperature_c, target_humidity, sim_time
    try:
        if dht_device: # Only read if the sensor was initialized
            temp_c_reading = dht_device.temperature
            humidity_reading = dht_device.humidity

            if temp_c_reading is not None and humidity_reading is not None:
                target_temperature_c = temp_c_reading # Update target values
                target_humidity = humidity_reading
                print(f"Read successful: Temp={target_temperature_c:.1f}°C, Humidity={target_humidity}%")
        else: # Simulation mode
            # Generate fake data that oscillates over time
            sim_time += 0.1 # Increment simulation time
            target_temperature_c = 25 + 5 * math.sin(sim_time) # Oscillate between 20 and 30
            target_humidity = 60 + 10 * math.cos(sim_time * 0.7) # Oscillate between 50 and 70
            print("Running in simulation mode.")

    except RuntimeError as error:
        print(error.args[0])
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# --- MAIN LOOP ---
running = True
while running:
    # Event handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    current_time_ms = pygame.time.get_ticks() # Get current time in milliseconds

    # Read DHT11 sensor data at regular intervals
    if current_time_ms - last_read_time > READ_INTERVAL:
        read_sensor_data()
        last_read_time = current_time_ms

    # Fetch outside weather data at regular intervals
    if current_time_ms - last_weather_api_read_time > WEATHER_API_INTERVAL:
        get_outside_weather()
        last_weather_api_read_time = current_time_ms

    # Smoothly update display values
    update_display_values()

    # Drawing
    draw_screen()

    # Update the display
    pygame.display.flip()

# Quit Pygame
pygame.quit()
sys.exit()