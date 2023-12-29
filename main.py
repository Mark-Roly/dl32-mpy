from microdot_asyncio import Microdot, send_file
from umqtt.simple import MQTTClient
from wiegand import Wiegand
from buzzer_music import music
from ota import OTAUpdater
import sdcard, machine, neopixel, time, uasyncio, os
from doorbells import Doorbells

gc.collect()

# Watchdog timeout set @ 5min
wdt = machine.WDT(timeout = 300000)

_VERSION = const('20231229a')

year, month, day, hour, mins, secs, weekday, yearday = time.localtime()

print('DL32 - MicroPython Edition')
print('Version: ' + _VERSION)
print('Current Date/Time: ' + '{}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(year, month, day, hour, mins, secs))

# 1.1 SD card Pins
# CD DAT3 CS 5
# CMD DI DIN MOSI 23
# CLK SCLK 18
# DAT0 D0 MISO 19

# 1.1 Pins - Uncomment if using board revision 1.1
# buzzer_pin = Pin(14, Pin.OUT)
# neopix_pin = Pin(21, Pin.OUT)
# lockRelay_pin = Pin(27, Pin.OUT)
# progButton_pin = Pin(12, Pin.IN, Pin.PULL_UP)
# exitButton_pin = Pin(32, Pin.IN, Pin.PULL_UP)
# bellButton_pin = Pin(33, Pin.IN, Pin.PULL_UP)
# magSensor = Pin(22, Pin.IN, Pin.PULL_UP)
# wiegand_0 = 25
# wiegand_1 = 26
# sd = SDCard(slot=2)

# 1.1 Pins w/TinyPico adapter - Uncomment if using board revision 1.1 with tinypico adapter
# buzzer_pin = machine.Pin(14, machine.Pin.OUT)
# neopix_pin = machine.Pin(21, machine.Pin.OUT)
# lockRelay_pin = machine.Pin(27, machine.Pin.OUT)
# progButton_pin = machine.Pin(4, machine.Pin.IN, machine.Pin.PULL_UP)
# exitButton_pin = machine.Pin(32, machine.Pin.IN, machine.Pin.PULL_UP)
# bellButton_pin = machine.Pin(33, machine.Pin.IN, machine.Pin.PULL_UP)
# magSensor = machine.Pin(22, machine.Pin.IN, machine.Pin.PULL_UP)
# wiegand_0 = 25
# wiegand_1 = 26
# sd = machine.SDCard(slot=2)

# 2.0 Pins - Uncomment if using S2 Mini board revision
# buzzer_pin = machine.Pin(14, Pin.OUT)
# neopix_pin = machine.Pin(38, Pin.OUT)
# lockRelay_pin = machine.Pin(10, Pin.OUT)
# progButton_pin = machine.Pin(12, Pin.IN, Pin.PULL_UP)
# exitButton_pin = machine.Pin(13, Pin.IN, Pin.PULL_UP)
# bellButton_pin = machine.Pin(33, Pin.IN, Pin.PULL_UP)
# magSensor = machine.Pin(11, Pin.IN, Pin.PULL_UP)
# wiegand_0 = 16
# wiegand_1 = 17

# 3.0 Pins - Uncomment if using S3 Wemos board revision
buzzer_pin = machine.Pin(14, Pin.OUT)
neopix_pin = machine.Pin(11, Pin.OUT)
lockRelay_pin = machine.Pin(1, Pin.OUT)
progButton_pin = machine.Pin(6, Pin.IN, Pin.PULL_UP)
exitButton_pin = machine.Pin(21, Pin.IN, Pin.PULL_UP)
bellButton_pin = machine.Pin(17, Pin.IN, Pin.PULL_UP)
magSensor = machine.Pin(15, Pin.IN, Pin.PULL_UP)
wiegand_0 = 16
wiegand_1 = 18
DS01 = machine.Pin(33, Pin.IN, Pin.PULL_UP)
DS02 = machine.Pin(37, Pin.IN, Pin.PULL_UP)
DS03 = machine.Pin(5, Pin.IN, Pin.PULL_UP)
DS04 = machine.Pin(10, Pin.IN, Pin.PULL_UP)

try:
  sd = sdcard.SDCard(machine.SPI(1, sck=machine.Pin(38), mosi=machine.Pin(36), miso=machine.Pin(35)), machine.Pin(34))
except:
  print ('No SD card present')
  sd_present = False
  
# 3.0 SD card Pins
# CD DAT3 CS 34
# CMD DI DIN MOSI 36
# CLK SCLK 38
# DAT0 D0 MISO 35

# Tunable parameters
exitBut_dur = 5000
http_dur = 10000
key_dur = 5000
mqtt_dur = 10000
garageMode_dur = 500
addKey_dur = 15000
add_hold_time = 2000
sd_boot_hold_time = 3000
magnetic_sensor_present = True
silent_mode = False
garage_mode = False
ota_mode = False
add_mode_intervals = 10
opening_type = 'door'

# Global parameters
add_mode_counter = 0
mag_state = 0
ip_address = '0.0.0.0'
bell_ringing = False
add_mode = False
sd_present = False
mqtt_online = False

# OTA variables
firmware_url = "https://raw.githubusercontent.com/Mark-Roly/DL32_mpy/main/"

# Set initial pin states
buzzer_pin.value(0)
lockRelay_pin.value(0)

np_standby = (0, 0, 255)
np_unlocked = (0, 255, 0)
np_invalid = (255, 0, 0)
np_add = (255, 0, 255)
np_doorbell = (255, 255, 255)

np = neopixel.NeoPixel(neopix_pin, 1)	
np[0] = np_standby	
np.write()

# Define dictionaries to store configuration and authorized keys
CONFIG_DICT = {}
KEYS_DICT = {}

# Try mounting SD card and list contents. Catch error.
try:
  os.mount(sd, '/sd')
  print('SD card mounted')
  print('  ' + str(os.listdir('/sd')))
  sd_present = True
except:
  print ('No SD card present')
  sd_present = False

# Function for copying files (Not currently in-use)
def copy(source, target):
  try: 
    if os.stat(target)[0] & 0x4000:  # is a directory
      target = target.rstrip("/") + "/" + source
  except OSError:
    pass
  with open(source, "rb") as source:
    with open(target, "wb") as target:
      while True:
        l = source.read(512)
        if not l: break
        target.write(l)

# Wipe config dictionary from memory
def wipe_config():
  global CONFIG_DICT
  CONFIG_DICT = {}

# Wipe key dictionary from memory
def wipe_keys():
  global KEYS_DICT
  KEYS_DICT = {}

# Load config file from ESP32
def load_esp_config():
  global CONFIG_DICT
  try:
    with open('dl32.cfg') as json_file:
      CONFIG_DICT = json.load(json_file)
  except:
    print('ERROR: Could not load dl32.cfg into config dictionary')
    
load_esp_config()

# Load keys file from ESP32
def load_esp_keys():
  global KEYS_DICT
  try:
    with open('keys.cfg') as json_file:
      KEYS_DICT = json.load(json_file)
  except:
    print('ERROR: Could not load keys.cfg into keys dictionary')
    
load_esp_keys()

# Load config file from SD card
def load_sd_config():
  global CONFIG_DICT
  global sd_present
  if (sd_present == False):
    print ('SD Card not present')
    return
  try:
    with open('sd/dl32.cfg') as json_file:
      wipe_config()
      CONFIG_DICT = json.load(json_file)
      resync_html_content()
  except:
    print('ERROR: Could not load sd/dl32.cfg into config dictionary')

# Load keys file from SD card
def load_sd_keys():
  global KEYS_DICT
  global sd_present
  if (sd_present == False):
    print ('SD Card not present')
    return
  try:
    with open('sd/keys.cfg') as json_file:
      wipe_keys()
      KEYS_DICT = json.load(json_file)
      resync_html_content()
  except:
    print('ERROR: Could not load sd/keys.cfg into keys dictionary')

wifi_ssid= (CONFIG_DICT['wifi_ssid'])
wifi_pass = (CONFIG_DICT['wifi_pass'])
mqtt_clid = (CONFIG_DICT['mqtt_clid'])
mqtt_brok = (CONFIG_DICT['mqtt_brok'])
mqtt_port = (CONFIG_DICT['mqtt_port'])
mqtt_user = (CONFIG_DICT['mqtt_user']).encode('utf_8')
mqtt_pass = (CONFIG_DICT['mqtt_pass']).encode('utf_8')
mqtt_cmd_top = (CONFIG_DICT['mqtt_cmd_top']).encode('utf_8')
mqtt_sta_top = (CONFIG_DICT['mqtt_sta_top']).encode('utf_8')
web_port = (CONFIG_DICT['web_port'])
current = Doorbells[CONFIG_DICT['doorbell']]
key_NUMS = KEYS_DICT.keys()

#Initialize doorbell object
doorbell = music(current['music'], pins=[buzzer_pin])
doorbell.stop()

# Check if a file exists
def file_exists(filename):
  try:
    os.stat(filename)
    return True
  except OSError:
    return False

# Connect to wifi using details from config file
def connect_wifi():
  global ip_address
  sta_if = network.WLAN(network.STA_IF)
  if not sta_if.isconnected():
    sta_if.active(True)
    sta_if.connect(wifi_ssid, wifi_pass)
    while not sta_if.isconnected():
      pass # wait till connection
  ip_address = sta_if.ifconfig()[0]
  print('IP address: ' + ip_address)
  print('Connected to wifi SSID ' + wifi_ssid)
  resync_html_content()

# REfresh the date and time
def refresh_time():
  global year, month, day, hour, mins, secs, weekday, yearday
  year, month, day, hour, mins, secs, weekday, yearday = time.localtime()

# Save key dictionary to SD card
def save_keys_to_sd():
  global sd_present
  if (sd_present == False):
    print ('SD Card not present')
    return
  if file_exists('sd/keys.cfg'):
    #rename old file
    refresh_time()
    os.rename('sd/keys.cfg', ('sd/keys_' + str('{}{:02d}{:02d}_{:02d}{:02d}{:02d}'.format(year, month, day, hour, mins, secs) + '.cfg')))
  with open('sd/keys.cfg', 'w') as json_file:
    json.dump(KEYS_DICT, json_file)

# Save configuration dictionary to SD card
def save_config_to_sd():
  global sd_present
  if (sd_present == False):
    print ('SD Card not present')
    return
  if file_exists('sd/dl32.cfg'):
    #rename old file
    refresh_time()
    print('renaming sd/dl32.cfg to sd/dl32' + str('{}{:02d}{:02d}_{:02d}{:02d}{:02d}'.format(year, month, day, hour, mins, secs) + '.cfg'))
    os.rename('sd/dl32.cfg', ('sd/dl32_' + str('{}{:02d}{:02d}_{:02d}{:02d}{:02d}'.format(year, month, day, hour, mins, secs) + '.cfg')))
  with open('sd/dl32.cfg', 'w') as json_file:
    print('Saving updated config to sd/dl32.cfg')
    json.dump(CONFIG_DICT, json_file)

# Save key dictionary to ESP32
def save_keys_to_esp():
  with open('keys.cfg', 'w') as json_file:
    json.dump(KEYS_DICT, json_file)

# Save configuration dictionary to ESP32
def save_config_to_esp():
  with open('dl32.cfg', 'w') as json_file:
    json.dump(CONFIG_DICT, json_file)






def publish_status(message):
  global mqtt_online
  if mqtt_online:
    try:
      mqtt.publish(mqtt_sta_top, message, retain=False, qos=0)
    except:
      print('error publishing to MQTT topic')












# Start Microdot Async web server
def start_server():
  print('Starting web server on port ' + str(web_port))
  publish_status('Starting web server on port ' + str(web_port))
  try:
    web_server.run(port = web_port)
  except:
    web_server.shutdown()
    print('Failed to start web server')

# Import keys from SD card into keys dictionary and overwrite keys.cfg on ESP32
def import_keys_from_sd():
  global sd_present
  if (sd_present == False):
    print ('SD Card not present')
    return
  if file_exists('sd/keys.cfg'):
    load_sd_keys()
    if file_exists('keys.cfg'):
      refresh_time()
      os.rename('keys.cfg', 'keys_' + (str('{}{:02d}{:02d}_{:02d}{:02d}{:02d}'.format(year, month, day, hour, mins, secs))))
      save_keys_to_esp()
  else:
    print('No file sd/keys.cfg on SD card')

# Import config from SD card into config dictionary and overwrite dl32.cfg on ESP32
def import_config_from_sd():
  global sd_present
  if (sd_present == False):
    print ('SD Card not present')
    return
  if file_exists('sd/dl32.cfg'):
    load_sd_config()
    if file_exists('dl32.cfg'):
      refresh_time()
      os.rename('dl32.cfg', 'dl32' + (str('{}{:02d}{:02d}_{:02d}{:02d}{:02d}'.format(year, month, day, hour, mins, secs))))
      save_config_to_esp()
  else:
    print('No file sd/dl32.cfg on SD card')
    
# Check for button commands at boot
def check_boot():
  global sd_boot_hold_time
  while True:
    if int(progButton_pin.value()) == 0:
      time_held = 0
      while (int(progButton_pin.value()) == 0 and time_held <= sd_boot_hold_time):
        time.sleep_ms(10)
        time_held += 10
      if time_held > add_hold_time:
        print('Loading configuration + keys from SD card')

# Add a new key to the autorized keys dictionary
def add_key(key_number):
  if (len(str(key_number)) > 1 and len(str(key_number)) < 7):
    print ('  Adding key ' + str(key_number))
    refresh_time()
    date_time = ('{}{:02d}{:02d}_{:02d}{:02d}{:02d}'.format(year, month, day, hour, mins, secs))
    KEYS_DICT[str(key_number)] = date_time
    save_keys_to_esp()
    print('  Key ' + str(key_number) + ' added to authorized list as: ' + date_time)
    publish_status('Key ' + str(key_number) + ' added to authorized list as ' + date_time)
    resync_html_content()
  else:
    print('  Unable to add key ' + key_number)
    print('  Invalid key!')

# Add a new key to the autorized keys dictionary
def rem_key(key_number):
  if (len(str(key_number)) > 1 and len(str(key_number)) < 7) and (str(key_number) in KEYS_DICT):
    print ('  Removing key ' + str(key_number))
    del KEYS_DICT[str(key_number)]
    save_keys_to_esp()
    print('  Key '+ str(key_number) +' removed!')
    publish_status('Key ' + str(key_number) + ' removed from authorized list')
    resync_html_content()
  else:
    print('  Unable to remove key ' + key_number)
    print('  Invalid key format - key not removed')

def ren_key(key, name):
  if (len(str(key)) > 1 and len(str(key)) < 7) and (str(key) in KEYS_DICT) and (len(name) > 0) and (len(name) < 16) :
    print ('  Renaming key ' + str(key) + ' to ' + name)
    KEYS_DICT[str(key)] = name
    save_keys_to_esp()
    print('  Key '+ str(key) +' renamed to ' + name)
    publish_status('Key ' + str(key) + ' renamed to ' + name)
    resync_html_content()
  else:
    print('  Unable to rename key ' + key)

# RFID key listener function
def on_key(key_number, facility_code, keys_read):
  global add_mode
  global add_mode_counter
  global add_mode_intervals
  print('key detected')
  if (str(key_number) in key_NUMS):
    if add_mode == False:
      print ('  Authorized key: ')
      print ('  key #: ' + str(key_number))
      print ('  key belongs to ' + KEYS_DICT[str(key_number)])
      publish_status('Authorized key ' + str(key_number) + ' (' + KEYS_DICT[str(key_number)] + ') scanned')
      unlock(key_dur)
    else:
      add_mode = False
      print ('  key #' + str(key_number) + ' is already authorized.')
      add_mode_counter = add_mode_intervals
  else:
    if add_mode == False:
      np[0] = np_unlocked	
      np.write()
      print ('  Unauthorized key: ')
      print ('  key #: ' + str(key_number))
      print ('  Facility code: ' + str(facility_code))
      publish_status('Unauthorized key ' + str(key_number) + ' scanned')
      invalidBeep()
      np[0] = np_standby
      np.write()
    else:
      add_key(key_number)
      add_mode = False
      add_mode_counter = add_mode_intervals

Wiegand(wiegand_0, wiegand_1, on_key)

# MQTT callback function
def sub_cb(topic, msg):
  print('Message arrived on topic ' + topic.decode('utf-8') + ': ' + msg.decode('utf-8'))
  if topic == mqtt_cmd_top:
    if msg.decode('utf-8') == 'unlock':
      unlock(mqtt_dur)
    else:
      print ('Command not recognized!')

css = "div {width: 400px; margin: 20px auto; text-align: center; border: 3px solid #32e1e1; background-color: #555555; left: auto; right: auto;} hr {border-bottom: 1px solid #32e1e1} .header {font-family: Arial, Helvetica, sans-serif; font-size: 20px; color: #32e1e1} button {width: 395px; background-color: #32e1e1; border: none; text-decoration: none} .backNav {width: 50px; float: left;} .saveConf{width: 150px; } .config_input{width: 150px;} button.rem {background-color: #C12200; width: 30px; padding-left: 2px;} button.rem:hover {background-color: red} button.ren {background-color: #ff9900; width: 55px; padding-left: 1px} button.ren:hover {background-color: #ffcc00} input {width: 296px; border: none; text-decoration: none;} button:hover {background-color: #12c1c1; border: none; text-decoration: none;} input.renInput{width: 75px} .addKey {width: 193px;} .main_heading {font-family: Arial, Helvetica, sans-serif; color: #32e1e1; font-size: 30px;} h5 {font-family: Arial, Helvetica, sans-serif; color: #32e1e1} label {font-family: Arial, Helvetica, sans-serif; font-size: 10px; color: #32e1e1;} a {font-family: Arial, Helvetica, sans-serif; font-size: 10px; color: #32e1e1;}textarea {background-color: #303030; font-size: 11px; width: 394px; height: 75px; resize: vertical; color: #32e1e1;} body {background-color: #303030; text-align: center;} "


# Resync contents of static HTML webpage to take into account changes
def resync_html_content():
  global main_html
  global ip_address
  
  rem_buttons = '<table style="width: 380px; text-align: left; border: 0px solid black; border-collapse: collapse; margin-left: auto; margin-right: auto;">'
  for key in KEYS_DICT:
      rem_buttons += '<tr> <td style="width: 200px;"> <a style="font-size: 15px;"> &bull; ' + key + ' (' + KEYS_DICT[key] + ')</a></td><td><input id="renKeyInput_' + key + '" class="renInput" value="" maxlength="16" placeholder="New name"> <a> <button onClick="renKey('+key+')" class="ren">Rename</button></a></td><td><a href="/rem_key/'+key+'"><button class="rem">DEL</button></a></td></tr>'
  rem_buttons += "</table>"
  
  main_html = """<!DOCTYPE html>
  <html>
    <head>
      <style>
      """ + css + """
      </style>
      <script>
      window.addKey = function(){
        var input = document.getElementById("addKeyInput").value;
        window.location.href = "/add_key/" + input;
      }
      </script>
      <script>
      window.renKey = function(key){
        var inputid = "renKeyInput_" + key.toString()
        console.log(inputid)
        var input = document.getElementById(inputid).value;
        window.location.href = "/ren_key/" + key + "/" + input;
      }
      </script>
    </head>
    <body>
      <div>
        <br/>
        <a class='main_heading'>DL32 MENU</a>
        </br/>
        <a style="font-size: 15px">--- MicroPython Edition ---</a>
        <br/>
        <a>by Mark Booth - </a><a href='https://github.com/Mark-Roly/DL32_mpy'>github.com/Mark-Roly/DL32_mpy</a>
        <br/>
        <br/>
        <hr>
        <a class='header'>Device Control</a>
        <br/>
        <a href='/unlock'><button>HTTP Unlock</button></a>
        <br/>
        <a href='/bell'><button>Ring bell</button></a>
        <br/>
        <a href='/reset'><button>Reset Board</button></a>
        <hr>
        <a class='header'>File Download</a>
        <br/>
        <a href='/download/main.py'><button>Download main.py</button></a>
        <br/>
        <a href='/download/boot.py'><button>Download boot.py</button></a>
        <br/>
        <a href='/download/doorbells.py'><button>Download doorbells.py</button></a>
        <br/>
        <a href='/download/dl32.cfg'><button>Download dl32.cfg</button></a>
        <br/>
        <a href='/download/keys.cfg'><button>Download keys.cfg</button></a>
        <hr>
        <a class='header'>Configuration</a>
        <a href='/config_network'><button>Configure Network</button></a>
        <br/>
        <a href='/config_mqtt'><button>Configure MQTT</button></a>
        <br/>
        <a href='/config_doorbell'><button>Configure Doorbell Tones</button></a>
        <hr>
        <a class='header'>Key Management</a>
        <br/>
        <a style="color:#ffcc00; font-size: 15px; font-weight: bold;">***This cannot be undone!***</a>
        <br/>
        <a href='/add_mode'><button>scan-to-add</button></a>
        <input type="text" placeholder="Enter key number" id="addKeyInput" value="" maxlength="8" class="addKey">
        <button onClick="addKey()" class="addKey">Add Key</button>
        <br/>
        """ + rem_buttons + """
        <a href='/purge_keys'><button>Purge all keys</button></a>

        <hr>
        <a>Version """ + _VERSION + """ IP Address """ + str(ip_address) + """</a>
        <br/>
        <br/>
      </div>
    </body>
  </html>"""

resync_html_content()

# Resync contents of static HTML webpage to take into account changes
def resync_config_network_content():
  global config_network_html
  global ip_address
  
  config_network_html = """<!DOCTYPE html>
  <html>
    <head>
      <style>
      """ + css + """
      </style>
      <script>
      window.saveConf = function(){
        var wifi_ssid = document.getElementById("wifi_ssid").value;
        var wifi_pass = document.getElementById("wifi_pass").value;
        var web_port = document.getElementById("web_port").value;
        window.location.href = "/config_network/update/";
      }
      </script>
    </head>
    <body>
      <div>
        <a href="/"><button class="backNav">Back</button></a><br/>
        <a class='main_heading'>DL32 MENU</a></br/>
        <a style="font-size: 15px">--- MicroPython Edition ---</a><br/>
        <a>by Mark Booth - </a><a href='https://github.com/Mark-Roly/DL32_mpy'>github.com/Mark-Roly/DL32_mpy</a><br/><br/>
        <a class='header'>Network Configuration</a>
        <br/> <br/>
        <form action="" method="GET">
          <table style="width: 300px; text-align: left; border: 0px solid black; border-collapse: collapse; margin-left: auto; margin-right: auto;">
            <tr> <td> <a>Wifi SSID:</a> </td> <td> <input id="wifi_ssid" name="wifi_ssid" class="config_input" value=""" + str(wifi_ssid) + """> </td> </tr>
            <tr> <td> <a>Wifi password:</a> </td> <td> <input type="password" id="wifi_pass" name="wifi_pass" class="config_input" value=""" + str(wifi_pass) + """> </td> </tr>
            <tr> <td> <a>WebUI port:</a> </td> <td> <input id="web_port" name="web_port" class="config_input" value=""" + str(web_port) + """> </td> </tr>
          </table>
        <br/>
        <button class="saveConf" type="submit">Save</button><br/>
        <br/>
        <a>Version """ + _VERSION + """ IP Address """ + str(ip_address) + """</a><br/>
        <br/>
      </div>
    </body>
  </html>"""
  
resync_config_network_content()

# Resync contents of static HTML webpage to take into account changes
def resync_config_mqtt_content():
  global config_mqtt_html
  global ip_address
  
  config_mqtt_html = """<!DOCTYPE html>
  <html>
    <head>
      <style>
      """ + css + """
      </style>      <script>
      window.saveConf = function(){
        var mqtt_brok = document.getElementById("mqtt_brok").value;
        var mqtt_port = document.getElementById("mqtt_port").value;
        var mqtt_clid = document.getElementById("mqtt_clid").value;
        var mqtt_user = document.getElementById("mqtt_user").value;
        var mqtt_pass = document.getElementById("mqtt_pass").value;
        var mqtt_sta_top = document.getElementById("mqtt_sta_top").value;
        var mqtt_cmd_top = document.getElementById("mqtt_cmd_top").value;
        window.location.href = "/config/";
      }
      </script>
    </head>
    <body>
      <div>
        <a href="/"><button class="backNav">Back</button></a><br/>
        <a class='main_heading'>DL32 MENU</a></br/>
        <a style="font-size: 15px">--- MicroPython Edition ---</a><br/>
        <a>by Mark Booth - </a><a href='https://github.com/Mark-Roly/DL32_mpy'>github.com/Mark-Roly/DL32_mpy</a><br/><br/>
        <a class='header'>MQTT Configuration</a>
        <br/> <br/>
        <form action="" method="GET">
          <table style="width: 300px; text-align: left; border: 0px solid black; border-collapse: collapse; margin-left: auto; margin-right: auto;">
            <tr> <td> <a>MQTT broker:</a> </td> <td> <input id="mqtt_brok" name="mqtt_brok" class="config_input" value=""" + str(mqtt_brok) + """> </td> </tr>
            <tr> <td> <a>MQTT port:</a> </td> <td> <input id="mqtt_port" name="mqtt_port" class="config_input" value=""" + str(mqtt_port) + """> </td> </tr>
            <tr> <td> <a>MQTT id:</a> </td> <td> <input id="mqtt_clid" name="mqtt_clid" class="config_input" value=""" + str(mqtt_clid) + """> </td> </tr>
            <tr> <td> <a>MQTT user:</a> </td> <td> <input id="mqtt_user" name="mqtt_user" class="config_input" value=""" + CONFIG_DICT['mqtt_user'] + """> </td> </tr>
            <tr> <td> <a>MQTT password:</a> </td> <td> <input type="password" id="mqtt_pass" name="mqtt_pass" class="config_input" value=""" + CONFIG_DICT['mqtt_pass'] + """> </td> </tr>
            <tr> <td> <a>MQTT status topic:</a> </td> <td> <input id="mqtt_sta_top" name="mqtt_sta_top" class="config_input" value=""" + CONFIG_DICT['mqtt_sta_top'] + """> </td> </tr>
            <tr> <td> <a>MQTT command topic:</a> </td> <td> <input id="mqtt_cmd_top" name="mqtt_cmd_top" class="config_input" value=""" + CONFIG_DICT['mqtt_cmd_top'] + """> </td> </tr>
          </table>
        <br/>
        <button class="saveConf" type="submit">Save</button><br/>
        <br/>
        <a>Version """ + _VERSION + """ IP Address """ + str(ip_address) + """</a><br/>
        <br/>
      </div>
    </body>
  </html>"""
  
resync_config_mqtt_content()

# Resync contents of static HTML webpage to take into account changes
def resync_config_doorbell_content():
  global config_doorbell_html
  global Doorbells
  global ip_address
  global current
  
  doorbell_options = ""
  
  for key in Doorbells:
    if (current["title"] == Doorbells[key]["title"]):
      doorbell_options += '<option value=' + key + ' selected>' + Doorbells[key]["title"] + '</option>'
    else:
      doorbell_options += '<option value=' + key + '>' + Doorbells[key]["title"] + '</option>'
      
  config_doorbell_html = """<!DOCTYPE html>
  <html>
    <head>
      <style>div {width: 400px; margin: 20px auto; text-align: center; border: 3px solid #32e1e1; background-color: #555555; left: auto; right: auto;}.header {font-family: Arial, Helvetica, sans-serif; font-size: 20px; color: #32e1e1;} .backNav {width: 50px; float: left;} .saveConf{width: 150px; } .config_input{width: 150px;} button {width: 395px; background-color: #32e1e1; border: none; text-decoration: none; }button.rem {background-color: #C12200; width: 40px;}button.rem:hover {background-color: red}button.ren {background-color: #ff9900; width: 40px;}button.ren:hover {background-color: #ffcc00}input {width: 296px; border: none; text-decoration: none;}button:hover {background-color: #12c1c1; border: none; text-decoration: none;} input.renInput{width: 75px} .addKey {width: 60px;} .main_heading {font-family: Arial, Helvetica, sans-serif; color: #32e1e1; font-size: 30px;}h5 {font-family: Arial, Helvetica, sans-serif; color: #32e1e1;}label{font-family: Arial, Helvetica, sans-serif; font-size: 10px; color: #32e1e1;}a {font-family: Arial, Helvetica, sans-serif; font-size: 10px; color: #32e1e1;}textarea {background-color: #303030; font-size: 11px; width: 394px; height: 75px; resize: vertical; color: #32e1e1;}body {background-color: #303030; text-align: center;}</style>
      <script>
        window.setBell = function(){
          var input = document.getElementById("doorbell").value;
          window.location.href = "/set_bell/" + input;
        }
      </script>
    </head>
    <body>
      <div>
        <a href="/"><button class="backNav">Back</button></a><br/>
        <a class='main_heading'>DL32 MENU</a></br/>
        <a style="font-size: 15px">--- MicroPython Edition ---</a><br/>
        <a>by Mark Booth - </a><a href='https://github.com/Mark-Roly/DL32_mpy'>github.com/Mark-Roly/DL32_mpy</a><br/><br/>
        <a class='header'>Doorbell Configuration</a>
        <br/> <br/>
        <table style="width: 300px; text-align: left; border: 0px solid black; border-collapse: collapse; margin-left: auto; margin-right: auto;">
          <tr> <td> <a>Bell Tune:</a> </td>
            <td>
              <select id="doorbell" name="doorbell" class="config_input">
                """ + doorbell_options + """
              </select>
            </td>
          </tr>
        </table>
        <br/>
        <button class="saveConf" onClick="setBell()">Save</button>
        <br/>
        <a href='/config_doorbell/test'><button class="saveConf">Test current</button></a><br/>
        <a href='/config_doorbell/stop'><button class="saveConf">Stop playing</button></a><br/>
        <br/>
        <a>Version """ + _VERSION + """ IP Address """ + str(ip_address) + """</a><br/>
        <br/>
      </div>
    </body>
  </html>"""
  
resync_config_doorbell_content()

# Print allowed keys to serial
def print_keys():
  global KEYS_DICT
  if KEYS_DICT == {}:
    print('  [NONE]')
  else:
    for key in KEYS_DICT:
      print('  ' + key + ' - ' + KEYS_DICT[key])

# Delete all allowed keys
def purge_keys():
  global KEYS_DICT
  wipe_keys()
  save_keys_to_esp()
  resync_html_content()

# Unlock for duration specified as argument
def unlock(dur):
  np[0] = np_unlocked
  np.write()
  lockRelay_pin.value(1)
  unlockBeep()
  print('  Unlocked')
  publish_status('Unlocked')
  time.sleep_ms(dur)
  lockRelay_pin.value(0)
  np[0] = np_standby
  np.write()
  print('  Locked')
  publish_status('Locked')

def mon_bell_butt():
  global current
  if (int(bellButton_pin.value()) == 0) and (bell_ringing == False):
    print('bell button pushed')
    uasyncio.create_task(ring_bell(current))

def mon_mag_sr():
  global mag_state
  global opening_type
  global magnetic_sensor_present
  global doorbell
  
  if magnetic_sensor_present == False:
    return
  
  if (int(magSensor.value()) == 0) and (mag_state == 1):
    print(opening_type + ' sensor closed')
    publish_status(opening_type + ' sensor closed')
    mag_state = 0
  elif (int(magSensor.value()) == 1) and (mag_state == 0):
    print(opening_type + ' sensor opened')
    doorbell.stop()
    publish_status(opening_type + ' sensor opened')
    mag_state = 1
  else:
    return
    
# Async function to listen for exit button presses
def mon_exit_butt():
  global add_hold_time
  global add_mode
  global doorbell
  
  if int(exitButton_pin.value()) == 0:
    doorbell.stop()
    buzzer_pin.value(0)
    time_held = 0
    while (int(exitButton_pin.value()) == 0 and time_held <= add_hold_time):
      time.sleep_ms(10)
      time_held += 10
    if time_held > add_hold_time:
      uasyncio.create_task(key_add_mode())
    elif add_mode == False:
      print('Exit button pressed')
      publish_status('Exit button pressed')
      unlock(exitBut_dur)

# Async function to listen for proramming button presses
def mon_prog_butt():
  global add_hold_time
  global sd_present
  global doorbell
  
  if int(progButton_pin.value()) == 0:
    doorbell.stop()
    time_held = 0
    while (int(progButton_pin.value()) == 0 and time_held <= add_hold_time):
      time.sleep_ms(10)
      time_held += 10
    if time_held > add_hold_time:
      if (sd_present == False):
        print ('SD Card not present')
        return
      print('Importing from SD card')
      prog_sd_beeps()
      try:
        import_keys_from_sd()
        import_config_from_sd()
        print('Import from SD card completed, restarting...')
        machine.reset()
      except:
        print('ERROR: Import from SD failed!')
    else:
      publish_status('Prog button pressed')
      print('prog button pressed')

# Async function to listed for MQTT commands
def mon_cmd_topic():
  global mqtt_online
  if mqtt_online:
    try:
      mqtt.check_msg()
    except:
      print('error checking MQTT topic')

# Async function to send PingReq messages to MQTT broker
async def mqtt_ping():
  global mqtt_online
  while mqtt_online:
    mqtt.ping()
    await uasyncio.sleep(60)

# Play doorbel tone
async def ring_bell(tune):
  global bell_ringing
  global doorbell
  if (bell_ringing) or (silent_mode):
    return
  bell_ringing = True
  np[0] = np_doorbell
  np.write()
  print ('  Ringing bell - melody: ' + tune['title'])
  publish_status('Ringing bell')
  doorbell = music(tune['music'], pins=[buzzer_pin])
  while doorbell.tick():
    await uasyncio.sleep_ms(tune['speed'])

  doorbell.stop()
  np[0] = np_standby
  np.write()
  bell_ringing = False
  print ('  Bell finished')

# Enter mode to add new key
def key_add_mode():
  global add_mode
  global add_mode_intervals
  global add_mode_counter
  add_mode = True
  np[0] = np_add
  np.write()
  print('Key add mode')
  add_mode_counter = 0
  print('Waiting for new key',end=' ')
  add_mode = True
  while add_mode_counter < add_mode_intervals:
    print('.',end=' ')
    lil_bip()
    await uasyncio.sleep_ms(int(addKey_dur/add_mode_intervals))
    add_mode_counter += 1
  if add_mode == True:
    print('No key detected.')
    add_mode = False
  np[0] = np_standby
  np.write()

# "Beep-Beep"
def unlockBeep():
  if silent_mode == True:
    return
  buzzer_pin.value(1)
  time.sleep_ms(75)
  buzzer_pin.value(0)
  time.sleep_ms(100)
  buzzer_pin.value(1)
  time.sleep_ms(75)
  buzzer_pin.value(0)

# "Beeeep-Beeeep"
def invalidBeep():
  if silent_mode == True:
    return
  buzzer_pin.value(1)
  time.sleep_ms(750)
  buzzer_pin.value(0)
  time.sleep_ms(100)
  buzzer_pin.value(1)
  time.sleep_ms(750)
  buzzer_pin.value(0)
  time.sleep_ms(100)
  buzzer_pin.value(1)
  time.sleep_ms(750)
  buzzer_pin.value(0)
  time.sleep_ms(100)
  buzzer_pin.value(1)
  time.sleep_ms(750)
  buzzer_pin.value(0)

# "Bip"
def lil_bip():
  if silent_mode == True:
    return
  buzzer_pin.value(1)
  time.sleep_ms(1)
  buzzer_pin.value(0)

def prog_sd_beeps():
  if silent_mode == True:
    return
  buzzer_pin.value(1)
  time.sleep_ms(50)
  buzzer_pin.value(0)
  time.sleep_ms(50)
  buzzer_pin.value(1)
  time.sleep_ms(50)
  buzzer_pin.value(0)
  time.sleep_ms(50)
  buzzer_pin.value(1)
  time.sleep_ms(50)
  buzzer_pin.value(0)

# --------- MAIN -----------

async def main_loop():
  while True:
    wdt.feed()
    mon_exit_butt()
    mon_prog_butt()
    mon_bell_butt()
    mon_cmd_topic()
    mon_mag_sr()
    await uasyncio.sleep_ms(50)
  
if int(DS01.value()) == 1:
  print('DS01 ON')
else:
  print('DS01 OFF')

if int(DS02.value()) == 1:
  print('DS02 ON - OTA Mode enabled')
  ota_updater = OTAUpdater(wifi_ssid, wifi_pass, firmware_url, "main.py")
  ota_updater.download_and_install_update_if_available()
else:
  print('DS02 OFF')

if int(DS03.value()) == 1:
  print('DS03 ON - Silent Mode active')
  silent_mode = True
else:
  print('DS03 OFF')

if int(DS04.value()) == 1:
  print('DS04 ON - Garage Mode Activated')
  garage_mode = True
  exitBut_dur = garageMode_dur
  http_dur = garageMode_dur
  key_dur = garageMode_dur
  mqtt_dur = garageMode_dur
else:
  print('DS04 OFF')

if silent_mode == True:
  print('Silent Mode activated')

try:
  connect_wifi()
except:
  print('ERROR: Could not connect to WiFi')

try:
  mqtt = MQTTClient(mqtt_clid, mqtt_brok, port=mqtt_port, user=mqtt_user, password=mqtt_pass, keepalive=300)
  mqtt.set_callback(sub_cb)
  mqtt.connect()
  print ('Connected to MQTT broker ' + mqtt_brok)
  mqtt_online = True
except:
  print('ERROR: Could not connect to MQTT Broker')
  mqtt_online = False

if mqtt_online:
  try:
    mqtt.subscribe(mqtt_cmd_top)
    print ('Subscribed to topic ' + mqtt_cmd_top.decode('utf-8'))
  except: 
    print('ERROR: Could not subscribe to MQTT command topic ' + mqtt_cmd_top.decode('utf-8'))

web_server = Microdot()

uasyncio.create_task(main_loop())

if mqtt_online:
  uasyncio.create_task(mqtt_ping())

@web_server.route('/')
def hello(request):
  return main_html, 200, {'Content-Type': 'text/html'}

@web_server.route('/config_network')
def config_network(request):
  resync_config_network_content()
  return config_network_html, 200, {'Content-Type': 'text/html'}

@web_server.route('/config_network/update')
def config_network_update(request):
  #do le updates
  resync_config_network_content()
  return config_network_html, 200, {'Content-Type': 'text/html'}

@web_server.route('/config_mqtt')
def config_mqtt(request):
  resync_config_mqtt_content()
  return config_mqtt_html, 200, {'Content-Type': 'text/html'}

@web_server.route('/config_doorbell')
def config_doorbell(request):
  resync_config_doorbell_content()
  return config_doorbell_html, 200, {'Content-Type': 'text/html'}

@web_server.route('/unlock')
def unlock_http(request):
  print('Unlock command recieved from WebUI')
  unlock(http_dur)
  return main_html, 200, {'Content-Type': 'text/html'}

@web_server.route('/reset')
def reset_http(request):
  print('Reset command recieved from WebUI')
  machine.reset()
  return main_html, 200, {'Content-Type': 'text/html'}

@web_server.route('/bell')
async def bell_http(request):
  global current
  print('Bell command recieved from WebUI')
  uasyncio.create_task(ring_bell(current))
  return main_html, 200, {'Content-Type': 'text/html'}

@web_server.route('/download/<string:filename>', methods=['GET', 'POST'])
def dl_file(request, filename):
  return send_file(str('/' + filename), status_code=200)

@web_server.route('/print_keys')
def print_keys_http(request):
  print('Print keys command recieved from WebUI')
  print_keys()
  return main_html, 200, {'Content-Type': 'text/html'}

@web_server.route('/purge_keys')
def purge_keys_http(request):
  print('Purge keys command recieved from WebUI')
  purge_keys()
  return main_html, 200, {'Content-Type': 'text/html'}

@web_server.route('/add_mode')
def web_add_mode(request):
  print('Add-key-mode command recieved from WebUI')
  uasyncio.create_task(key_add_mode())
  return main_html, 200, {'Content-Type': 'text/html'}

@web_server.route('/add_key/<string:key>', methods=['GET', 'POST'])
def content(request, key):
  print('Add key command recieved from WebUI ' + key)
  add_key(key)
  return main_html, 200, {'Content-Type': 'text/html'}

@web_server.route('/rem_key/<string:key>', methods=['GET', 'POST'])
def content(request, key):
  print('Remove key command recieved from WebUI ' + key)
  rem_key(key)
  return main_html, 200, {'Content-Type': 'text/html'}

@web_server.route('/ren_key/<string:key>/<string:name>', methods=['GET', 'POST'])
def content(request, key, name):
  print('Rename key command recieved from WebUI  to rename ' + key + ' to ' + name)
  ren_key(key, name)
  return main_html, 200, {'Content-Type': 'text/html'}

@web_server.route('/set_bell/<string:tone>', methods=['GET', 'POST'])
def content(request, tone):
  global Doorbells
  global current
  print('Switching doorbell tone to ' + tone)
  current = Doorbells[tone]
  CONFIG_DICT['doorbell'] = tone
  save_config_to_esp()
  resync_config_doorbell_content()
  return config_doorbell_html, 200, {'Content-Type': 'text/html'}

@web_server.route('/config_doorbell/test', methods=['GET', 'POST'])
def content(request):
  global current
  doorbell.stop()
  print('Testing doorbell: ' + current["title"])
  uasyncio.create_task(ring_bell(current))
  return config_doorbell_html, 200, {'Content-Type': 'text/html'}

@web_server.route('/config_doorbell/stop', methods=['GET', 'POST'])
def content(request):
  global current
  doorbell.stop()
  return config_doorbell_html, 200, {'Content-Type': 'text/html'}

start_server()