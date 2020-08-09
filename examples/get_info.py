from pyharp.device import Device

# open serial connection and load info
device = Device("/dev/tty.usbserial-A106C8O9")
device.info()
device.disconnect()
