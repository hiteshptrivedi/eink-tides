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
import board
import displayio
import adafruit_uc8151d
import adafruit_ntp
import rtc
import terminalio
from adafruit_display_text import label

try:
    from fourwire import FourWire
except ImportError:
    from displayio import FourWire


TIME_URL = "http://worldtimeapi.org/api/ip"
TIMEZONE = "America/New_York"
DISPLAY_WIDTH = 296
DISPLAY_HEIGHT = 176

BLACK = 0x000000
WHITE = 0xFFFFFF
RED = 0xFF0000
FOREGROUND_COLOR = BLACK
BACKGROUND_COLOR = WHITE


# If you have an AirLift Featherwing or ItsyBitsy Airlift:
wifi_cs = DigitalInOut(board.D13)
wifi_ready = DigitalInOut(board.D11)
wifi_reset = DigitalInOut(board.D12)
# eink display
epd_cs = board.D9
epd_dc = board.D10
epd_reset = None
epd_busy = None

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
    print("configure diusplay")
    displayio.release_displays()

    # This pinout works on a Feather M4 and may need to be altered for other boards.
    #    spi = board.SPI()  # Uses SCK and MOSI

    display_bus = FourWire(
        spi, command=epd_dc, chip_select=epd_cs, reset=epd_reset, baudrate=1000000
    )
    time.sleep(1)

    display = adafruit_uc8151d.UC8151D(
        display_bus, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, rotation=90, busy_pin=epd_busy
    )
    return display


def display_things(display, tides):
    print("entering display_things")

    g = displayio.Group()
    # Set a white background
    background_bitmap = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
    # Map colors in a palette
    palette = displayio.Palette(1)
    palette[0] = BACKGROUND_COLOR

    # Create a Tilegrid with the background and put in the displayio group
    t = displayio.TileGrid(background_bitmap, pixel_shader=palette)
    g.append(t)

    # Draw simple text using the built-in font into a displayio group
    text_group = displayio.Group(scale=2, x=40, y=40)
    text = ""
    for tide in tides:
        text += tide
        text += "\r\n"

    text_area = label.Label(terminalio.FONT, text=text, color=FOREGROUND_COLOR)
    text_group.append(text_area)  # Add this text to the text group
    g.append(text_group)

    # Place the display group on the screen
    display.root_group = g
    # Set a white background
    background_bitmap = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
    # Map colors in a palette
    palette = displayio.Palette(1)
    palette[0] = BACKGROUND_COLOR

    # Create a Tilegrid with the background and put in the displayio group
    t = displayio.TileGrid(background_bitmap, pixel_shader=palette)
    g.append(t)

    # Draw simple text using the built-in font into a displayio group
    text_group = displayio.Group(scale=2, x=40, y=40)
#    text = ""
##    for tide in tides:
    text += tide[0]

    print(text)
    text_area = label.Label(terminalio.FONT, text=text, color=FOREGROUND_COLOR)
    text_group.append(text_area)  # Add this text to the text group
    g.append(text_group)

    # Place the display group on the screen
    display.root_group = g

    display.refresh()

    print("leaving display_things")

def update_rtc_time(wifi_connection, pool, ssl_context, requests):
    print("updating RTC")
    with requests.get(TIME_URL) as response:
#        print(response.json())
        time_data = response.json()
        tz_hour_offset = int(time_data["utc_offset"][0:3])
        tz_min_offset = int(time_data["utc_offset"][4:6])
        if tz_hour_offset < 0:
            tz_min_offset *= -1
        unixtime = int(time_data["unixtime"] + (tz_hour_offset * 60 * 60)) + (
            tz_min_offset * 60
        )

#        print(time_data)
#        print("URL time: ", response.headers["date"])

        rtc.RTC().datetime = time.localtime(
            unixtime
        )  # create time struct and set RTC with it
    print(unixtime)
    print("updated rtc:")

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
    print("My IP address is", wifi.pretty_ip(wifi.ip_address))
    return wifi


def disconnect_wifi(wifi_connection, pool, ssl_context, requests):
    print("disconnecting from wifi")
    wifi_connection.disconnect()


#    adafruit_connection_manager.connection_manager_close_all(pool, True)
#    spi.release()


def get_tide_info(wifi_connection, pool, ssl_context, requests):

    TIDE_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=today&range=48&station=8446121&product=predictions&datum=MLLW&time_zone=lst_ldt&interval=hilo&units=english&application=DataAPI_Sample&format=json"
    #    tides = requests.get(TIDE_URL)

    with requests.get(TIDE_URL) as tides:
#        print(f"CircuitPython Tides: {tides.json()['predictions'][0]}")
        pTownTides = []

        for item in tides.json()["predictions"]:
            # the_datetime is now a datetime type
            the_datetime = datetime.fromisoformat(item["t"])
            hour = the_datetime.hour % 12
            if hour == 0:
                hour = 12
            am_pm = "AM"
            if the_datetime.hour / 12 >= 1:
                am_pm = "PM"

            if item["type"] == "L":
                tide_type = "Low Tide"
            else:
                tide_type = "High Tide"

            theTime = (
                str(the_datetime.month)
                + "/"
                + str(the_datetime.day)
                + "   "
                + str(hour)
                + ":"
                + "{:02d}".format(the_datetime.minute)
                + am_pm
                + "   "
                + tide_type
            )
            print("theTide")
            print(theTime)
            pTownTides.append(theTime)
    return pTownTides

# Defining main function
def main():
    spi = configure_spi()
    #    display_things()
    wifi, pool, ssl_context, requests = configure_wifi_hardware(spi)
    display = configure_display(spi)
    wifi_connection = connect_wifi(wifi)
    count = 0
    while True:
#       if count > 5:
#           print("we got 5 exceptions")
#           exit()
#       try:
        print("going to start at the beginning")
        if not wifi_connection.is_connected:
            wifi_connection = connect_wifi(wifi)

        update_rtc_time(wifi, pool, ssl_context, requests)

        tides = get_tide_info(wifi_connection, pool, ssl_context, requests)
    #            disconnect_wifi(wifi_connection, pool, ssl_context, requests)
        display_things(display, tides)
        time.sleep(120)

#        except:
#            print("we got an exception")
#            count = count + 1


# Using the special variable
# __name__
if __name__ == "__main__":
    main()
