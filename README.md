# DL32_mpy
MicroPython release of the ESP32-powered Wifi & RFID Smart Door Lock.

Designed for use with ESP32S3-based Wemos S3 Mini.
Should run on other ESP32 board provided they have at least 2MB RAM (standard ESP32/S2/S3 only have 320-512KB, so external PSRAM is required).

Requires following 3rd party libraries:
- buzzer_music library used written by james1236 available from https://github.com/james1236/buzzer_music
- microdot_asyncio
- umqtt.simple
- wiegand
- ugit
- os, machine, network, json, time, esp, gc, sdcard, neopixel, time, uasyncio
