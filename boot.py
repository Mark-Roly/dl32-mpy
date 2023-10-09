from machine import Pin
import network
import json
import time
import esp
import gc

gc.collect()
esp.osdebug(None)