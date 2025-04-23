# pyharp

Python implementation of the Harp protocol for hardware control and data acquisition.

## Installation

```bash
uv add pyharp
# or
pip install pyharp
```

## Quick Start

```python
from pyharp import MessageType, PayloadType
from pyharp.device import Device
from pyharp.messages import HarpMessage

# Connect to a device
device = Device("/dev/ttyUSB0")

# Get device information
device.info()

# define register_address
register_address = 32

# Read from register
value = device.send(HarpMessage.create(MessageType.READ, register_address, PayloadType.U8))

# Write to register
device.send(HarpMessage.create(MessageType.WRITE, register_address, PayloadType.U8, value))

# Disconnect when done
device.disconnect()
```

or using the `with` statement:

```python
from pyharp import MessageType, PayloadType
from pyharp.device import Device
from pyharp.messages import HarpMessage

with Device("/dev/ttyUSB0") as device:
    # Get device information
    device.info()

    # define register_address
    register_address = 32

    # Read from register
    value = device.send(HarpMessage.create(MessageType.READ, register_address, PayloadType.U8))

    # Write to register
    device.send(HarpMessage.create(MessageType.WRITE, register_address, PayloadType.U8, value))
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
