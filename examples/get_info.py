#!/usr/bin/env python3
from pyharp.device import Device, DeviceMode
from pyharp.messages import HarpMessage
from pyharp.messages import MessageType
from struct import *
import os


# ON THIS EXAMPLE
#
# This code opens the connection with the device and displays the information
# Also saves device's information into variables


# Open the device and print the info on screen
# Open serial connection and save communication to a file
if os.name == 'posix': # check for Linux.
    #device = Device("/dev/harp_device_00", "ibl.bin")
    device = Device("/dev/ttyACM0")
    #device = Device("/dev/ttyUSB0")
else: # assume Windows.
    device = Device("COM95", "ibl.bin")
device.info()                           # Display device's info on screen

# Get some of the device's parameters
device_id = device.WHO_AM_I                     # Get device's ID
device_id_description = device.WHO_AM_I_DEVICE  # Get device's user name
device_user_name = device.DEVICE_NAME           # Get device's user name

# Get versions
device_fw_h = device.FIRMWARE_VERSION_H         # Get device's firmware version
device_fw_l = device.FIRMWARE_VERSION_L         # Get device's firmware version
device_hw_h = device.HW_VERSION_H               # Get device's hardware version
device_hw_l = device.HW_VERSION_L               # Get device's hardware version
device_harp_h = device.HARP_VERSION_H           # Get device's harp core version
device_harp_l = device.HARP_VERSION_L           # Get device's harp core version
device_assembly = device.ASSEMBLY_VERSION       # Get device's assembly version

reg_dump = device.dump_registers()
for i in range(11):
    print(reg_dump[i])

# Close connection
device.disconnect()
