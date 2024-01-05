# DL32_mpy
MicroPython release of the ESP32-powered Wifi & RFID Smart Door Lock.

Designed for use with ESP32S3-based Wemos S3 Mini using DL32-S3 carrier board (Schematics and gerbers coming).

Should run on other ESP32 board provided they have at least 2MB RAM (standard ESP32/S2/S3 only have 320-512KB, so external PSRAM is required).

Requires following 3rd party libraries:
- [buzzer_music](https://github.com/james1236/buzzer_music) by james1236
- [wiegand](https://github.com/pjz/micropython-wiegand) by pjz
- [ugit](https://github.com/turfptax/ugit) by turfptax
