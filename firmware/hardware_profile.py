"""PlatformIO pre-build: no guessed motion parameters or private profile in Git."""
Import('env')
import json
import hashlib
import os
from pathlib import Path

mode = env.GetProjectOption('custom_hardware_mode','disabled')
flags = [('GRASSROOT_HARDWARE_MODE', {'disabled':0,'calibration':1,'run':2}[mode])]
if mode == 'run':
    path = Path(os.environ.get('GRASSROOT_HARDWARE_PROFILE',str(Path(env['PROJECT_DIR']).parent/'hardware.local.json')))
    p = json.loads(path.read_text())
    if not (p.get('wiringVerified') is True and p.get('motorRatingVerified') is True and p.get('acknowledged') is True):
        raise ValueError('Run profile requires verified wiring, motor rating and explicit calibration acknowledgement')
    if p.get('cellCm') != 22 or p.get('supplyVolts') != 6:
        raise ValueError('Expected 22 cm cell / 6 V supply profile')
    polarity=p.get('polarity',[])
    if len(polarity)!=4 or any(type(v) is not int or v not in (-1,1) for v in polarity):
        raise ValueError('Measure LF/RF/LR/RR polarities first')
    for key,macro,maximum in [('msPerCell','PROFILE_MS_CELL',8000),('msPer90','PROFILE_MS_90',8000),('driveDuty','PROFILE_DRIVE_DUTY',200),('turnDuty','PROFILE_TURN_DUTY',200)]:
        value=p.get(key)
        if type(value) is not int or not 1<=value<=maximum:raise ValueError(f'Measure {key} before building run profile')
        flags.append((macro,value))
    for i,value in enumerate(polarity):flags.append((f'PROFILE_POLARITY_{i}',value))
    ident=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()[:16]
    flags.append(('PROFILE_ID','\\"'+ident+'\\"'))
env.Append(CPPDEFINES=flags)
