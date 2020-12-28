import logging
from configparser import ConfigParser, NoSectionError, NoOptionError
from os import system
from os.path import abspath, dirname
from time import sleep
from datetime import datetime
from blynklib import Blynk
from blynktimer import Timer
from gpiozero import CPUTemperature, LoadAverage, DiskUsage


# Set default values
DEFAULT_CONFIG_PATH = "/etc/blynk-raspberrypi.conf"
DEFAULT_NOTIFICATIONS_EMAIL = "example@example.com"
DEFAULT_NUM_CORES = 1

# Tune console logging
_log = logging.getLogger("BlynkLog")
logFormatter = logging.Formatter("%(asctime)s [%(levelname)s]  %(message)s")
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
_log.addHandler(consoleHandler)
_log.setLevel(logging.DEBUG)

# Parse config file
config = ConfigParser(
    {"notifications_email": DEFAULT_NOTIFICATIONS_EMAIL, "num_cores": DEFAULT_NUM_CORES}
)
config.read(DEFAULT_CONFIG_PATH)

try:
    auth_token = config.get("general", "auth_token")

except (NoSectionError, NoOptionError):
    _log.error("No Blynk auth token found in /etc/blynk-raspberrypi.conf. Exiting.")
    raise SystemExit(1)

notifications_email = config.get("general", "notifications_email")
num_cores = config.getint("system_metrics", "num_cores")

# Initialize Blynk connection and timer
blynk = Blynk(
    auth_token,
    server="blynk-cloud.com",
    port=443,
    ssl_cert="{}/blynk-cloud.com.crt".format(dirname(abspath(__file__))),
    heartbeat=30,
    rcv_buffer=1024,
    log=_log.info,
)
timer = Timer()


# Notify on connect: push and email
@blynk.handle_event("connect")
def connect_handler():
    sleep(2)
    blynk.email(notifications_email, "Raspberry Pi", "Raspberry Pi connected.")
    blynk.notify("Raspberry Pi connected.")


# Notify on disconnect: email (push notification is sent by widget)
@blynk.handle_event("disconnect")
def disconnect_handler():
    sleep(2)
    blynk.email(notifications_email, "Raspberry Pi", "Raspberry Pi disconnected.")


# Read system time (only when Blynk app is open)
@blynk.handle_event("read V0")
def read_virtual_pin_handler(pin):
    data = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    blynk.virtual_write(pin, data)


# Push system metrics to Blynk Cloud
## CPU Temperature (Celsius), each second, send push notification on critical
@timer.register(vpin_num=1, interval=1, run_once=False)
def write_to_virtual_pin(vpin_num=2):
    cpu_temp = CPUTemperature()
    blynk.virtual_write(vpin_num, cpu_temp.temperature)
    if cpu_temp.is_active:
        blynk.notify("CPU Temperature Critical!")


## Load Average (normalized to cores count), each second
@timer.register(vpin_num=3, interval=1, run_once=False)
def write_to_virtual_pin(vpin_num=4):
    load_avg = LoadAverage(min_load_average=0, max_load_average=num_cores, minutes=1)
    blynk.virtual_write(vpin_num, load_avg.value)


## Disk Usage (percent), each second, send push notification on critical
@timer.register(vpin_num=5, interval=1, run_once=False)
def write_to_virtual_pin(vpin_num=6):
    disk_usage = DiskUsage()
    blynk.virtual_write(vpin_num, disk_usage.usage)
    if disk_usage.is_active:
        blynk.notify("Disk almost full!")


# Listen for reboot events
@blynk.handle_event("write V255")
def write_virtual_pin_handler(pin, value):
    if value[0] == "1":
        _log.info("Caught reboot event, restarting the system")
        system("/usr/bin/reboot")


def main():
    # Run application and timer loops
    while True:
        blynk.run()
        timer.run()


if __name__ == "__main__":
    main()
