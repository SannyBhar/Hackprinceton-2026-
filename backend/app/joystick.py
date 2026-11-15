"""Timestamped continuous input, USB adapter and conservative reverse compiler."""
import asyncio
import json
import math
import time
import secrets
from collections import deque
from pydantic import BaseModel, Field, StrictInt, StrictBool
from .models import Instruction, RobotPose
from .compiler import plan


class JoystickSample(BaseModel):
    protocolVersion: StrictInt = 1
    bootId: str | None = Field(default=None, max_length=64)
    syncId: str | None = Field(default=None, max_length=64)
    syncTimestampMs: StrictInt = Field(default=0, ge=0)
    seq: StrictInt = Field(ge=0)
    timestampMs: StrictInt = Field(ge=0)
    x: float = Field(ge=-1, le=1, allow_inf_nan=False)
    y: float = Field(ge=-1, le=1, allow_inf_nan=False)
    button: StrictBool = False


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
        self.connected = False
        self.armed = False
        self.protocol = None
        self.boot_id = None
        self.sync_id = None
        self.sync_sent = 0.
        self.last_device_time = -1
        self.latest = None
        self.edges = deque()
        self.edge_limit = 16
        self.wakeup = asyncio.Event()
        self._neutral_task = None
        self._ingest_button = False

    def status(self):
        age = max(0,int(time.monotonic()*1000)-self.last_received) if self.last_received else None
        return dict(active=self.active, connected=self.connected, armed=self.armed,
                    fresh=age is not None and age <= 300, ageMs=age, error=self.error,
                    protocolVersion=self.protocol, source=self.source)

    def reset_connection(self):
        self.connected = False
        self.armed = False
        self.last_seq = self.last_device_time = -1
        self.boot_id = self.protocol = None
        self.source = "serial"
        self.last_received = 0
        self.last_button = self._ingest_button = True
        self.latest = None
        self.edges.clear()
        self.sync_id = secrets.token_hex(12)
        self.sync_sent = time.monotonic()*1000
        return {'type':'sync', 'protocolVersion':2, 'syncId':self.sync_id}

    def ingest(self, sample):
        """No motor awaits here: acquisition always drains USB independently of ACKs."""
        now = time.monotonic()*1000
        if sample.protocolVersion != 2:
            raise ValueError('joystick firmware v2 required; flash the XIAO joystick target')
        if sample.syncId != self.sync_id:
            return  # flushed/replayed frames from a previous host lease
        if not sample.bootId:
            raise ValueError('joystick boot identity missing')
        if self.boot_id is not None and sample.bootId != self.boot_id:
            raise ValueError('joystick rebooted; reconnect and release controls')
        age = now-self.sync_sent-(sample.timestampMs-sample.syncTimestampMs)
        if not -100 <= age <= 150:
            raise ValueError('delayed joystick input')
        if sample.seq <= self.last_seq or sample.timestampMs <= self.last_device_time:
            raise ValueError('replayed joystick input')
        self.boot_id, self.protocol, self.connected = sample.bootId, 2, True
        self.source = 'serial'
        self.last_seq, self.last_device_time = sample.seq, sample.timestampMs
        self.last_received = int(now)
        if not self.armed:
            if sample.button or direction(sample.x,sample.y)[0] != 'STOP':
                return
            self.armed = True
            self.last_button = self._ingest_button = False
            self.error = None
        if self.active:
            self.raw.append({**sample.model_dump(),'receivedAt':int(time.time()*1000)})
        if sample.button != self._ingest_button:
            if len(self.edges) >= self.edge_limit:
                raise ValueError('joystick button queue overflow')
            self.edges.append((sample,int(now)))
            self._ingest_button = sample.button
        if self.active and direction(sample.x,sample.y)[0] == 'STOP':
            previous=self.latest[0] if self.latest else None
            if previous is None or direction(previous.x,previous.y)[0] != 'STOP':
                if self._neutral_task is None or self._neutral_task.done():
                    self._neutral_task=asyncio.create_task(self.session.robot.stop('neutral input'))
        self.latest = (sample,int(now))
        self.wakeup.set()

    async def consume(self):
        while True:
            await self.wakeup.wait()
            self.wakeup.clear()
            while self.edges:
                sample,received = self.edges.popleft()
                if time.monotonic()*1000-received > 300:
                    raise ValueError('delayed joystick button edge')
                # Edges toggle recording; old axes are never replayed.
                await self.sample(sample, validated=True, edge=True)
            item,self.latest = self.latest,None
            if item and self.armed:
                sample,received=item
                if time.monotonic()*1000-received > 150:
                    raise ValueError('delayed joystick axes')
                await self.sample(sample, validated=True)

    async def sample(self, sample: JoystickSample, source='serial', *, validated=False, edge=False):
        now = int(time.time()*1000)
        if validated and not self.armed: return
        if not validated:
            if self.session.robot.name != 'simulator' or sample.protocolVersion != 1:
                raise ValueError('physical joystick requires synchronized firmware protocol v2')
            if self.source not in (None,source): raise ValueError('another input source owns the joystick lease')
            if sample.seq <= self.last_seq: return
            self.source,self.protocol,self.connected,self.armed = source,1,True,True
            self.last_seq,self.last_received = sample.seq,int(time.monotonic()*1000)
        toggle = sample.button and not self.last_button
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
            self.raw, self.commands, self.segments = [{**sample.model_dump(),'receivedAt':now}],[],[]
            self.session.recording['mode'] = 'continuous'
            self.session.changed()
        if not self.active or (validated and not self.armed): return
        if edge: return
        action,amount = direction(sample.x,sample.y)
        if not validated: self.raw.append({**sample.model_dump(),'receivedAt':now})
        if not self.segments or self.segments[-1]['action']!=action:
            self.segments.append({'action':action,'poses':[]})
            self.observe(self.session.pose)
        if len(self.raw) > 36000:  # 30-minute bound at 20 Hz
            await self.end('recording length limit'); return
        command = {'action':action,'amount':amount,'sentAt':now}
        record = self.session.recording
        command['ack'] = {'status':'PENDING'}
        self.commands.append(command)
        ack = await self.session.robot.drive(action,amount,250)
        command['ack'] = ack
        if not self.active and record.get('id'):
            self.session.persist(self.session.storage.put_record,'recordings',record['id'],record)
        if ack.get('status') == 'ERROR' and self.session.recording is record:
            await self.end('drive transport failure')

    def observe(self, pose):
        if self.active and self.segments and pose is not None:
            self.segments[-1]['poses'].append(pose.model_dump())

    async def end(self, reason):
        if not self.active: return
        self.active = False
        self.armed = False
        self.edges.clear()
        self.latest = None
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
            if self.active and int(time.monotonic()*1000)-self.last_received>300:
                await self.end('stale joystick input')
                self.error='joystick input timed out'
                self.session.changed()

    async def serial_loop(self, port):
        while True:
            device = consumer = None
            try:
                import serial
                device = await asyncio.to_thread(serial.Serial,port,115200,timeout=.05)
                await asyncio.to_thread(device.reset_input_buffer)
                sync = self.reset_connection()
                await asyncio.to_thread(device.write,(json.dumps(sync)+'\n').encode())
                self.session.changed()
                consumer = asyncio.create_task(self.consume())
                last_publish = 0
                while True:
                    if consumer.done():
                        consumer.result()
                    line = await asyncio.to_thread(device.readline)
                    if not line:
                        if not self.connected and time.monotonic()*1000-self.sync_sent > 2000:
                            raise ValueError('joystick protocol v2 sync timed out; check firmware and USB serial')
                        if time.monotonic()*1000-self.last_received > 300 and self.connected:
                            self.connected = self.armed = False
                            await self.end('stale joystick input')
                            raise ValueError('joystick input timed out')
                        continue
                    if len(line)>4096: raise ValueError('oversized joystick sample')
                    self.ingest(JoystickSample.model_validate_json(line))
                    if time.monotonic()-last_publish > .25:
                        self.session.changed()
                        last_publish=time.monotonic()
            except asyncio.CancelledError:
                await self.end('application shutdown'); raise
            except Exception as e:
                self.error=str(e)
                self.connected = self.armed = False
                self.edges.clear()
                self.latest=None
                await self.end('joystick disconnected or invalid data')
                self.session.log('warn',f'joystick: {e}')
                self.session.changed()
                await asyncio.sleep(1)
            finally:
                if consumer:
                    consumer.cancel()
                    await asyncio.gather(consumer,return_exceptions=True)
                if device is not None: await asyncio.to_thread(device.close)
