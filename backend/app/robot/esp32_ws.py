"""ESP32 WebSocket transport (UNVERIFIED against hardware).

Wire protocol (JSON text frames), matching firmware/esp32/codeanywhere/codeanywhere.ino:
  laptop -> robot  {"type":"cmd","runId","instrIndex","msgId","kind":"MOVE|TURN|STOP","value"}
  laptop -> robot  {"type":"hb","t":<ms>}                     every 250 ms
  robot  -> laptop {"type":"ack","msgId","status":"ACCEPTED|DONE|STOPPED|DUPLICATE|ERROR","error"?}
Firmware stops motors if no heartbeat for 1000 ms and bounds every command's duration.
Pose does NOT come from the robot; it comes from the overhead camera tracker.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Optional

from .base import Ack, PoseCallback, Primitive


class Esp32WebSocketRobot:
    name = "esp32"

    def __init__(self, url: str, ack_timeout_s: float = 15.0):
        self.url = url
        self.ack_timeout_s = ack_timeout_s
        self.on_pose: Optional[PoseCallback] = None  # camera supplies pose
        self._ws = None
        self._pending: dict[str, asyncio.Future] = {}
        self._tasks: list[asyncio.Task] = []

    @property
    def connected(self) -> bool:
        return self._ws is not None

    async def start(self) -> None:
        self._tasks.append(asyncio.create_task(self._connect_loop()))

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
                            if msg.get("type") == "ack" and msg.get("status") != "ACCEPTED":
                                fut = self._pending.pop(msg["msgId"], None)
                                if fut and not fut.done():
                                    fut.set_result(Ack(msg["msgId"], msg["status"], msg.get("error")))
                    finally:
                        hb.cancel()
            except Exception:
                pass
            self._ws = None
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_result(Ack("?", "ERROR", "connection lost"))
            self._pending.clear()
            await asyncio.sleep(1.0)

    async def _heartbeat(self, ws):
        while True:
            await ws.send(json.dumps({"type": "hb", "t": int(time.time() * 1000)}))
            await asyncio.sleep(0.25)

    async def execute(self, p: Primitive) -> Ack:
        if not self._ws:
            return Ack(p.msgId, "ERROR", "robot not connected")
        fut = asyncio.get_running_loop().create_future()
        self._pending[p.msgId] = fut
        await self._ws.send(json.dumps({"type": "cmd", **p.to_dict()}))
        try:
            return await asyncio.wait_for(fut, self.ack_timeout_s)
        except asyncio.TimeoutError:
            await self.stop("ack timeout")
            return Ack(p.msgId, "ERROR", "ack timeout")

    async def stop(self, reason: str) -> None:
        if self._ws:
            await self._ws.send(json.dumps({"type": "cmd", "runId": "-", "instrIndex": -1,
                                            "msgId": f"stop-{time.time_ns()}", "kind": "STOP", "value": 0}))

    def place(self, row: int, col: int, heading_deg: float) -> None:
        pass  # physical robot is placed by hand
