#!/usr/bin/env python3
from pyharp.drivers.behavior import Behavior
from pyharp.messages import HarpMessage
from pyharp.messages import MessageType
from struct import *
import os


# Open the device and print the info on screen
# Open serial connection and save communication to a file
device = None
if os.name == 'posix': # check for Linux.
    device = Behavior("/dev/harp_device_00", "ibl.bin")
else: # assume Windows.
    device = Behavior("COM95", "ibl.bin")

print(f"digital inputs: {device.all_input_states:03b}")
print(f"digital outputs: {device.all_output_states:016b}")
print(f"setting digital outputs")
#device.all_output_states = 0x0000 # Set the whole port directly.
#device.set_outputs(0xFFFF) # Set the values set to logic 1 only.
#device.clear_outputs(0xFFFF)# Clear values set to logic 1 only.
print(f"digital outputs: {device.all_output_states:016b}")
device.set_io_configuration(0b111)

# TODO: FIXME. IOs are not working
#device.set_io_configuration(0b111) # This is getting ignored?
#device.set_io_outputs(0b000)
#device.all_io_states = 0b000
#print(f"digital ios: {device.all_io_states:03b}")

#device.D0 = 0
#print(f"D0: {device.D0}")
#device.D0 = 1
#print(f"D0: {device.D0}")
#
#device.D1 = 0
#print(f"D1: {device.D1}")
#device.D1 = 1
#print(f"D1: {device.D1}")
#
#print(f"DI2: {device.DI2}")


#import time
#while True:
#    print(f"PORT0 IN State:  {device.port0_i0}")
#    print(f"PORT0 IO State:  {device.port0_io0}")
#    print(f"PORT0 OUT State:  {device.port0_o0}")
#    print(f"all port io states:     {device.all_port_io_states}")
#    print(f"all port output states: {device.all_port_output_states}")
#    print()
#    time.sleep(0.1)
