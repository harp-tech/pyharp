# harp-serial

[![PyPI version](https://badge.fury.io/py/harp-serial.svg)](https://badge.fury.io/py/harp-serial)

A Python library for communicating with Harp devices over serial connections.

## Installation

```bash
uv add harp-serial
# or
pip install harp-serial
```

## Quick Start

```python
from harp.protocol import MessageType, PayloadType
from harp.protocol.messages import HarpMessage
from harp.serial.device import Device

# Connect to a device
device = Device("/dev/ttyUSB0")
#device = Device("COM3")  # for Windows

# Get device information
device.info()

# define register_address
register_address = 32

# Read from register
reply = device.send(HarpMessage.create(MessageType.READ, register_address, PayloadType.U8))

# Write to register
device.send(HarpMessage.create(MessageType.WRITE, register_address, PayloadType.U8, reply.payload))

# Disconnect when done
device.disconnect()
```

or using the `with` statement:

```python
from harp.protocol import MessageType, PayloadType
from harp.protocol.messages import HarpMessage
from harp.serial.device import Device

with Device("/dev/ttyUSB0") as device:
    # Get device information
    device.info()

    # define register_address
    register_address = 32

    # Read from register
    reply = device.send(HarpMessage.create(MessageType.READ, register_address, PayloadType.U8))

    # Write to register
    device.send(HarpMessage.create(MessageType.WRITE, register_address, PayloadType.U8, reply.payload))
```

## for Linux

### Install UDEV Rules

Install by either copying `10-harp.rules` over to your `/etc/udev/rules.d` folder or by symlinking it with:
````
sudo ln -s /absolute/path/to/10-harp.rules /etc/udev/rules.d/10-harp.rules
````

Then reload udev rules with
````
sudo udevadm control --reload-rules
````
