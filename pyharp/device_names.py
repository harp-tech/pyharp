def get(value: int) -> str:
    if value == 1024:
        return "Poke"
    elif value == 1040:
        return "MultiPwm"
    elif value == 1056:
        return "Wear"
    elif value == 1072:
        return "VoltsDrive"
    elif value == 1088:
        return "LedController"
    elif value == 1104:
        return "Synchronizer"
    elif value == 1121:
        return "SimpleAnalogGenerator"
    elif value == 1136:
        return "Archimedes"
    elif value == 1152:
        return "ClockSynchronizer"
    elif value == 1168:
        return "Camera"
    elif value == 1184:
        return "PyControl"
    elif value == 1200:
        return "FlyPad"
    elif value == 1216:
        return "Behavior"
    elif value == 1232:
        return "LoadCells"
    elif value == 1248:
        return "AudioSwitch"
    elif value == 1264:
        return "Rgb"
    elif value == 1200:
        return "FlyPad"
    elif value == 2064:
        return "FP3002"
    elif value == 2080:
        return "IblBehavior"
    else:
        return "NotSpecified"
