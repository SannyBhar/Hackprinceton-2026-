"""Simulated robot + simulated overhead camera.

Emits continuous poses (cell units) so the real CellEntryDetector, bounds
monitor, and grader are exercised exactly as with hardware. Fault injection
hooks let you rehearse boundary, drift and tracking-loss stops.
"""
from __future__ import annotations

import asyncio
import math
import random
import time
from typing import Optional

from ..models import RobotPose
from .base import Ack, PoseCallback, Primitive


def now_ms() -> int:
    return int(time.time() * 1000)


class SimulatedRobot:
    name = "simulator"

    def __init__(self, speed_cells_s: float = 1.2, turn_deg_s: float = 180.0,
                 tick_s: float = 1 / 30, noise: float = 0.01):
        self.speed = speed_cells_s
        self.turn_rate = turn_deg_s
        self.tick = tick_s
        self.noise = noise
        self.x, self.y, self.heading = 0.5, 0.5, 0.0
        self.on_pose: Optional[PoseCallback] = None
        self._stop = asyncio.Event()
        self._done: dict[str, Ack] = {}
        self._lock = asyncio.Lock()
        self._idle_task: Optional[asyncio.Task] = None
        # fault injection
        self.lateral_drift = 0.0          # cells per cell travelled, sideways
        self.tracking_lost_until = 0
        self.link_up = True

    @property
    def connected(self) -> bool:
        return self.link_up

    async def start(self) -> None:
        if self._idle_task is None:
            self._idle_task = asyncio.create_task(self._idle_loop())

    async def _idle_loop(self):
        while True:  # the camera keeps seeing the robot while it is parked
            if not self._lock.locked():
                self._emit()
            await asyncio.sleep(0.1)

    async def close(self):
        if self._idle_task:
            self._idle_task.cancel()
            await asyncio.gather(self._idle_task, return_exceptions=True)

    def place(self, row: int, col: int, heading_deg: float) -> None:
        self.x, self.y, self.heading = col + 0.5, row + 0.5, heading_deg % 360
        self._emit()

    def _emit(self):
        if self.on_pose is None:
            return
        valid = now_ms() >= self.tracking_lost_until
        n = self.noise
        self.on_pose(RobotPose(
            timestampMs=now_ms(),
            x=self.x + random.gauss(0, n), y=self.y + random.gauss(0, n),
            headingDeg=(self.heading + random.gauss(0, n * 50)) % 360,
            trackingValid=valid,
        ))

    async def execute(self, p: Primitive) -> Ack:
        if p.msgId in self._done:
            return Ack(p.msgId, "DUPLICATE")
        if not self.link_up:
            return Ack(p.msgId, "ERROR", "link down")
        async with self._lock:
            if p.msgId in self._done:
                return Ack(p.msgId, "DUPLICATE")
            self._stop.clear()
            status = "DONE"
            if p.kind == "MOVE":
                status = await self._move(p.value)
            elif p.kind == "TURN":
                status = await self._turn(p.value)
            ack = Ack(p.msgId, status)
            self._done[p.msgId] = ack
            return ack

    async def _move(self, cells: int) -> str:
        rad = math.radians(self.heading)
        fx, fy = math.sin(rad), -math.cos(rad)   # 0deg = N = -y
        sx, sy = -fy, fx                         # lateral (right-hand) vector
        sign = 1 if cells > 0 else -1
        dist = abs(cells)
        travelled = 0.0
        step = self.speed * self.tick
        while travelled < dist - 1e-9:
            if self._stop.is_set():
                return "STOPPED"
            d = min(step, dist - travelled)
            self.x += sign * fx * d + sx * self.lateral_drift * d
            self.y += sign * fy * d + sy * self.lateral_drift * d
            travelled += d
            self._emit()
            await asyncio.sleep(self.tick)
        return "DONE"

    async def _turn(self, deg: int) -> str:
        sign = 1 if deg > 0 else -1
        remaining = abs(deg)
        step = self.turn_rate * self.tick
        while remaining > 1e-9:
            if self._stop.is_set():
                return "STOPPED"
            d = min(step, remaining)
            self.heading = (self.heading + sign * d) % 360
            remaining -= d
            self._emit()
            await asyncio.sleep(self.tick)
        return "DONE"

    async def stop(self, reason: str) -> None:
        self._stop.set()
