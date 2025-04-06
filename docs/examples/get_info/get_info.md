# Getting Device Info

This example demonstrates how to connect to a Harp device, read its info and dump the device's registers.

!!! warning
    Don't forget to change the `SERIAL_PORT` to the one that corresponds to your device! The `SERIAL_PORT` must be denoted as `/dev/ttyUSBx` in Linux and `COMx` in Windows, where `x` is the number of the serial port.

<!--codeinclude-->
```python
[](./get_info.py)
```
<!--/codeinclude-->
