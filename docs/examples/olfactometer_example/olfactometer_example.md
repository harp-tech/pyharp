# Olfactometer Example

This example shows how to interface with the [Harp Olfactometer](https://github.com/harp-tech/device.olfactometer).

In this example, the flows for the different channels are enabled to random flow values, then every odor valve is opened, one at a time every 5 seconds, and finally the flow is disabled before closing the connection with the device. During this time, the actual flows in every channel are being printed out in the terminal.

!!! warning
    Don't forget to change the `SERIAL_PORT` to the one that corresponds to your device! The `SERIAL_PORT` must be denoted as `/dev/ttyUSBx` in Linux and `COMx` in Windows, where `x` is the number of the serial port.

<!--codeinclude-->
```python
[](./olfactometer_example.py)
```
<!--/codeinclude-->
