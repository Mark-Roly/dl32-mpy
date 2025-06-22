# DL32_mpy

[!] NOTICE [!]
As Micropython does not have the required speed to reliably and consistently read Wiegand input, this project is archived and no longer being actively developed.
Please see the [C++/Arduino variant](https://github.com/Mark-Roly/DL32)

MicroPython release of the ESP32-powered Wifi & RFID Smart Door Lock.

Designed for use with ESP32S3-based Wemos S3 Mini using DL32-S3 carrier board.

Should run on other ESP32 board provided they have at least 2MB RAM (standard ESP32/S2/S3 only have 320-512KB, so external PSRAM is required).

Requires following 3rd party libraries:
- [buzzer_music](https://github.com/james1236/buzzer_music) by james1236
- [wiegand](https://github.com/pjz/micropython-wiegand) by pjz
- [ugit](https://github.com/turfptax/ugit) by turfptax
