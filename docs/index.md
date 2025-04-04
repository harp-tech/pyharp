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
from pyharp.device import Device

# Connect to a device
device = Device("/dev/ttyUSB0")

# Get device information
device.info()

# define register_address
register_address = 32

# Read from register
value = device.read_u8(register_address)

# Write to register
device.write_u8(register_address, value)

# Disconnect when done
device.disconnect()
```

or using the `with` statement:

```python
from pyharp.device import Device

with Device("/dev/ttyUSB0") as device:
    # Get device information
    device.info()

    # define register_address
    register_address = 32

    # Read from register
    value = device.read_u8(register_address)

    # Write to register
    device.write_u8(register_address, value)
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
