# Raspberry Pi Weather Display

This project displays indoor temperature and humidity from a DHT sensor and outdoor weather data (temperature, humidity, wind speed, and more) from the Open-Meteo API on a Raspberry Pi with a 7-inch HDMI LCD (H) display. It features a modern graphical user interface using Pygame, including gauges, a clock, a calendar, and system stats.

## Features

*   **Indoor Readings:** Displays real-time temperature and humidity from a DHT11/DHT22 sensor.
*   **Outdoor Weather:** Fetches and displays current outdoor temperature, humidity, wind speed, weather description, sunlight percentage, and "Feels Like" (apparent) temperature for a specified location using the Open-Meteo API.
*   **Daily High/Low:** Shows daily high and low outdoor temperatures in dedicated circles.
*   **Weather Details:** Displays weather description (e.g., Clear, Rainy, Foggy) and a weather icon, as well as sunlight percentage based on cloud cover.
*   **Wind Speed:** Shows current wind speed in km/h.
*   **System Stats:** Displays Raspberry Pi CPU temperature, memory usage, and storage usage in circular gauges.
*   **Graphical UI:** Pygame-based interface with large, clear gauges for indoor/outdoor readings, a digital clock, and a calendar.
*   **Dimming Overlay:** Adjustable dimming overlay for day/night or manual control, with a slider for user override.
*   **Full-screen Mode:** Optimized for a 7-inch display, runs in fullscreen.

## Hardware Requirements

*   Raspberry Pi (tested with Raspberry Pi 4)
*   DHT11 or DHT22 temperature and humidity sensor
*   Waveshare 7inch HDMI LCD (H) (SKU:14628) or compatible HDMI display

## Setup Instructions

1.  **Raspberry Pi OS:** Ensure you have Raspberry Pi OS (formerly Raspbian) installed on your Raspberry Pi. This project was developed on a Bullseye branch system.

2.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd <your-repository-name>
    ```

3.  **Python Virtual Environment:**
    It's recommended to use a Python virtual environment to manage dependencies.

    ```bash
    python3 -m venv myenv
    source myenv/bin/activate
    ```

4.  **Install Dependencies:**
    Install the required Python libraries.

    ```bash
    pip install adafruit-blinka adafruit-circuitpython-dht pygame requests psutil
    ```

5.  **DHT Sensor Wiring:**
    Connect your DHT sensor to the Raspberry Pi's GPIO pins as follows (adjust pin numbers if necessary, typical for DHT11/DHT22):

    *   **DHT Data Pin:** Connect to a GPIO pin (e.g., GPIO 4).
    *   **DHT VCC:** Connect to a 3.3V or 5V pin.
    *   **DHT GND:** Connect to a GND pin.

    *Note: You may need to run the script with `sudo` to access GPIO pins correctly.*

6.  **Display Configuration (Waveshare 7inch HDMI LCD (H)):**
    This display has an onboard OSD menu for brightness and contrast control. Software control of brightness is not directly supported without hardware modification. You can adjust brightness using the physical buttons on the display.

    Ensure your `/boot/firmware/config.txt` file has the `vc4-kms-v3d` overlay enabled for proper display operation.

    ```
    # Enable DRM VC4 V3D driver
    dtoverlay=vc4-kms-v3d
    max_framebuffers=2
    ```

## Running the Application

1.  **Activate Virtual Environment:**
    ```bash
    source myenv/bin/activate
    ```

2.  **Navigate to Project Directory:**
    ```bash
    cd <your-project-directory>
    ```

3.  **Run the Script:**
    ```bash
    python3 dhtui.py
    ```
    *   You might need to run with `sudo` for sensor access:
        ```bash
        sudo python3 dhtui.py
        ```

## Customization

*   **DHT Sensor Pin:** Modify the DHT pin in `dhtui.py` to match your sensor's data pin.
*   **Weather Location:** Change `WOLFSBURG_LAT` and `WOLFSBURG_LON` in `dhtui.py` to your desired location's latitude and longitude.
*   **UI Adjustments:** Modify Pygame rendering parameters (font sizes, positions, colors) in `dhtui.py` to customize the display.
*   **API Fields:** You can expand or change the weather data shown by editing the `get_outside_weather()` function and the API parameters in `dhtui.py`.
*   **Dimming Behavior:** Adjust day/night dimming levels or disable auto-dimming in the code.

## Weather Data Used

The application uses the following fields from the Open-Meteo API:
- **Current:** temperature, humidity, wind speed, weather code/description, apparent temperature (feels like), is_day, cloud cover (for sunlight %)
- **Daily:** high/low temperature
- **Other:** wind speed, weather icon, and more

You can easily add more fields (precipitation, UV index, sunrise/sunset, etc.) by updating the API call and UI.

## Brightness Control Note

Direct software control of the display brightness for the Waveshare 7inch HDMI LCD (H) (SKU:14628) is not readily available through standard Linux interfaces or tools like `xrandr`, `ddcutil`, or `/sys/class/backlight`. The display features an onboard OSD menu for manual brightness adjustment via its physical buttons. An advanced method involving hardware modification to the display board and PWM control via Raspberry Pi GPIO is documented on the Waveshare Wiki, but it is outside the scope of this software project. 
