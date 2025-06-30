from collections import defaultdict

# This file contains the device names for the current version of the harp library.
# These names were extracted from https://github.com/harp-tech/protocol/blob/main/whoami.yml
# commit used: https://github.com/harp-tech/protocol/commit/3e2a228

current_device_names = {
    256: "USBHub",
    1024: "Poke",
    1040: "MultiPwmGenerator",
    1056: "Wear",
    1058: "WearBaseStationGen2",
    1072: "Driver12Volts",
    1088: "LedController",
    1104: "Synchronizer",
    1106: "InputExpander",
    1108: "OutputExpander",
    1121: "SimpleAnalogGenerator",
    1130: "StepperDriver",
    1136: "Archimedes",
    1140: "Olfactometer",
    1152: "ClockSynchronizer",
    1154: "TimestampGeneratorGen1",
    1158: "TimestampGeneratorGen3",
    1168: "CameraController",
    1170: "CameraControllerGen2",
    1184: "PyControlAdapter",
    1200: "FlyPad",
    1216: "Behavior",
    1224: "VestibularH1",
    1225: "VestibularH2",
    1232: "LoadCells",
    1236: "AnalogInput",
    1248: "RgbArray",
    1280: "SoundCard",
    1296: "SyringePump",
    1400: "LicketySplit",
    1401: "SniffDetector",
    1402: "Treadmill",
    1403: "cuTTLefish",
    1404: "WhiteRabbit",
    1405: "EnvironmentSensor",
    2064: "NeurophotometricsFP3002",
    2080: "Ibl_behavior_control",
    2094: "RfidReader",
    2110: "Pluma",
}

device_names = defaultdict(lambda: "NotSpecified")
device_names.update(current_device_names)
