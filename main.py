#
# DL32 MicroPython Release
# markrolandbooth@gmail.com
# github.com/Mark-Roly/DL32_mpy
#

from microdot_asyncio import Microdot, send_file
from umqtt.simple import MQTTClient
from wiegand import Wiegand
from machine import SDCard
import time
import uasyncio
import os
gc.collect()

_VERSION = const("20230623")

year, month, day, hour, mins, secs, weekday, yearday = time.localtime()

print('DL32 - MicroPython Edition')
print('Version: ' + _VERSION)
print("Current Date/Time: " + "{}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(year, month, day, hour, mins, secs))

try:
  sd = SDCard(slot=2)
  uos.mount(sd, '/sd')
  print("SD Card mounted")
  print("  " + str(os.listdir("/sd")))
except:
  print ("No SD card present")

# SD Card Pins
# CD DAT3 CS 5
# CMD DI DIN MOSI 23
# CLK SCLK 18
# DAT0 D0 MISO 19

# 1.1 Pins - Uncomment if using board revision 1.1
buzzer_pin = Pin(14, Pin.OUT)
neopin_pin = Pin(21, Pin.OUT)
lockRelay_pin = Pin(27, Pin.OUT)
progButton_pin = Pin(12, Pin.IN, Pin.PULL_UP)
exitButton_pin = Pin(32, Pin.IN, Pin.PULL_UP)
bellButton_pin = Pin(33, Pin.IN, Pin.PULL_UP)
magSensor = Pin(22, Pin.IN, Pin.PULL_UP)
wiegand_0 = 25
wiegand_1 = 26
silent_mode = False

# 2.0 Pins - Uncomment if using S2 Mini board revision
# buzzer_pin = Pin(14, Pin.OUT)
# neopin_pin = Pin(38, Pin.OUT)
# lockRelay_pin = Pin(10, Pin.OUT)
# progButton_pin = Pin(12, Pin.IN, Pin.PULL_UP)
# exitButton_pin = Pin(13, Pin.IN, Pin.PULL_UP)
# bellButton_pin = Pin(33, Pin.IN, Pin.PULL_UP)
# magSensor = Pin(11, Pin.IN, Pin.PULL_UP)
# wiegand_0 = 16
# wiegand_1 = 17

# Durations for each unlock type (eg: unlock for 10 seconds if unclocked via MQTT)
exitBut_dur = 5000
http_dur = 10000
card_dur = 5000
mqtt_dur = 10000
addKey_dur = 15000
add_hold_time = 2000
add_mode = False
add_mode_counter = 0
add_mode_intervals = 10
ip_address = "0.0.0.0"

# Set initial pin states
buzzer_pin.value(0)
lockRelay_pin.value(0)

# Opening JSON file
try:
  with open('dl32.cfg') as json_file:
    CONFIG_DICT = json.load(json_file)
except:
  print("ERROR: Could not load dl32.cfg into config dictionary")
        
try:
  with open('keys.cfg') as json_file:
    KEYS_DICT = json.load(json_file)
except:
  print("ERROR: Could not load keys.cfg into keys dictionary")

WIFISSID = (CONFIG_DICT["wifi_ssid"])
WIFIPASS = (CONFIG_DICT["wifi_pass"])
mqtt_clid = (CONFIG_DICT["mqtt_clid"])
mqtt_brok = (CONFIG_DICT["mqtt_brok"])
mqtt_port = (CONFIG_DICT["mqtt_port"])
mqtt_user = (CONFIG_DICT["mqtt_user"]).encode('utf_8')
mqtt_pass = (CONFIG_DICT["mqtt_pass"]).encode('utf_8')
mqtt_cmd_top = (CONFIG_DICT["mqtt_cmd_top"]).encode('utf_8')
mqtt_sta_top = (CONFIG_DICT["mqtt_sta_top"]).encode('utf_8')
web_port = (CONFIG_DICT["web_port"])
CARD_NUMS = KEYS_DICT.keys()

def file_exists(filename):
    try:
        os.stat(filename)
        return True
    except OSError:
        return False

def connect_wifi():
  global ip_address
  sta_if = network.WLAN(network.STA_IF)
  if not sta_if.isconnected():
    sta_if.active(True)
    sta_if.connect(WIFISSID, WIFIPASS)
    while not sta_if.isconnected():
      pass # wait till connection
  ip_address = sta_if.ifconfig()[0]
  print('IP address: ' + ip_address)
  print('Connected to wifi SSID ' + WIFISSID)
  resync_html_content()

def refresh_time():
  global year, month, day, hour, mins, secs, weekday, yearday
  year, month, day, hour, mins, secs, weekday, yearday = time.localtime()

def save_keys_to_SD():
  if file_exists("sd/keys.cfg"):
      #rename old file
      refresh_time()
      os.rename("sd/keys.cfg", ("sd/keys" + str("{}{:02d}{:02d}_{:02d}{:02d}{:02d}".format(year, month, day, hour, mins, secs) + ".cfg")))
  with open('sd/keys.cfg', 'w') as json_file:
    json.dump(KEYS_DICT, json_file)

def start_server():
  print('Starting web server on port ' + str(web_port))
  mqtt.publish(mqtt_sta_top, ('Starting web server on port ' + str(web_port)), retain=False, qos=0)
  try:
    web_server.run(port = web_port)
  except:
    web_server.shutdown()
    print('Failed to start web server')

def add_key(card_number):
  if (len(str(card_number)) > 1 and len(str(card_number)) < 7):
    print ("  Adding key " + str(card_number))
    refresh_time()
    KEYS_DICT[str(card_number)] = ("{}{:02d}{:02d}_{:02d}{:02d}{:02d}".format(year, month, day, hour, mins, secs))
    with open('keys.cfg', 'w') as json_file:
      json.dump(KEYS_DICT, json_file)
    print("  Key added to authorized list as: " + "{}{:02d}{:02d}_{:02d}{:02d}{:02d}".format(year, month, day, hour, mins, secs))
    resync_html_content()
  else:
    print("  Unable to add key " + card_number)
    print("  Invalid key format - key not added")


def on_card(card_number, facility_code, cards_read):
  global add_mode
  global add_mode_counter
  global add_mode_intervals
  print('Card detected')
  if (str(card_number) in CARD_NUMS):
    if add_mode == False:
      print ("  Authorized card: ")
      print ("  Card #: " + str(card_number))
      print ("  Card belongs to " + KEYS_DICT[str(card_number)])
      unlock(card_dur)
    else:
      add_mode = False
      print ("  Card #" + str(card_number) + " is already authorized.")
      add_mode_counter = add_mode_intervals
  else:
    if add_mode == False:
      print ("  Unauthorized card: ")
      print ("  Card #: " + str(card_number))
      print ("  Facility code: " + str(facility_code))
      invalidBeep()
    else:
      add_key(card_number)
      add_mode = False
      add_mode_counter = add_mode_intervals

Wiegand(wiegand_0, wiegand_1, on_card)

def sub_cb(topic, msg):
  print('Message arrived on topic ' + topic.decode('utf-8') + ': ' + msg.decode('utf-8'))
  if topic == mqtt_cmd_top:
    if msg.decode('utf-8') == "unlock":
      unlock(mqtt_dur)

def resync_html_content():
  global html
  global ip_address
  html = """<!DOCTYPE html>
  <html>
    <head>
      <style>div {width: 350px; margin: 20px auto; text-align: center; border: 3px solid #32e1e1; background-color: #555555; left: auto; right: auto;}.header {font-family: Arial, Helvetica, sans-serif; font-size: 20px; color: #32e1e1;}button {width: 300px; background-color: #32e1e1; border: none; text-decoration: none;}button:hover {width: 300px; background-color: #12c1c1; border: none; text-decoration: none;}.main_heading {font-family: Arial, Helvetica, sans-serif; color: #32e1e1; font-size: 30px;}h5 {font-family: Arial, Helvetica, sans-serif; color: #32e1e1;}a {font-family: Arial, Helvetica, sans-serif; font-size: 10px; color: #32e1e1;}textarea {background-color: #303030; font-size: 11px; width: 300px; height: 75px; resize: vertical; color: #32e1e1;}body {background-color: #303030; text-align: center;}</style>
    </head>
    <body>
      <div>
        <br/>
        <a class='main_heading'>DL32 MENU</a></br/>
        <a style="font-size: 15px">--- MicroPython edition ---</a><br/>
        <a>by Mark Booth - markrolandbooth@gmail.com</a><br/><br/>
        <a class='header'>Device Control<a/>
        <a href='/unlock'><button>HTTP Unlock</button></a><br/>
        <a href='/bell'><button>Ring bell</button></a><br/>
        <a href='/reset'><button>Reset Board</button></a><br/><br/>
        <a class='header'>Key Management<a/>
        <a href='/print_keys'><button>List authorized keys</button></a><br/>
        <a href='/purge_keys'><button>Purge authorized keys</button></a><br/><br/>
        <a class='header'>File Download<a/>
        <a href='/download/main.py'><button>Download main.py</button></a><br/>
        <a href='/download/boot.py'><button>Download boot.py</button></a><br/>
        <a href='/download/dl32.cfg'><button>Download dl32.cfg</button></a><br/>
        <a href='/download/keys.cfg'><button>Download keys.cfg</button></a><br/><br/>
        <hr>
        <br/>
        <a class='header'>keys.cfg JSON<a/>
        <textarea readonly style="height: 50px">""" + str(KEYS_DICT) + """</textarea><br/><br/>
        <a class='header'>dl32.cfg JSON<a/>
        <textarea readonly style="height: 100px">""" + str(CONFIG_DICT) + """</textarea>
        <br/>
        <a>Version """ + _VERSION + """ IP Address """ + str(ip_address) + """</a><br/>
        <br/>
      </div>
    </body>
  </html>"""

resync_html_content()

def print_keys():
  global KEYS_DICT
  if KEYS_DICT == {}:
    print('  [NONE]')
  else:
    for key in KEYS_DICT:
      print('  ' + key + ' - ' + KEYS_DICT[key])

def purge_keys():
  global KEYS_DICT
  KEYS_DICT = {}
  with open('keys.cfg', 'w') as json_file:
    json.dump(KEYS_DICT, json_file)
  resync_html_content()

def unlock(*args):
  unlockBeep()
  for dur in args:
    lockRelay_pin.value(1)
    print('  Unlocked')
    mqtt.publish(mqtt_sta_top, "Unlocked", retain=False, qos=0)
    time.sleep_ms(dur)
    lockRelay_pin.value(0)
    print('  Locked')
    mqtt.publish(mqtt_sta_top, "Locked", retain=False, qos=0)
    
async def monbut():
  global add_hold_time
  while True:
    if int(exitButton_pin.value()) == 0:
      time_held = 0
      while (int(exitButton_pin.value()) == 0 and time_held <= add_hold_time):
        time.sleep_ms(10)
        time_held += 10
      if time_held > add_hold_time:
        print('Key add mode')
        uasyncio.create_task(key_add_mode())
        await uasyncio.sleep_ms(addKey_dur)
      else:
        print('Exit button pressed')
        unlock(exitBut_dur)
    await uasyncio.sleep_ms(50)
    
async def montop():
  while True:
    mqtt.check_msg()
    await uasyncio.sleep_ms(50)

async def mqtt_ping():
  while True:
    mqtt.ping()
    await uasyncio.sleep(60)

async def mqtt_status():
  while True:
    print('Published status message to ' + mqtt_sta_top.decode('utf-8'))
    mqtt.publish(mqtt_sta_top, "Stayin' alive!", retain=False, qos=0)
    await uasyncio.sleep(1800)

async def ring_bell():
  print ("  Ringing bell")
  mqtt.publish(mqtt_sta_top, "Ringing bell", retain=False, qos=0)
  loop1 = 0
  while loop1 <= 3:
    loop2 = 0
    while loop2 <= 30:
      if silent_mode == False:
        buzzer_pin.value(1)
      await uasyncio.sleep_ms(10)
      buzzer_pin.value(0)
      await uasyncio.sleep_ms(10)
      loop2 +=1
    await uasyncio.sleep_ms(2000)
    loop1 +=1

async def key_add_mode():
  global add_mode
  global add_mode_intervals
  global add_mode_counter
  add_mode_counter = 0
  print("Waiting for new key",end=" ")
  add_mode = True
  while add_mode_counter < add_mode_intervals:
    print(".",end=" ")
    lil_bip()
    await uasyncio.sleep_ms(int(addKey_dur/add_mode_intervals))
    add_mode_counter += 1
  if key_add_mode == True:
    print("No key detected.")
    key_add_mode == False

def unlockBeep():
  if silent_mode == False:
    buzzer_pin.value(1)
  time.sleep_ms(75)
  buzzer_pin.value(0)
  time.sleep_ms(100)
  if silent_mode == False:
    buzzer_pin.value(1)
  buzzer_pin.value(0)

def invalidBeep():
  if silent_mode == False:
    buzzer_pin.value(1)
  time.sleep_ms(1000)
  buzzer_pin.value(0)
  if silent_mode == False:
    buzzer_pin.value(1)
  time.sleep_ms(1000)
  buzzer_pin.value(0)

def lil_bip():
  if silent_mode == False:
    buzzer_pin.value(1)
  time.sleep_ms(10)
  buzzer_pin.value(0)

# --------- MAIN -----------

if silent_mode == True:
  print("Silent Mode Activated")

try:
  connect_wifi()
except:
  print("ERROR: Could not connect to WiFi")

try:
  mqtt = MQTTClient(mqtt_clid, mqtt_brok, port=mqtt_port, user=mqtt_user, password=mqtt_pass, keepalive=300)
  mqtt.set_callback(sub_cb)
  mqtt.connect()
  print ("Connected to MQTT broker " + mqtt_brok)
except:
  print("ERROR: Could not connect to MQTT Broker")

try:
  mqtt.subscribe(mqtt_cmd_top)
  print ("Subscribed to topic " + mqtt_cmd_top.decode('utf-8'))
except: 
  print("ERROR: Could not subscribe to MQTT command topic " + mqtt_cmd_top.decode('utf-8'))


web_server = Microdot()

uasyncio.create_task(monbut())
uasyncio.create_task(montop())
uasyncio.create_task(mqtt_ping())
# uasyncio.create_task(mqtt_status())

@web_server.route('/')
def hello(request):
  return html, 200, {'Content-Type': 'text/html'}

@web_server.route('/unlock')
def unlock_http(request):
  print('Unlock command recieved from WebUI')
  unlock(http_dur)
  return html, 200, {'Content-Type': 'text/html'}

@web_server.route('/reset')
def reset_http(request):
  print('Reset command recieved from WebUI')
  machine.reset()
  return html, 200, {'Content-Type': 'text/html'}

@web_server.route('/bell')
async def bell_http(request):
  print('Bell command recieved from WebUI')
  uasyncio.create_task(ring_bell())
  return html, 200, {'Content-Type': 'text/html'}

@web_server.route("/download/<string:filename>", methods=["GET", "POST"])
def dl_file(request, filename):
  return send_file(str("/" + filename), status_code=200)

@web_server.route('/print_keys')
def print_keys_http(request):
  print('Print keys command recieved from WebUI')
  print_keys()
  return html, 200, {'Content-Type': 'text/html'}

@web_server.route('/purge_keys')
def purge_keys_http(request):
  print('Purge keys command recieved from WebUI')
  purge_keys()
  return html, 200, {'Content-Type': 'text/html'}

@web_server.route("/add_key/<string:key>", methods=["GET", "POST"])
def content(request, key):
  print('Add key command recieved from WebUI ' + key)
  add_key(key)
  return html, 200, {'Content-Type': 'text/html'}

start_server()

