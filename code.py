from os import getenv
import board
import busio
from digitalio import DigitalInOut
import adafruit_connection_manager
import adafruit_requests
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_datetime import datetime, date, time
import time
import displayio
import adafruit_uc8151d
import adafruit_ntp
import rtc
import terminalio
from adafruit_display_text import label
import adafruit_il0373
import gc
import microcontroller
import alarm

try:
    from fourwire import FourWire
except ImportError:
    from displayio import FourWire

TIME_URL = "http://worldtimeapi.org/api/ip"
TIMEZONE = "America/New_York"
BLACK = 0x000000
WHITE = 0xFFFFFF
RED = 0xFF0000

# Power management settings
UPDATE_INTERVAL_HOURS = 2  # How often to update (in hours)
DEEP_SLEEP_ENABLED = True  # Enable deep sleep for power saving
# Change text colors, choose from the following values:
# BLACK, RED, WHITE
FOREGROUND_COLOR = BLACK
BACKGROUND_COLOR = WHITE

DISPLAY_WIDTH = 296
DISPLAY_HEIGHT = 128

# Set up GPIOs for the featherwing
# WiFi Chip Selects
wifi_cs = DigitalInOut(board.D13)
wifi_ready = DigitalInOut(board.D11)
wifi_reset = DigitalInOut(board.D12)

# eink display chip selects
epd_cs = board.D9
epd_dc = board.D10
epd_reset = board.D5
epd_busy = board.D6

# Functions to configure the Hardware
# SPI Transport configuration  (Display and Wifi Communication over SPI)
def configure_spi():
    print("starting configure_spi")
    displayio.release_displays()

    # This pinout works on a Feather M4 and may need to be altered for other boards.
    #    spi = board.SPI()  # Uses SCK and MOSI

    # Secondary (SCK1) SPI used to connect to WiFi board on Arduino Nano Connect RP2040
    spi = busio.SPI(board.SCK, board.MOSI, board.MISO)

    print("ending configure_spi")
    return spi

# Function to configure the Wifi board
def configure_wifi_hardware(spi):
    wifi = adafruit_esp32spi.ESP_SPIcontrol(spi, wifi_cs, wifi_ready, wifi_reset)

    if wifi.status == adafruit_esp32spi.WL_IDLE_STATUS:
        print("ESP32 found and in idle mode")
    print("Firmware vers.", wifi.firmware_version.decode("utf-8"))
    print("MAC addr:", ":".join("%02X" % byte for byte in wifi.MAC_address))

    pool = adafruit_connection_manager.get_radio_socketpool(wifi)
    ssl_context = adafruit_connection_manager.get_radio_ssl_context(wifi)
    requests = adafruit_requests.Session(pool, ssl_context)

    return wifi, pool, ssl_context, requests


#Function to Configure the Display
def configure_display(spi):
    print("configure display")
    # Used to ensure the display is free in CircuitPython
    displayio.release_displays()

    # This pinout works on a Feather M4 and may need to be altered for other boards.
    #    spi = board.SPI()  # Uses SCK and MOSI

    display_bus = FourWire(
        spi, command=epd_dc, chip_select=epd_cs, reset=epd_reset, baudrate=1000000
    )
    time.sleep(1)

    # Create the display object - the third color is red (0xff0000)
    display = adafruit_il0373.IL0373(
        display_bus,
        width=296,
        height=128,
        rotation=270,
        busy_pin=epd_busy,
        highlight_color=0xFF0000,
    )
    return display

# This will request Wifi to connect to my local router and then the internet
def connect_wifi(wifi):
    # Get wifi details and more from a settings.toml file
    # tokens used by this Demo: CIRCUITPY_WIFI_SSID, CIRCUITPY_WIFI_PASSWORD
    secrets = {
        "ssid": getenv("CIRCUITPY_WIFI_SSID"),
        "password": getenv("CIRCUITPY_WIFI_PASSWORD"),
    }

    if secrets == {"ssid": None, "password": None}:
        try:
            # Fallback on secrets.py until depreciation is over and option is removed
            from secrets import secrets
        except ImportError:
            print("WiFi secrets are kept in settings.toml, please add them there!")
            raise

    for ap in wifi.scan_networks():
        print("\t%-23s RSSI: %d" % (str(ap["ssid"], "utf-8"), ap["rssi"]))

    print("Connecting to AP...")
    while not wifi.is_connected:
        try:
            wifi.connect_AP(secrets["ssid"], secrets["password"])
        except OSError as e:
            print("could not connect to AP, retrying: ", e)
            continue
    print("Connected to", str(wifi.ssid, "utf-8"), "\tRSSI:", wifi.rssi)
    return wifi

# Optional to disconnect Wifi
def disconnect_wifi(wifi_connection, pool, ssl_context, requests):
    print("disconnecting from wifi")
    wifi_connection.disconnect()

# Update the Real Time clock on the MCU
def update_rtc_time(wifi_connection, pool, ssl_context, requests):
    print("updating RTC")
    try:
        with requests.get(TIME_URL) as response:
            time_data = response.json()
            tz_offset_str = time_data["utc_offset"]
            tz_hour_offset = int(tz_offset_str[0:3])
            tz_min_offset = int(tz_offset_str[4:6])

            # Handle negative timezone offsets correctly
            if tz_offset_str[0] == '-':
                tz_min_offset = -tz_min_offset

            unixtime = int(time_data["unixtime"] + (tz_hour_offset * 60 * 60) + (tz_min_offset * 60))
            rtc.RTC().datetime = time.localtime(unixtime)
    except Exception as e:
        print("Error updating RTC:", e)

# Create the time string that we'll be displaying
def CreateTimeString(item, now):
    the_datetime = datetime.fromisoformat(item["t"])
    theTime = ""
    print(now, the_datetime)

    # Only show future tides (tides that haven't happened yet)
    if now < the_datetime:
        hour = the_datetime.hour % 12
        if hour == 0:
            hour = 12
        am_pm = "AM"
        if the_datetime.hour >= 12:
            am_pm = "PM"

        if item["type"] == "L":
            tide_type = "Low "
        else:
            tide_type = "High"

        theTime = (
            "{:2d}".format(the_datetime.month)
            + "/"
            + "{:02d}".format(the_datetime.day)
            + " "
            + tide_type
            + " "
            + "{:2d}".format(hour)
            + ":"
            + "{:02d}".format(the_datetime.minute)
            + " "
            + am_pm
        )
    print(theTime)
    return theTime

# Query the NOAA endpoint closest to PTown for the Local tide information
def get_tide_info(requests):

    today = datetime.now()

    tom_time_struct = time.localtime(time.time() + 24*3600)

    # Construct the URL to use Today's date and tomorrow's date
    TIDE_URL = (
        "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?begin_date=" +
        str(today.year) +
        '{:02d}{:02d}'.format(today.month,today.day) +
        "&end_date=" +
        str(tom_time_struct.tm_year) +
        '{:02d}{:02d}'.format(tom_time_struct.tm_mon, tom_time_struct.tm_mday) +
        "&station=8446121&product=predictions&datum=MLLW&time_zone=lst_ldt&interval=hilo&units=english&format=json"
    )

    print(TIDE_URL)
    pTownTides = []

    try:
        # get the Tide information
        with requests.get(TIDE_URL) as tides:
            tide_data = tides.json()
            if "predictions" not in tide_data:
                print("No predictions data in response")
                return pTownTides

            for item in tide_data["predictions"]:
                # the_datetime is now a datetime type
                theTime = CreateTimeString(item, today)
                if theTime != "":
                    pTownTides.append(theTime)
                    # Limit to 4 future tides
                    if len(pTownTides) >= 4:
                        break
    except Exception as e:
        print("Error fetching tide data:", e)
        return pTownTides

    return pTownTides

# Display the tide info on the display
def display_things(display, tides):
    print("entering display_things")

    # Create a hash of the tide data to check if it's changed
    tide_hash = hash(str(tides))

    # Check if tide data has changed (stored in sleep memory)
    if alarm.sleep_memory[1] == tide_hash:
        print("Tide data unchanged, skipping display update")
        return

    # Store the new hash
    alarm.sleep_memory[1] = tide_hash

    # Create a display group for our screen objects
    g = displayio.Group()

    gc.collect()
    start_mem = gc.mem_free()
    print( "Point 3 Available memory: {} bytes".format(start_mem) )
    # Set a background
    background_bitmap = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)

    # Map colors in a palette
    palette = displayio.Palette(1)
    palette[0] = BACKGROUND_COLOR

    # Create a Tilegrid with the background and put in the displayio group
    t = displayio.TileGrid(background_bitmap, pixel_shader=palette)
    g.append(t)

    # Draw simple text using the built-in font into a displayio group
    text_group = displayio.Group(scale=2, x=10, y=20)
    text = ""

    for tide in tides:
        text += tide
        text += "\n"

    text_area = label.Label(terminalio.FONT, text=text, color=FOREGROUND_COLOR)

    text_group.append(text_area)  # Add this text to the text group
    g.append(text_group)

    # Place the display group on the screen
    display.root_group = g

    # Refresh the display to have everything show on the display
    # NOTE: Do not refresh eInk displays more often than 180 seconds!
    display.refresh()

    # Give the e-ink display time to complete the refresh cycle
    time.sleep(5)

    del background_bitmap
    del g
    del text_area
    del text_group
    del t
    gc.collect()
    start_mem = gc.mem_free()
    print("Point 1 Available memory: {} bytes".format(start_mem))
    print("leaving display_things")

# Defining main function
def main():
    gc.enable()

    # Check if we're waking from deep sleep
    if alarm.wake_alarm:
        print("Waking from deep sleep")
    else:
        print("Starting fresh")

    spi = configure_spi()
    #    display_things()
    wifi, pool, ssl_context, requests = configure_wifi_hardware(spi)
    display = configure_display(spi)
    wifi_connection = connect_wifi(wifi)
    count = 0
    while True:
        # It seems like the display controller can get hung up
        # if we run into this exception 5 times let's just reset the
        # processor
        if count > 5:
            print("we got 5 exceptions")
            microcontroller.reset()
        try:
            print("going to start at the beginning")
            if not wifi_connection.is_connected:
                wifi_connection = connect_wifi(wifi)

            update_rtc_time(wifi, pool, ssl_context, requests)

            tides = get_tide_info(requests)

            gc.collect()
            start_mem = gc.mem_free()
            print( "Point 2 Available memory: {} bytes".format(start_mem) )

            # Only update display if we have tide data
            if tides:
                display_things(display, tides)
            else:
                print("No tide data available, skipping display update")

                        # Disconnect WiFi to save power
            disconnect_wifi(wifi_connection, pool, ssl_context, requests)

            # Use deep sleep instead of regular sleep to save power
            sleep_seconds = UPDATE_INTERVAL_HOURS * 60 * 60
            print(f"Going to deep sleep for {UPDATE_INTERVAL_HOURS} hours...")
            alarm.sleep_memory[0] = 1  # Set a flag to indicate we've run
            alarm.exit_and_deep_sleep_until_alarms(alarm.time.TimeAlarm(monotonic_time=time.monotonic() + sleep_seconds))

        except Exception as e:
            print("we got an exception:", e)
            count = count + 1


# Using the special variable
# __name__
if __name__ == "__main__":
    main()
