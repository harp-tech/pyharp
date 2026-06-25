# Read and Write from Registers

This example demonstrates how to read and write from registers, using the core registers exposed by `harp.device`. Device-specific registers (e.g. a [Harp Behavior](https://harp-tech.org/api/Harp.Behavior.html)'s digital I/O) are used the same way — pass that device's register classes to `read`/`write`.

!!! warning
    Don't forget to change the `SERIAL_PORT` to the one that corresponds to your device! The `SERIAL_PORT` must be denoted as `/dev/ttyUSBx` in Linux and `COMx` in Windows, where `x` is the number of the serial port.

<!--codeinclude-->
```python
[](./read_and_write_from_registers.py)
```
<!--/codeinclude-->
