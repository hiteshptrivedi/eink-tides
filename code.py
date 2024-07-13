# SPDX-FileCopyrightText: 2019 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

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

try:
    from fourwire import FourWire
except ImportError:
    from displayio import FourWire

TIME_URL = "http://worldtimeapi.org/api/ip"
TIMEZONE = "America/New_York"
BLACK = 0x000000
WHITE = 0xFFFFFF
RED = 0xFF0000
# Change text colors, choose from the following values:
# BLACK, RED, WHITE
FOREGROUND_COLOR = BLACK
BACKGROUND_COLOR = WHITE

DISPLAY_WIDTH = 296
DISPLAY_HEIGHT = 128

# for the featherwing
wifi_cs = DigitalInOut(board.D13)
wifi_ready = DigitalInOut(board.D11)
wifi_reset = DigitalInOut(board.D12)
# eink display
epd_cs = board.D9
epd_dc = board.D10
epd_reset = board.D5
epd_busy = board.D6


def configure_spi():
    print("starting configure_spi")
    displayio.release_displays()

    # This pinout works on a Feather M4 and may need to be altered for other boards.
    #    spi = board.SPI()  # Uses SCK and MOSI

    # Secondary (SCK1) SPI used to connect to WiFi board on Arduino Nano Connect RP2040
    spi = busio.SPI(board.SCK, board.MOSI, board.MISO)

    print("ending configure_spi")
    return spi


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


def update_rtc_time(wifi_connection, pool, ssl_context, requests):
    print("updating RTC")
    with requests.get(TIME_URL) as response:
        time_data = response.json()
        tz_hour_offset = int(time_data["utc_offset"][0:3])
        tz_min_offset = int(time_data["utc_offset"][4:6])
        if tz_hour_offset < 0:
            tz_min_offset *= -1
        unixtime = int(time_data["unixtime"] + (tz_hour_offset * 60 * 60)) + (
            tz_min_offset * 60
        )
        rtc.RTC().datetime = time.localtime(unixtime)


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

def disconnect_wifi(wifi_connection, pool, ssl_context, requests):
    print("disconnecting from wifi")
    wifi_connection.disconnect()

def CreateTimeString(item, now):
    the_datetime = datetime.fromisoformat(item["t"])
    theTime = ""
    count = 0
    print(count, now, the_datetime)
    if ((now < the_datetime) and (count < 4)):
        count = count + 1
        hour = the_datetime.hour % 12
        if hour == 0:
            hour = 12
        am_pm = "AM"
        if the_datetime.hour / 12 >= 1:
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

def get_tide_info(requests):

    #    TIDE_URL_TODAY = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=today&range=48&station=8446121&product=predictions&datum=MLLW&time_zone=lst_ldt&interval=hilo&units=english&application=DataAPI_Sample&format=json"
    #    TIDE_URL_TOMORROW = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=tomorrow&range=48&station=8446121&product=predictions&datum=MLLW&time_zone=lst_ldt&interval=hilo&units=english&application=DataAPI_Sample&format=json"
    #    TIDE_URL_BEGIN = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?begin_date=20240628&end_date=20240629&station=8446121&product=predictions&datum=MLLW&time_zone=lst_ldt&interval=hilo&units=english&format=json"
    today = datetime.now()

    tom_time_struct = time.localtime(time.time() + 24*3600)

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

    with requests.get(TIDE_URL) as tides:
        for item in tides.json()["predictions"]:
            # the_datetime is now a datetime type
            theTime = CreateTimeString(item, today)
            if theTime != "":
                pTownTides.append(theTime)

    return pTownTides


def display_things(display, tides):
    print("entering display_things")

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

    # Set scaling factor for display text
    my_scale = 1


    text_group.append(text_area)  # Add this text to the text group
    g.append(text_group)

    # Place the display group on the screen
    display.root_group = g

    # Refresh the display to have everything show on the display
    # NOTE: Do not refresh eInk displays more often than 180 seconds!
    display.refresh()

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
    spi = configure_spi()
    #    display_things()
    wifi, pool, ssl_context, requests = configure_wifi_hardware(spi)
    display = configure_display(spi)
    wifi_connection = connect_wifi(wifi)
    count = 0
    while True:
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

            display_things(display, tides)
            # sleep for 2 hours
            time.sleep(2 * 60 * 60)
                    #sleep for 3 minutes
        #            time.sleep(180)

        except:
            print("we got an exception")
            count = count + 1


# Using the special variable
# __name__
if __name__ == "__main__":
    main()
