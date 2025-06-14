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
import subprocess # Added for running shell commands like vcgencmd
import psutil # Added for system monitoring (memory, disk usage)
import shutil # Added for disk usage

# --- PYGAME SETUP ---
pygame.init()
pygame.mixer.quit() # Disable audio to prevent ALSA errors
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
OFF_WHITE = (220, 220, 220) # A softer white for text
PALE_CYAN = (175, 238, 238) # A softer, non-white color for text
YELLOW = (255, 255, 0) # For sun
GREY = (150, 150, 150) # For clouds
ORANGE = (255, 165, 0) # For CPU temperature
PURPLE = (128, 0, 128) # For Memory usage
BROWN = (139, 69, 19) # For Storage usage

# Fonts
label_font_size = 40
value_font_size = 180 # Increased for larger numbers on the new gauge
min_max_font_size = 30
status_font_size = 30 # Re-added for status message

font_label = pygame.font.Font(None, label_font_size)
font_value = pygame.font.Font(None, value_font_size)
font_min_max = pygame.font.Font(None, min_max_font_size)
font_status = pygame.font.Font(None, status_font_size) # New font for status
font_cpu_temp = pygame.font.Font(None, 28) # Smaller font for CPU temp value
font_cpu_label = pygame.font.Font(None, 20) # Very small font for "CPU" label

# New fonts for clock and calendar
font_time = pygame.font.Font(None, 220) # Increased size
font_date = pygame.font.Font(None, 80) # Kept at 80
font_detail = pygame.font.Font(None, 50) # New font for wind/weather details

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
outdoor_weather_description = "N/A" # New global variable for weather description

# Function to fetch outside weather data
def get_outside_weather():
    global outdoor_temperature_c, outdoor_humidity, outdoor_wind_speed, outdoor_weather_description
    params = {
        "latitude": WOLFSBURG_LAT,
        "longitude": WOLFSBURG_LON,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code", # Added weather_code
        "temperature_unit": "celsius",
        # "timezone": "UTC" # Removed API timezone request
    }
    try:
        response = requests.get(WEATHER_API_URL, params=params, timeout=5)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        # print(f"API Response: {data}") # Added for debugging
        if "current" in data:
            outdoor_temperature_c = data["current"]["temperature_2m"]
            outdoor_humidity = data["current"]["relative_humidity_2m"]
            # Convert wind speed from m/s to km/h (1 m/s = 3.6 km/h)
            outdoor_wind_speed = data["current"]["wind_speed_10m"] * 3.6 # Convert to km/h
            weather_code = data["current"]["weather_code"]
            outdoor_weather_description = get_weather_description(weather_code)

            # print(f"Outside Weather: Temp={outdoor_temperature_c}°C, Humidity={outdoor_humidity}%, Wind={outdoor_wind_speed:.1f} km/h, Weather={outdoor_weather_description}")
        else:
            print("current data not found in API response.")
            outdoor_temperature_c = None
            outdoor_humidity = None
            outdoor_wind_speed = None
            outdoor_weather_description = "N/A"

    except requests.exceptions.RequestException as e:
        print(f"Error fetching outside weather: {e}")
        outdoor_temperature_c = None
        outdoor_humidity = None
        outdoor_wind_speed = None
        outdoor_weather_description = "N/A"

# New function to interpret WMO weather codes
def get_weather_description(code):
    if code == 0:
        return "Clear Sky"
    elif 1 <= code <= 3:
        return "Partly Cloudy"
    elif code in [45, 48]:
        return "Foggy"
    elif 51 <= code <= 57:
        return "Drizzle"
    elif 61 <= code <= 67:
        return "Rainy"
    elif 71 <= code <= 77:
        return "Snowy"
    elif 80 <= code <= 82:
        return "Rain Showers"
    elif 85 <= code <= 86:
        return "Snow Showers"
    elif 95 <= code <= 99:
        return "Thunderstorm"
    else:
        return "Unknown"

# --- MAIN LOOP VARIABLES ---
# Store last known good values
temperature_c = None
humidity = None

# New variables for smooth transitions
target_temperature_c = None
target_humidity = None
display_temperature_c = None
display_humidity = None
SMOOTHING_FACTOR = 0.05 # Increased for more visible transitions

# New variables for full circle animation
last_full_animation_time = 0  # Re-initializing at the global scope
FULL_ANIMATION_INTERVAL = 5000  # Every 5 seconds
FULL_ANIMATION_DURATION = 1500  # Animation lasts 1.5 seconds (full to actual)

# Simulation variables
sim_time = 0.0

# Timer for reading the sensor (in milliseconds)
# The DHT11 sensor is slow and should not be read more than once every 2 seconds.
READ_INTERVAL = 2000  # 2 seconds
last_read_time = 0

# Timer for fetching outside weather (e.g., every 5 minutes)
WEATHER_API_INTERVAL = 10 * 1000 # 10 seconds to stay within daily free tier limits
last_weather_api_read_time = 0

# Timer for reading CPU temperature (e.g., every 10 seconds)
CPU_TEMP_READ_INTERVAL = 10000 # 10 seconds
last_cpu_temp_read_time = 0

# Timer for reading Memory and Storage (e.g., every 10 seconds)
SYSTEM_STATS_READ_INTERVAL = 10000 # 10 seconds
last_system_stats_read_time = 0

# Global variable for CPU temperature
cpu_temperature_c = None

# Global variables for Memory and Storage
memory_percentage = None
storage_percentage = None

# Function to read CPU temperature
def get_cpu_temperature():
    global cpu_temperature_c
    try:
        # Run vcgencmd to get CPU temperature
        result = subprocess.run(['vcgencmd', 'measure_temp'], capture_output=True, text=True, check=True)
        output = result.stdout.strip()
        # Extract temperature (e.g., "temp=45.6'C")
        temp_str = output.split('=')[1].replace("'C", "")
        cpu_temperature_c = float(temp_str)
        # print(f"CPU Temperature: {cpu_temperature_c}°C") # For debugging
    except Exception as e:
        print(f"Error reading CPU temperature: {e}")
        cpu_temperature_c = None

# Function to get memory usage percentage
def get_memory_usage():
    global memory_percentage
    try:
        mem = psutil.virtual_memory()
        memory_percentage = mem.percent
        # print(f"Memory Usage: {memory_percentage}%") # For debugging
    except Exception as e:
        print(f"Error reading memory usage: {e}")
        memory_percentage = None

# Function to get storage usage percentage
def get_storage_usage():
    global storage_percentage
    try:
        total, used, free = shutil.disk_usage("/")
        storage_percentage = (used / total) * 100
        # print(f"Storage Usage: {storage_percentage:.1f}%") # For debugging
    except Exception as e:
        print(f"Error reading storage usage: {e}")
        storage_percentage = None

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

# New function to draw a rectangular gauge
def draw_gauge(surface, center_x, center_y, width, height, value, title, gauge_color, is_humidity):
    gauge_rect = pygame.Rect(center_x - width // 2, center_y - height // 2, width, height)
    pygame.draw.rect(surface, gauge_color, gauge_rect, border_radius=15) # Rounded corners
    pygame.draw.rect(surface, DARK_GREY, gauge_rect, 5, border_radius=15) # Border

    # Title
    draw_text(surface, title, font_label, PALE_CYAN, center_x, center_y - height // 2 - 20)

    # Value
    if value is not None:
        display_value = f"{int(round(value))}" if not is_humidity else f"{int(value)}"
        draw_text(surface, display_value, font_value, PALE_CYAN, center_x, center_y + 10) # Adjusted Y
    else:
        draw_text(surface, "N/A", font_value, PALE_CYAN, center_x, center_y)

# Function to draw the main screen
def draw_screen():
    screen.fill(BLACK)

    # Gauge dimensions and positions for the left half
    display_width = SCREEN_WIDTH // 2
    gauge_width = display_width * 0.4 # Make gauges occupy 40% of the half-screen width
    gauge_height = SCREEN_HEIGHT * 0.35 # Make gauges occupy 35% of the screen height

    # Spacing and positioning for gauges
    horizontal_gap = (display_width - (2 * gauge_width)) // 3
    vertical_gap = (SCREEN_HEIGHT - (2 * gauge_height)) // 3

    x_col1 = horizontal_gap + gauge_width // 2
    x_col2 = display_width - horizontal_gap - gauge_width // 2

    y_row1 = vertical_gap + gauge_height // 2
    y_row2 = y_row1 + gauge_height + vertical_gap

    # Indoor gauges
    draw_gauge(screen, x_col1, y_row1, gauge_width, gauge_height,
               display_temperature_c, "Indoor Temp", LIGHT_GREEN, is_humidity=False)
    draw_gauge(screen, x_col2, y_row1, gauge_width, gauge_height,
               display_humidity, "Indoor Humid", LIGHT_BLUE, is_humidity=True)

    # Outdoor gauges
    draw_gauge(screen, x_col1, y_row2, gauge_width, gauge_height,
               outdoor_temperature_c, "Outside Temp", LIGHT_GREEN, is_humidity=False)
    draw_gauge(screen, x_col2, y_row2, gauge_width, gauge_height,
               outdoor_humidity, "Outside Humid", LIGHT_BLUE, is_humidity=True)

    # Draw Clock, Calendar, Wind Speed, and Weather Description on the right half of the screen
    current_datetime = datetime.datetime.now()
    time_str = current_datetime.strftime("%H:%M")
    date_str = current_datetime.strftime("%A, %B %d")

    clock_calendar_center_x = SCREEN_WIDTH * 3 // 4

    # Adjusted Y positions for better spacing and to use font_detail
    clock_y = SCREEN_HEIGHT * 0.25
    date_y = clock_y + font_time.get_height() // 2 + 30 # Date below clock with good spacing
    wind_y = date_y + font_date.get_height() // 2 + 50 # Wind below date
    weather_y = wind_y + font_detail.get_height() + 10 # Weather below wind

    draw_text(screen, time_str, font_time, PALE_CYAN, clock_calendar_center_x, clock_y)
    draw_text(screen, date_str, font_date, PALE_CYAN, clock_calendar_center_x, date_y)

    # Draw Wind Speed with new font_detail
    if outdoor_wind_speed is not None:
        wind_speed_text = f"Wind: {outdoor_wind_speed:.1f} km/h"
        draw_text(screen, wind_speed_text, font_detail, PALE_CYAN, clock_calendar_center_x, wind_y)

    # Draw Weather Description with new font_detail
    weather_text_surface = font_detail.render(outdoor_weather_description, True, PALE_CYAN)
    weather_text_rect = weather_text_surface.get_rect(centerx=clock_calendar_center_x, centery=weather_y) # Revert to center
    screen.blit(weather_text_surface, weather_text_rect)

    # Draw Weather Icon below the text
    icon_size = 60 # Define icon size here for local use if needed
    icon_x = clock_calendar_center_x # Center icon horizontally
    icon_y = weather_y + font_detail.get_height() // 2 + 40 # Increased padding to move it further down
    draw_weather_icon(screen, icon_x, icon_y, outdoor_weather_description, icon_size=icon_size)

    # Draw CPU Temperature Circle
    if cpu_temperature_c is not None:
        cpu_circle_radius = 40 # Size of the CPU temp circle
        cpu_circle_x = clock_calendar_center_x # Center horizontally with other right-side elements
        cpu_circle_y = SCREEN_HEIGHT * 0.85 # Adjusted to be lower for horizontal row
        draw_cpu_temp_circle(screen, cpu_circle_x, cpu_circle_y, cpu_circle_radius, cpu_temperature_c)

    # Draw Memory Percentage Circle (Left of CPU)
    if memory_percentage is not None:
        mem_circle_radius = 40
        mem_circle_x = cpu_circle_x - cpu_circle_radius - mem_circle_radius - 20 # Position to the left of CPU, with padding
        mem_circle_y = cpu_circle_y # Same vertical position as CPU
        draw_percentage_circle(screen, mem_circle_x, mem_circle_y, mem_circle_radius, memory_percentage, "MEM", PURPLE)

    # Draw Storage Percentage Circle (Right of CPU)
    if storage_percentage is not None:
        storage_circle_radius = 40
        storage_circle_x = cpu_circle_x + cpu_circle_radius + storage_circle_radius + 20 # Position to the right of CPU, with padding
        storage_circle_y = cpu_circle_y # Same vertical position as CPU
        draw_percentage_circle(screen, storage_circle_x, storage_circle_y, storage_circle_radius, storage_percentage, "DISK", BROWN)

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
                # print(f"Read successful: Temp={target_temperature_c:.1f}°C, Humidity={target_humidity}%")
        else: # Simulation mode
            # Generate fake data that oscillates over time
            sim_time += 0.1 # Increment simulation time
            target_temperature_c = 25 + 5 * math.sin(sim_time) # Oscillate between 20 and 30
            target_humidity = 60 + 10 * math.cos(sim_time * 0.7) # Oscillate between 50 and 70
            # print("Running in simulation mode.")

    except RuntimeError as error:
        print(error.args[0])
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# New function to draw weather icons directly
def draw_weather_icon(surface, x, y, description, icon_size=60):
    center_x, center_y = x, y
    radius = icon_size // 3

    if description == "Clear Sky":
        # Sun
        pygame.draw.circle(surface, YELLOW, (center_x, center_y), radius)
        for i in range(8):
            angle = math.radians(i * 45)
            start_x = center_x + radius * math.cos(angle)
            start_y = center_y + radius * math.sin(angle)
            end_x = center_x + (radius + 10) * math.cos(angle)
            end_y = center_y + (radius + 10) * math.sin(angle)
            pygame.draw.line(surface, YELLOW, (start_x, start_y), (end_x, end_y), 3)
    elif description == "Partly Cloudy":
        # Sun
        pygame.draw.circle(surface, YELLOW, (center_x - radius, center_y - radius), radius // 1.5)
        # Cloud
        pygame.draw.circle(surface, GREY, (center_x + radius // 2, center_y + radius // 2), radius)
        pygame.draw.circle(surface, GREY, (center_x - radius // 2, center_y + radius // 2), radius * 0.8)
        pygame.draw.circle(surface, GREY, (center_x, center_y - radius // 2), radius * 0.7)
    elif description == "Foggy":
        # Simple grey cloud
        pygame.draw.circle(surface, GREY, (center_x, center_y), radius)
        pygame.draw.circle(surface, GREY, (center_x - radius // 2, center_y + radius // 4), radius * 0.7)
        pygame.draw.circle(surface, GREY, (center_x + radius // 2, center_y + radius // 4), radius * 0.7)
    elif description in ["Drizzle", "Rainy", "Rain Showers"]:
        # Cloud
        pygame.draw.circle(surface, GREY, (center_x, center_y), radius)
        pygame.draw.circle(surface, GREY, (center_x - radius // 2, center_y + radius // 4), radius * 0.7)
        pygame.draw.circle(surface, GREY, (center_x + radius // 2, center_y + radius // 4), radius * 0.7)
        # Rain drops
        for i in range(3):
            pygame.draw.line(surface, BLUE, (center_x - 15 + i * 15, center_y + radius + 5), (center_x - 15 + i * 15, center_y + radius + 15), 2)
    elif description in ["Snowy", "Snow Showers"]:
        # Cloud
        pygame.draw.circle(surface, GREY, (center_x, center_y), radius)
        pygame.draw.circle(surface, GREY, (center_x - radius // 2, center_y + radius // 4), radius * 0.7)
        pygame.draw.circle(surface, GREY, (center_x + radius // 2, center_y + radius // 4), radius * 0.7)
        # Snowflakes
        for i in range(3):
            pygame.draw.circle(surface, PALE_CYAN, (center_x - 15 + i * 15, center_y + radius + 10), 3)
    elif description == "Thunderstorm":
        # Dark cloud
        pygame.draw.circle(surface, DARK_GREY, (center_x, center_y), radius)
        pygame.draw.circle(surface, DARK_GREY, (center_x - radius // 2, center_y + radius // 4), radius * 0.7)
        pygame.draw.circle(surface, DARK_GREY, (center_x + radius // 2, center_y + radius // 4), radius * 0.7)
        # Lightning bolt
        points = [
            (center_x - 10, center_y + radius),
            (center_x + 5, center_y + radius + 15),
            (center_x - 5, center_y + radius + 15),
            (center_x + 10, center_y + radius + 30)
        ]
        pygame.draw.lines(surface, YELLOW, False, points, 2)
    else:
        # Unknown / Generic cloud
        pygame.draw.circle(surface, GREY, (center_x, center_y), radius)
        pygame.draw.circle(surface, GREY, (center_x - radius // 2, center_y + radius // 4), radius * 0.7)
        pygame.draw.circle(surface, GREY, (center_x + radius // 2, center_y + radius // 4), radius * 0.7)

# New function to draw CPU temperature in a circle
def draw_cpu_temp_circle(surface, center_x, center_y, radius, temperature):
    pygame.draw.circle(surface, ORANGE, (center_x, center_y), radius) # Orange circle
    pygame.draw.circle(surface, DARK_GREY, (center_x, center_y), radius, 3) # Dark grey border

    # Draw temperature value
    temp_text = f"{int(round(temperature))}°C"
    draw_text(surface, temp_text, font_cpu_temp, PALE_CYAN, center_x, center_y - 10) # Adjust Y for temp value

    # Draw "CPU" text
    draw_text(surface, "CPU", font_cpu_label, PALE_CYAN, center_x, center_y + 10) # Position below temp value, using new smaller font

# New generic function to draw a percentage in a circle
def draw_percentage_circle(surface, center_x, center_y, radius, percentage, label, color):
    pygame.draw.circle(surface, color, (center_x, center_y), radius) # Colored circle
    pygame.draw.circle(surface, DARK_GREY, (center_x, center_y), radius, 3) # Dark grey border

    # Draw percentage value
    percentage_text = f"{int(round(percentage))} %"
    draw_text(surface, percentage_text, font_cpu_temp, PALE_CYAN, center_x, center_y - 10) # Reuse font_cpu_temp

    # Draw label
    draw_text(surface, label, font_cpu_label, PALE_CYAN, center_x, center_y + 10) # Reuse font_cpu_label

# --- MAIN LOOP ---
running = True
while running:
    # Event handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN: # Added to handle key presses
            if event.key == pygame.K_ESCAPE: # Added to check for the escape key
                running = False # Set running to False to exit the loop

    current_time_ms = pygame.time.get_ticks() # Get current time in milliseconds
    # Trigger full animation at regular intervals
    # This block is no longer needed if gauges are always full.
    # if current_time_ms - last_full_animation_time > FULL_ANIMATION_INTERVAL:
    #     last_full_animation_time = current_time_ms

    # Read DHT11 sensor data at regular intervals
    if current_time_ms - last_read_time > READ_INTERVAL:
        read_sensor_data()
        last_read_time = current_time_ms

    # Fetch outside weather data at regular intervals
    if current_time_ms - last_weather_api_read_time > WEATHER_API_INTERVAL:
        get_outside_weather()
        last_weather_api_read_time = current_time_ms

    # Read CPU temperature at regular intervals
    if current_time_ms - last_cpu_temp_read_time > CPU_TEMP_READ_INTERVAL:
        get_cpu_temperature()
        last_cpu_temp_read_time = current_time_ms

    # Read Memory and Storage at regular intervals
    if current_time_ms - last_system_stats_read_time > SYSTEM_STATS_READ_INTERVAL:
        get_memory_usage()
        get_storage_usage()
        last_system_stats_read_time = current_time_ms

    # Smoothly update display values
    update_display_values()

    # Drawing
    draw_screen()

    # Update the display
    pygame.display.flip()

# Quit Pygame
pygame.quit()
sys.exit()