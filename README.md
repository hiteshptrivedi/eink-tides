# eink-tides
### Video Demo:  (https://youtu.be/dMhMmFg1iJU)
## Description:
This is my Final CS50 project and I wrote a circuitpython project that gathers the ocean tide information and displays the next 4 tides on an eink display 
I live by the ocean and it’s very helpful to know when the tide times are.
I had heard a lot about Arduinos and did some programming in C for it. In CS50 we learned a bit of python and arduinos have support for “Circuit Python” so I used what I learned and then learned some more.

## The code:
code.py has all of the code in the one file. 
It's broken down into three different sections:
<ol>
    <li>Set up the hardware (SPI, Display, Wifi) </li>
    <li>Connect wifi and get the tide info </li>
    <li>Construct the information to be displayed and display it.
   and repeat every couple of hours. </li>
</ol>

## Construction of the hardware:

<ul>
    <li>M4 Feather express https://www.adafruit.com/product/3857 </li>
    <li>ESP32 Wifi Coprocessor https://www.adafruit.com/product/4264 </li>
    <li>2.9" eInk Display https://www.adafruit.com/product/4778 </li>
</ul>

The feather wings are great. You need to solder the preincluded headers onto the M4 board
Then press the Wifi board through those headers and solder
Then press the eInk display through and solder that

You do need to solder things because you'll have flaky connections that'll mess with you.

## Prepping the system:
Then prep the file system on the M4 board.
Connect the boards via USB on the M4 to a laptop
A nice walkthrough to use can be found here: https://learn.adafruit.com/adafruit-matrixportal-m4/circuitpython-setup

Then, when you connect this hardware via USE, you'll have a USB drive connected. 

Copy all of the files in this repo to the USB drive.
To have this connect to your wifi router, you'll need to create a settings.toml that has the AP router name and password. Dont ever hard code that into your python file.

## Go Go Go
And then reset and it'll do the thing


![Viola](https://github.com/hiteshptrivedi/eink-tides/blob/main/Final%20project.jpg)

Enjoy
