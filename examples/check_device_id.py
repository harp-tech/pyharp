#!/usr/bin/env python3
from pyharp.device import Device
from pyharp.messages import HarpMessage
from pyharp.messages import MessageType
from pyharp.device_names import device_names
from struct import *
import os


# ON THIS EXAMPLE
#
# This code check if the device at COMx is the expected device.
# The device ID used is the 2080, the IblBehavior


# Open the device
# Open serial connection
if os.name == "posix": # check for Linux.
    device = Device("/dev/ttyUSB0")
else: # assume Windows.
    device = Device("COM95")

# Get some of the device's parameters
device_id = device.WHO_AM_I                     # Get device's ID
device_id_description = device.WHO_AM_I_DEVICE  # Get device's user name
device_user_name = device.DEVICE_NAME           # Get device's user name

# Check if we are dealing with the correct device
if device_id in device_names:
    print("Correct device was found!")
    print(f"Device's ID: {device_id}")
    print(f"Device's name: {device_id_description}")
    print(f"Device's user name: {device_user_name}")
else:
    print("Device not correct or is not a Harp device!")

# Close connection
device.disconnect()
