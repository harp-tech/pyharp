from pyharp.device import Device
from pyharp.messages import HarpMessage
from pyharp.messages import MessageType
from struct import *


# ON THIS EXAMPLE
#
# This code opens the connection with the device and update content on a register
# It uses register address 42, which stores the analog sensor's higher threshold in the IBLBehavior device
# This register is unsigned with 16 bits (U16)


# Open the device and print the info on screen
device = Device("COM95", "ibl.bin")     # Open serial connection and save communication to a file

# Read current analog sensor's higher threshold (ANA_SENSOR_TH0_HIGH) at address 42
analog_threshold_h = device.send(HarpMessage.ReadU16(42).frame).payload_as_int()
print(f"Analog sensor's higher threshold: {analog_threshold_h}")

# Increase current analog sensor's higher threshold by one unit
device.send(HarpMessage.WriteU16(42, analog_threshold_h+1).frame)

# Check if the register was well written
analog_threshold_h = device.send(HarpMessage.ReadU16(42).frame).payload_as_int()
print(f"Analog sensor's higher threshold: {analog_threshold_h}")

# Close connection
device.disconnect()