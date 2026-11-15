"""ESP32 WebSocket transport (UNVERIFIED against hardware).

Wire protocol (JSON text frames), matching firmware/esp32/codeanywhere/codeanywhere.ino:
  laptop -> robot  {"type":"cmd","runId","instrIndex","msgId","kind":"MOVE|TURN|STOP","value"}
  laptop -> robot  {"type":"hb","t":<ms>}                     every 250 ms
  robot  -> laptop {"type":"ack","msgId","status":"ACCEPTED|DONE|STOPPED|DUPLICATE|ERROR","error"?}
Firmware stops motors if no heartbeat for 1000 ms and bounds every command's duration.

Pose is ESTIMATED from the commands themselves (dead reckoning): the robot has no sensors, so
a MOVE advances the estimate across cells at the measured msPerCell from the private hardware
profile, and a TURN changes heading when the robot acknowledges it. This is what lights tiles
during a run when the overhead camera is not used. It reflects what the robot was told to do,
not where it physically ended up.
"""
from __future__ import annotations

import asyncio
import json
import math
import time
from typing import Optional

from ..models import RobotPose
from .base import Ack, PoseCallback, Primitive


class Esp32WebSocketRobot:
    name = "esp32"

    def __init__(self, url: str, ack_timeout_s: float = 15.0):
        self.url = url
        self.ack_timeout_s = ack_timeout_s
        self.on_pose: Optional[PoseCallback] = None
        # Dead-reckoned pose (board units: x = col + 0.5, y = row + 0.5, 0 deg = north = -y).
        self.x, self.y, self.heading = 0.5, 0.5, 0.0
        self._motion: Optional[dict] = None   # active MOVE: start time, duration, from/to
        self.continuous_supported = False
        self._drive_seq = 0
        self.on_status = None
        self.error = None
        self.readiness = {'ready':False, 'error':'waiting for firmware readiness', 'mode':'unknown'}
        self._ws = None
        self._pending: dict[str, asyncio.Future] = {}
        self._tasks: list[asyncio.Task] = []

    @property
    def connected(self) -> bool:
        return self._ws is not None

    async def start(self) -> None:
        self._tasks.append(asyncio.create_task(self._connect_loop()))
        self._tasks.append(asyncio.create_task(self._pose_loop()))

    # ------------------------------------------------------------------ dead reckoning
    def _ms_per_cell(self) -> Optional[int]:
        try:
            from ..hardware import load_profile
            return load_profile().msPerCell
        except Exception:
            return None

    def _current_xy(self, at_ms: Optional[int] = None):
        m = self._motion
        if not m:
            return self.x, self.y
        t = (time.time() * 1000 if at_ms is None else at_ms) - m["start"]
        f = 0.0 if m["dur"] <= 0 else max(0.0, min(1.0, t / m["dur"]))
        return m["x0"] + (m["x1"] - m["x0"]) * f, m["y0"] + (m["y1"] - m["y0"]) * f

    def _emit(self):
        if self.on_pose is None:
            return
        x, y = self._current_xy()
        self.on_pose(RobotPose(timestampMs=int(time.time() * 1000), x=x, y=y,
                               headingDeg=self.heading % 360, trackingValid=True))

    async def _pose_loop(self):
        while True:  # steady stream keeps tile timing live and the session's stale watchdog fed
            self._emit()
            await asyncio.sleep(0.05)

    async def close(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        if self._ws is not None:
            await self._ws.close()
        self._ws = None
        self.readiness.update(ready=False,error="robot closed")

    async def _connect_loop(self):
        import websockets  # provided by uvicorn[standard]
        while True:
            try:
                async with websockets.connect(self.url, ping_interval=None) as ws:
                    self._ws = ws
                    hb = asyncio.create_task(self._heartbeat(ws))
                    try:
                        async for raw in ws:
                            msg = json.loads(raw)
                            if msg.get("type") == "hello":
                                self.continuous_supported = msg.get("protocolVersion") == 2
                                self.readiness = {k:msg.get(k) for k in ('outputsEnabled','calibrated','mode','profileId','remainingCommands')}
                                try:
                                    from ..hardware import load_profile
                                    profile=load_profile()
                                    ready=bool(self.continuous_supported and msg.get('outputsEnabled') and msg.get('calibrated') and
                                               profile.calibrated and msg.get('profileId')==profile.profile_id)
                                    error=None if ready else 'calibration/profile verification required before movement'
                                except Exception as e:
                                    ready,error=False,f'hardware profile unavailable or invalid: {e}'
                                self.readiness.update(ready=ready,error=error)
                                self.error=None
                                if self.on_status:self.on_status()
                            if 'remainingCommands' in msg and self.readiness.get('remainingCommands') != msg['remainingCommands']:
                                self.readiness['remainingCommands']=msg['remainingCommands']
                                if self.on_status:self.on_status()
                            if msg.get("type") == "ack" and msg.get("status") != "ACCEPTED":
                                fut = self._pending.pop(msg["msgId"], None)
                                if fut and not fut.done():
                                    fut.set_result(Ack(msg["msgId"], msg["status"], msg.get("error")))
                    finally:
                        hb.cancel()
            except Exception as e:
                self.error = f'robot transport: {type(e).__name__}: {e}'
            self.readiness.update(ready=False,error=self.error or 'robot disconnected')
            self._ws = None
            self.continuous_supported = False
            if self.on_status:self.on_status()
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_result(Ack("?", "ERROR", "connection lost"))
            self._pending.clear()
            await asyncio.sleep(1.0)

    async def _heartbeat(self, ws):
        while True:
            await ws.send(json.dumps({"type": "hb", "t": int(time.time() * 1000)}))
            await asyncio.sleep(0.25)

    def preflight(self, command_count=1):
        from ..errors import ConflictError
        if not self.connected or not self.readiness.get('ready'):
            raise ConflictError(self.readiness.get('error') or 'robot not ready')
        from ..hardware import load_profile
        try:
            profile=load_profile()
            if not profile.calibrated or profile.profile_id != self.readiness.get('profileId'):
                raise ValueError('measured hardware profile changed; rebuild/reflash and reconnect')
        except (OSError,ValueError) as e:
            self.readiness.update(ready=False,error=str(e))
            raise ConflictError(str(e))
        if self.readiness.get('remainingCommands',0) < command_count:
            raise ConflictError(f"robot command ledger has {self.readiness.get('remainingCommands',0)} slots; {command_count} required; power-cycle only while stopped")

    async def calibration(self, command):
        if not self.connected or self.readiness.get('mode') != 'calibration':
            from ..errors import ConflictError
            raise ConflictError('flash/connect the explicit robot-calibration profile first')
        return await self._exchange({'type':'calibration',**command},self.ack_timeout_s)

    async def execute(self, p: Primitive) -> Ack:
        if p.kind != 'STOP':
            try: self.preflight()
            except Exception as e: return Ack(p.msgId,'ERROR',str(e))
        if p.kind == 'MOVE':
            rad = math.radians(self.heading)
            ms = self._ms_per_cell()
            self._motion = dict(start=time.time() * 1000, dur=(ms or 0) * abs(p.value),
                                x0=self.x, y0=self.y,
                                x1=self.x + round(math.sin(rad)) * p.value,
                                y1=self.y - round(math.cos(rad)) * p.value)
        ack = await self._exchange({'type':'cmd',**p.to_dict()},self.ack_timeout_s)
        if p.kind == 'MOVE' and self._motion:
            m = self._motion
            if ack.status == 'DONE':
                self.x, self.y = m["x1"], m["y1"]          # commanded move completed
            else:
                self.x, self.y = self._current_xy()        # stopped early: best time-based guess
            self._motion = None
        elif p.kind == 'TURN' and ack.status == 'DONE':
            self.heading = (self.heading + p.value) % 360
        self._emit()
        return ack

    async def _exchange(self, message, timeout):
        msg_id=message['msgId']
        if msg_id in self._pending:
            return await asyncio.shield(self._pending[msg_id])
        if not self._ws:
            return Ack(msg_id, "ERROR", "robot not connected")
        fut = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = fut
        try:
            await self._ws.send(json.dumps(message))
            return await asyncio.wait_for(fut,timeout)
        except asyncio.TimeoutError:
            await self.stop("ack timeout")
            return Ack(msg_id, "ERROR", "ack timeout")
        except Exception as e:
            return Ack(msg_id, "ERROR", str(e))
        finally:
            self._pending.pop(msg_id, None)

    async def drive(self, action: str, amount: float, ttl_ms: int) -> dict:
        if action == "STOP":
            await self.stop("neutral input")
            return {"status":"DONE"}
        if not self._ws or not self.continuous_supported or not self.readiness.get("ready"):
            return {"status":"ERROR", "error":"continuous protocol v2 unavailable"}
        self._drive_seq += 1
        linear = amount if action == "FORWARD" else -amount if action == "BACKWARD" else 0
        angular = amount if action == "RIGHT" else -amount if action == "LEFT" else 0
        msg_id = f"drive-{time.time_ns()}"
        future = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = future
        try:
            await self._ws.send(json.dumps({"type":"drive", "protocolVersion":2,
                "msgId":msg_id, "seq":self._drive_seq,
                "linear":linear, "angular":angular, "ttlMs":min(ttl_ms,250)}))
            ack = await asyncio.wait_for(future,.2)
            return ack.__dict__
        except Exception as e:
            await self.stop("continuous ack failure")
            return {"status":"ERROR", "error":str(e)}
        finally:
            self._pending.pop(msg_id,None)

    async def stop(self, reason: str) -> None:
        if self._ws:
            try:
                await self._ws.send(json.dumps({"type": "cmd", "runId": "-", "instrIndex": -1,
                                                "msgId": f"stop-{time.time_ns()}", "kind": "STOP", "value": 0}))
            except Exception:
                # Do not block session cleanup on a dead link. Firmware watchdog/drive
                # expiry is the independent motor stop; disconnected status stays visible.
                self._ws = None
                self.continuous_supported = False
                self.readiness.update(ready=False,error="STOP transport unavailable; independent firmware watchdog remains armed")
                if self.on_status:self.on_status()

    def place(self, row: int, col: int, heading_deg: float) -> None:
        # The instructor puts the robot here by hand; the estimate restarts from this cell.
        self._motion = None
        self.x, self.y, self.heading = col + 0.5, row + 0.5, heading_deg % 360
        self._emit()
