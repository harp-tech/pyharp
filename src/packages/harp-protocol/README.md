# harp-protocol

[![PyPI version](https://badge.fury.io/py/harp-protocol.svg)](https://badge.fury.io/py/harp-protocol)

The Harp Protocol is a binary communication protocol created in order to facilitate and unify the interaction between different devices. It was designed with efficiency and ease of parsing in mind.

For more detail please check Harp Tech's official documentation [here](https://harp-tech.org/protocol/BinaryProtocol-8bit.html).

`harp-protocol` provides the building blocks: message framing and the typed register/payload DSL. Each register knows how to build (`format`) and decode (`parse`) its frames.

```python
import numpy as np
from harp.protocol import HarpMessage, RegisterU16

class WhoAmI(RegisterU16):
    address = 0

frame = WhoAmI.format(np.uint16(1216))           # build a Write frame
value = WhoAmI.parse(HarpMessage.parse(frame))   # -> np.uint16(1216)
```

It carries no transport or device logic — see [`harp-device`](../harp-device) for the device layer.
