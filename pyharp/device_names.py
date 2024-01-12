from collections import defaultdict


current_device_names = \
    {1024: 'Poke',
     1040: 'MultiPwm',
     1056: 'Wear',
     1072: 'VoltsDrive',
     1088: 'LedController',
     1104: 'Synchronizer',
     1121: 'SimpleAnalogGenerator',
     1136: 'Archimedes',
     1152: 'ClockSynchronizer',
     1168: 'Camera',
     1184: 'PyControl',
     1200: 'FlyPad',
     1216: 'Behavior',
     1232: 'LoadCells',
     1248: 'AudioSwitch',
     1264: 'Rgb',
     1200: 'FlyPad',
     2064: 'FP3002',
     2080: 'IblBehavior'}
device_names = defaultdict(lambda: 'NotSpecified')
device_names.update(current_device_names)

