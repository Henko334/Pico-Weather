import network
import urequests
import time
import socket
import json
import machine
import bme280

from machine import Pin, I2C
from time import sleep

# Initialize I2C communication
i2c = I2C(id=0, scl=Pin(17), sda=Pin(16), freq=10000)

# Wi-Fi credentials
SSID = "WifiNameHere"
PASSWORD = "PasswordHere"

# DB API list
url = 'http://192.168.0.3:5000/log_event'
url2 = 'http://192.168.0.3:5000/log_readings'

# Log file setup
LOG_FILE = "/log.txt"

# wifi satus LED
led = machine.Pin(0, machine.Pin.OUT)

# Initialize BME280 sensor
bme = bme280.bme280(i2c=i2c)
            
# reading variables
tempC = 0
hum = 0
pres = 0

def log_event(message):
    try:
        data = {
            "Event" : message
        }
        response = urequests.post(url, json=data)
        response.close()  # Free memory
    except Exception as e:
        with open(LOG_FILE, "a") as log_file:
            log_file.write(f"{time.time()}: {message}\n")

def log_readings(timer=None):
    try:
        data = {
            "Temperature" : tempC,
            "Humidity" : hum,
            "Pressure" : pres
            }
        response = urequests.post(url2, json=data)
        response.close()  # Free memory
        log_event("Sensor readings logged successfully.")
    except Exception as e:
        print("Failed to write readings to DB", e)

# Connect to Wi-Fi
def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)

    while not wlan.isconnected():
        # Blink LED when not connected
        led.value(1)  # Turn LED on
        time.sleep(0.5)
        led.value(0)  # Turn LED off
        time.sleep(0.5)

    # Turn LED on when connected
    led.value(1)

def check_wifi_status():
    wlan = network.WLAN(network.STA_IF)
    return wlan.isconnected()

# Start HTTP server on Pi Pico
def serve_data():
    addr = socket.getaddrinfo('192.168.0.113', 80)[0][-1]
    s = socket.socket()
    s.bind(addr)
    s.listen(1)

    while True:
        cl, addr = s.accept()
        cl.settimeout(30)

        try:
            # Read the HTTP request to check the requested path
            request = cl.recv(1024).decode()
            
            # Read sensor data
            global tempC, hum, pres
            tempC = float(bme.temperature.replace('C', '').replace('°C', ''))
            hum = float(bme.humidity.replace('%', ''))
            pres = float(bme.pressure.replace('hPa', ''))

            # Prepare weather data
            data = {
                "temperature": tempC,
                "humidity": hum,
                "pressure": pres,
            }

            # Check if the path is '/weather'
            if '/weather' in request:
                cl.send('HTTP/1.1 200 OK\r\n')
                cl.send('Content-Type: application/json\r\n\r\n')
                cl.send(json.dumps(data))
            else:
                # Handle invalid endpoint
                cl.send('HTTP/1.1 404 Not Found\r\n')
                cl.send('Content-Type: text/plain\r\n\r\n')
                cl.send('404 Not Found')

        except Exception as e:
            log_event(f"Error: {e}")
            cl.send('HTTP/1.1 500 Internal Server Error\r\n')
            cl.send('Content-Type: text/plain\r\n\r\n')
            cl.send('Error reading data')

        cl.close()

# Timer functions
wifi_timer = machine.Timer(-1)
reading_timer = machine.Timer(-1)

# Check Wi-Fi status every 5 minutes
def wifi_check(timer):
    if not check_wifi_status():
        led.value(1)  # Blink LED when not connected
        time.sleep(0.5)
        led.value(0)
    else:
        led.value(1)  # Keep LED on when connected

# Main program
connect_wifi(SSID, PASSWORD)

# Set timers
wifi_timer.init(period=300000, mode=machine.Timer.PERIODIC, callback=wifi_check)  # 5 minutes
reading_timer.init(period=900000, mode=machine.Timer.PERIODIC, callback=log_readings)  # 15 minutes

# Main loop to keep the program running
while True:
    serve_data()
    time.sleep(1)
