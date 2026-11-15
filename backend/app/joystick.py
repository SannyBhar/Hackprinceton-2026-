"""Timestamped continuous input, USB adapter and conservative reverse compiler."""
import asyncio
import json
import math
import time
from pydantic import BaseModel, Field, StrictInt
from .models import Instruction, RobotPose
from .compiler import plan


class JoystickSample(BaseModel):
    protocolVersion: int = 1
    seq: StrictInt = Field(ge=0)
    timestampMs: StrictInt = Field(ge=0)
    x: float = Field(ge=-1, le=1, allow_inf_nan=False)
    y: float = Field(ge=-1, le=1, allow_inf_nan=False)
    button: bool = False


def direction(x, y, dead_zone=.18):
    if max(abs(x),abs(y)) <= dead_zone: return 'STOP',0.
    if abs(y) >= abs(x): return ('FORWARD' if y < 0 else 'BACKWARD'),abs(y)
    return ('RIGHT' if x > 0 else 'LEFT'),abs(x)


def reconstruct(puzzle, segments, max_steps=5):
    instructions = [Instruction(op='START')]
    warnings = []
    for i, segment in enumerate(segments):
        action, poses = segment['action'], segment['poses']
        if action == 'STOP': continue
        valid = [RobotPose.model_validate(p) for p in poses if p.get('trackingValid')]
        if len(valid) < 2:
            warnings.append(f'segment {i+1}: insufficient observed trajectory')
            continue
        if len(valid) != len(poses): warnings.append(f'segment {i+1}: tracking gap')
        start, end = valid[0],valid[-1]
        distance = math.hypot(end.x-start.x,end.y-start.y)
        rotation = sum((b.headingDeg-a.headingDeg+180)%360-180 for a,b in zip(valid,valid[1:]))
        if action in ('LEFT','RIGHT'):
            turns = round(abs(rotation)/90)
            if distance > .2 or abs(abs(rotation)-turns*90) > 15 or turns == 0:
                warnings.append(f'segment {i+1}: uncertain turn or translation while turning')
            if rotation and ((rotation > 0) != (action == 'RIGHT')):
                warnings.append(f'segment {i+1}: rotation disagrees with input')
                continue
            instructions.extend(Instruction(op=action) for _ in range(min(turns,4)))
        else:
            rad = math.radians(start.headingDeg)
            along = (end.x-start.x)*math.sin(rad)-(end.y-start.y)*math.cos(rad)
            signed = along if action == 'FORWARD' else -along
            count = max(0,round(signed))
            lateral = abs((end.x-start.x)*math.cos(rad)+(end.y-start.y)*math.sin(rad))
            if count == 0 or abs(signed-count) > .25 or lateral > .2 or abs(rotation)>15:
                warnings.append(f'segment {i+1}: fractional/curved/slipped movement; approximation')
            for _ in range(min(count,400)):
                last = instructions[-1]
                if last.op == action and (last.steps or 0)<max_steps: last.steps += 1
                else: instructions.append(Instruction(op=action,steps=1))
    instructions.append(Instruction(op='STOP'))
    result = plan(puzzle,instructions,max_steps)
    warnings += result.errors
    return {'generated':[i.model_dump(mode='json') for i in instructions], 'warnings':warnings,
            'approximate':True, 'valid':result.ok}


class ContinuousRecorder:
    def __init__(self, session):
        self.session = session
        self.last_seq = -1
        self.last_received = 0
        self.last_button = False
        self.last_toggle = 0
        self.active = False
        self.segments = []
        self.raw = []
        self.commands = []
        self.error = None
        self.source = None

    async def sample(self, sample: JoystickSample, source='serial'):
        now = int(time.time()*1000)
        if sample.protocolVersion != 1: raise ValueError('unsupported joystick protocol')
        if self.source not in (None,source): raise ValueError('another input source owns the joystick lease')
        if sample.seq <= self.last_seq: return
        self.source = source
        self.last_seq, self.last_received = sample.seq,now
        toggle = sample.button and not self.last_button and now-self.last_toggle >= 600
        self.last_button = sample.button
        if toggle:
            self.last_toggle = now
            if self.active:
                await self.end('button stop')
                return
            if not getattr(self.session.robot,'continuous_supported',False):
                raise ValueError('robot firmware lacks continuous-drive protocol v2')
            await self.session.toggle_recording(grade=self.session.recording_grade,source='ui')
            self.active = True
            self.raw, self.commands, self.segments = [],[],[]
            self.session.recording['mode'] = 'continuous'
        if not self.active: return
        action,amount = direction(sample.x,sample.y)
        self.raw.append({**sample.model_dump(),'receivedAt':now})
        if not self.segments or self.segments[-1]['action']!=action:
            self.segments.append({'action':action,'poses':[]})
            self.observe(self.session.pose)
        if len(self.raw) > 36000:  # 30-minute bound at 20 Hz
            await self.end('recording length limit'); return
        command = {'action':action,'amount':amount,'sentAt':now}
        ack = await self.session.robot.drive(action,amount,250)
        self.commands.append({**command,'ack':ack})
        if ack.get('status') == 'ERROR': await self.end('drive transport failure')

    def observe(self, pose):
        if self.active and self.segments and pose is not None:
            self.segments[-1]['poses'].append(pose.model_dump())

    async def end(self, reason):
        if not self.active: return
        self.active = False
        await self.session.robot.stop(reason)
        record = self.session.recording
        record.update(rawInputs=self.raw,commands=self.commands,segments=self.segments)
        result = reconstruct(self.session.puzzle,self.segments,self.session.max_steps)
        await self.session._end_recording()
        record.update(result)
        record['stopReason'] = reason
        if record.get('summary') and reason not in ('button stop','instructor recording stop'):
            record['summary']['success'] = False
            record['summary']['details'].append('Recording ended by an operational stop')
        self.session.persist(self.session.storage.put_record,'recordings',record['id'],record)
        self.session.changed()

    async def watchdog(self):
        while True:
            await asyncio.sleep(.05)
            if self.active and int(time.time()*1000)-self.last_received>300:
                await self.end('stale joystick input')
                self.error='joystick input timed out'

    async def serial_loop(self, port):
        while True:
            device = None
            try:
                import serial
                device = await asyncio.to_thread(serial.Serial,port,115200,timeout=.1)
                self.last_seq,self.source=-1,None
                # Require a released button before a press on every new connection.
                self.last_button=True
                self.error=None
                while True:
                    line = await asyncio.to_thread(device.readline)
                    if not line: continue
                    if len(line)>4096: raise ValueError('oversized joystick sample')
                    await self.sample(JoystickSample.model_validate_json(line))
            except asyncio.CancelledError:
                await self.end('application shutdown'); raise
            except Exception as e:
                self.error=str(e)
                await self.end('joystick disconnected or invalid data')
                self.session.log('warn',f'joystick: {e}')
                self.session.changed()
                await asyncio.sleep(1)
            finally:
                if device is not None: await asyncio.to_thread(device.close)
