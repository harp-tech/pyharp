#!/usr/bin/env python3
from pyharp.device import Device
from pyharp.messages import HarpMessage
from pyharp.messages import MessageType
from struct import *
import os


# ON THIS EXAMPLE
#
# This code opens the connection with the device and update content on a register
# It uses register address 42, which stores the analog sensor's higher threshold in the IBLBehavior device
# This register is unsigned with 16 bits (U16)


# Open the device and print the info on screen
# Open serial connection and save communication to a file
if os.name == 'posix': # check for Linux.
    device = Device("/dev/harp_device_00", "ibl.bin")
else: # assume Windows.
    device = Device("COM95", "ibl.bin")

# Read current analog sensor's higher threshold (ANA_SENSOR_TH0_HIGH) at address 42
#analog_threshold_h = device.send(HarpMessage.ReadU16(42).frame).payload_as_int()
#print(f"Analog sensor's higher threshold: {analog_threshold_h}")


import time

print(f"System time: {time.perf_counter():.6f}")
data_stream = device.send(HarpMessage.ReadU8(33).frame) # returns a ReplyHarpMessage
#data_stream = device.send(HarpMessage.ReadS16(33).frame).payload_as_int_array()
print(f"Data Stream payload type: {data_stream.payload_type.name}")
print(f"Data Stream message type: {data_stream.message_type.name}")
print(f"Data Stream timestamp: {data_stream.timestamp}")
print(f"Data Stream num bytes: {data_stream.length}")
print(f"Data Stream payload: {data_stream.payload}")

print(f"System time: {time.perf_counter():.6f}")
event_reg_response = device.send(HarpMessage.ReadU8(77).frame) # returns a ReplyHarpMessage
print(f"EVNT_ENABLE payload type: {event_reg_response.payload_type.name}")
print(f"EVNT_ENABLE message type: {event_reg_response.message_type.name}")
print(f"EVNT_ENABLE timestamp:    {event_reg_response.timestamp}")
print(f"EVNT_ENABLE num bytes:    {event_reg_response.length}")
print(f"EVNT_ENABLE payload:      {event_reg_response.payload[0]:08b}")

## Increase current analog sensor's higher threshold by one unit
#device.send(HarpMessage.WriteU16(42, analog_threshold_h+1).frame)
#
## Check if the register was well written
#analog_threshold_h = device.send(HarpMessage.ReadU16(42).frame).payload_as_int()
#print(f"Analog sensor's higher threshold: {analog_threshold_h}")
#
## Read 10 samples of the analog sensor and display the values
## The value is at register STREAM[0], address 33
#analog_sensor = []
#for x in range(10):
#    value = device.send(HarpMessage.ReadS16(33).frame).payload_as_int()
#    analog_sensor.append(value & 0xffff)
#print(f"Analog sensor's values: {analog_sensor}")

# Close connection
device.disconnect()
