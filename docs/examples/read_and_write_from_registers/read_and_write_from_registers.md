# Read and Write from Registers

This example demonstrates how to read and write from registers. In this particular example, the [Harp Behavior](https://harp-tech.org/api/Harp.Behavior.html) is used to read from the DI3 pin and to turn on and off the DO0 pin, according to the schematics shown [below](#schematics).

!!! warning
    Don't forget to change the `SERIAL_PORT` to the one that corresponds to your device! The `SERIAL_PORT` must be denoted as `/dev/ttyUSBx` in Linux and `COMx` in Windows, where `x` is the number of the serial port.

<!--codeinclude-->
```python
[](./read_and_write_from_registers.py)
```
<!--/codeinclude-->

## Schematics

!!! warning
    _TODO_
