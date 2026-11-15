"""Authoritative session state machine. Instructor and projection clients only render this."""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Optional

from .compiler import DEFAULT_MAX_STEPS, PlanResult, plan
from .grading import Grader, reduce_tile, summarize
from .models import (HEADING_DEG, Cell, Corner, Instruction, ProjectionSettings,
                     ProjectorCalibration, Puzzle, RobotPose, ScanResult, SessionState,
                     StopReason)
from .recording import RecordedAction, generate_program
from .robot.base import Primitive, RobotAdapter
from .repository import Repository
from .tracking import CellEntryDetector, TrackerConfig
from .vision.cards import CardRecognizer

S = SessionState


class ConflictError(Exception):
    """Action not allowed in the current session state (HTTP 409)."""


class InvalidError(Exception):
    """Request content invalid (HTTP 400)."""


def now_ms() -> int:
    return int(time.time() * 1000)


def default_calibration() -> ProjectorCalibration:
    return ProjectorCalibration(
        corners=[Corner(x=0.1, y=0.1), Corner(x=0.9, y=0.1), Corner(x=0.9, y=0.9), Corner(x=0.1, y=0.9)],
        viewportWidth=1920, viewportHeight=1080)


class Session:
    def __init__(self, robot: RobotAdapter, recognizer: CardRecognizer, storage: Repository,
                 tracker_cfg: TrackerConfig | None = None, tile_policy: str = "first_latest",
                 max_steps: int = DEFAULT_MAX_STEPS):
        self.robot = robot
        self.recognizer = recognizer
        self.storage = storage
        self.tracker_cfg = tracker_cfg or TrackerConfig()
        self.tile_policy = tile_policy
        self.max_steps = max_steps

        self.state: SessionState = S.IDLE
        puzzles = storage.list_puzzles()
        self.puzzle: Puzzle = puzzles[0]
        self.calibration = storage.load_calibration() or default_calibration()
        self.projection = ProjectionSettings()
        self.scan: Optional[ScanResult] = None
        self.program: Optional[list[Instruction]] = None
        self.plan: Optional[PlanResult] = None
        self.attempt: Optional[dict] = None
        self.attempt_history: list[dict] = []
        self.grader: Optional[Grader] = None
        self.tile_history: dict[str, list[bool]] = {}
        self.pose: Optional[RobotPose] = None
        self.detector: Optional[CellEntryDetector] = None
        self.feed: list[dict] = []
        self.recording: dict[str, Any] = {"actions": [], "generated": None, "warnings": [], "path": []}
        self._rec_current: Optional[RecordedAction] = None
        self._rec_lock = asyncio.Lock()
        self._last_toggle = 0
        self._bg: list[asyncio.Task] = []
        self._run_task: Optional[asyncio.Task] = None
        self._stop_reason: Optional[StopReason] = None

        self.seq = 0
        self.subscribers: set[asyncio.Queue] = set()
        self.robot.on_pose = self.on_pose

    # ------------------------------------------------------------------ plumbing
    async def start(self):
        await self.robot.start()
        self.robot.place(self.puzzle.startCell.row, self.puzzle.startCell.col,
                         HEADING_DEG[self.puzzle.startHeading])
        self._bg = [asyncio.create_task(self._watchdog())]

    async def close(self):
        tasks = self._bg + ([self._run_task] if self._run_task else [])
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if hasattr(self.robot, "close"):
            await self.robot.close()

    def _publish(self, type_: str, payload: Any):
        self.seq += 1
        msg = {"seq": self.seq, "type": type_, "payload": payload}
        for q in list(self.subscribers):
            if q.qsize() > 500:  # slow client: drop it, it will reconnect and resnapshot
                self.subscribers.discard(q)
            else:
                q.put_nowait(msg)

    def changed(self):
        self._publish("snapshot", self.snapshot())

    def log(self, level: str, msg: str):
        self.feed.append({"t": now_ms(), "level": level, "msg": msg})
        self.feed = self.feed[-60:]

    def snapshot(self) -> dict:
        tiles = {k: reduce_tile(h, self.tile_policy).to_dict() for k, h in self.tile_history.items()}
        return {
            "seq": self.seq,
            "state": self.state.value,
            "puzzle": self.puzzle.model_dump(mode="json"),
            "calibration": self.calibration.model_dump(mode="json"),
            "projection": self.projection.model_dump(mode="json"),
            "scan": self.scan.model_dump(mode="json") if self.scan else None,
            "program": [i.model_dump(mode="json") for i in self.program] if self.program else None,
            "plannedEntries": [c.model_dump() for c in self.plan.plannedEntries] if self.plan else [],
            "attempt": self.attempt,
            "attemptHistory": [{k: a[k] for k in ("id", "startedAt", "stopReason", "summary")}
                               for a in self.attempt_history[-10:]],
            "tiles": tiles,
            "pose": self.pose.model_dump() if self.pose else None,
            "robot": {"adapter": self.robot.name, "connected": self.robot.connected},
            "recording": self.recording,
            "feed": self.feed[-25:],
            "tilePolicy": self.tile_policy,
            "maxSteps": self.max_steps,
        }

    def _require(self, *states: SessionState, action: str):
        if self.state not in states:
            raise ConflictError(f"cannot {action} while {self.state.value}")

    # ------------------------------------------------------------------ puzzle / calibration
    def set_puzzle(self, p: Puzzle):
        self._require(S.IDLE, S.SCANNING, S.PROGRAM_READY, S.COMPLETED, S.STOPPED, S.FAULT,
                      action="change puzzle")
        if p.id == self.puzzle.id and p != self.puzzle:
            p = p.model_copy(update={"version": max(p.version, self.puzzle.version + 1)})
        self.puzzle = p
        self.storage.save_puzzle(p)
        self._clear_feedback()
        if self.program:
            self.plan = plan(p, self.program, self.max_steps)
            if not self.plan.ok:
                self.program, self.plan = None, None
                self.log("warn", "confirmed program no longer fits the edited puzzle; rescan")
        self.state = S.PROGRAM_READY if self.program else S.IDLE
        self._place_at_start()
        self.log("info", f"puzzle '{p.name}' v{p.version} loaded")
        self.changed()

    def set_calibration(self, c: ProjectorCalibration):
        self._require(S.IDLE, S.SCANNING, S.PROGRAM_READY, S.COMPLETED, S.STOPPED, S.FAULT,
                      action="calibrate (motors must be stopped)")
        self.calibration = c
        self.storage.save_calibration(c)
        self.changed()

    def set_projection(self, ps: ProjectionSettings):
        self.projection = ps  # display-only toggles; allowed any time
        self.changed()

    # ------------------------------------------------------------------ scanning / program
    def do_scan(self, image: Optional[bytes] = None) -> ScanResult:
        self._require(S.IDLE, S.SCANNING, S.PROGRAM_READY, S.COMPLETED, S.STOPPED,
                      action="scan cards")
        self.state = S.SCANNING
        try:
            self.scan = self.recognizer.scan(image)
        except Exception as e:  # camera unplugged etc.
            self.scan = ScanResult(scanId="err", source=self.recognizer.name, cards=[],
                                   errors=[f"scan failed: {e}"])
        self.log("info", f"scan {self.scan.scanId}: {len(self.scan.cards)} card(s) from {self.scan.source}")
        self.changed()
        return self.scan

    def confirm_program(self, program: list[Instruction]) -> PlanResult:
        self._require(S.IDLE, S.SCANNING, S.PROGRAM_READY, S.COMPLETED, S.STOPPED,
                      action="confirm a program")
        result = plan(self.puzzle, program, self.max_steps)
        if not result.ok:
            raise InvalidError("; ".join(result.errors))
        self.program = [i.model_copy() for i in program]
        self.plan = result
        self.state = S.PROGRAM_READY
        self.log("info", f"program confirmed ({len(program)} cards)")
        self.changed()
        return result

    # ------------------------------------------------------------------ execution
    def _clear_feedback(self):
        self.tile_history = {}
        self.grader = None
        self.attempt = None

    def _place_at_start(self):
        self.robot.place(self.puzzle.startCell.row, self.puzzle.startCell.col,
                         HEADING_DEG[self.puzzle.startHeading])

    def _check_start_pose(self):
        p = self.pose
        if p is None or not p.trackingValid:
            raise ConflictError("robot pose not observed; cannot confirm start position")
        cell = Cell(row=int(p.y), col=int(p.x))
        if cell != self.puzzle.startCell:
            raise ConflictError(f"robot is at {cell.key()}, not at start {self.puzzle.startCell.key()}")
        diff = abs((p.headingDeg - HEADING_DEG[self.puzzle.startHeading] + 180) % 360 - 180)
        if diff > 30:
            raise ConflictError(f"robot heading {p.headingDeg:.0f}° does not match start heading "
                                f"{self.puzzle.startHeading}")

    async def run(self):
        self._require(S.PROGRAM_READY, action="run")
        if not self.program:
            raise ConflictError("no confirmed program")
        self._check_start_pose()
        attempt_id = uuid.uuid4().hex[:10]
        self._clear_feedback()
        self.grader = Grader(attempt_id, self.puzzle.targetEntries)
        self.detector = CellEntryDetector(self.puzzle.rows, self.puzzle.cols,
                                          self.puzzle.startCell, self.tracker_cfg)
        self.detector.last_valid_ms = now_ms()  # arm the stale watchdog from Run time
        self.attempt = {
            "id": attempt_id, "startedAt": now_ms(), "puzzleId": self.puzzle.id,
            "puzzleVersion": self.puzzle.version,
            "program": [i.model_dump(mode="json") for i in self.program],  # frozen copy
            "instructionIndex": -1, "events": [], "warnings": [], "stopReason": None,
            "summary": None,
        }
        self._stop_reason = None
        self.state = S.RUNNING
        self.log("info", f"run {attempt_id} started")
        self.changed()
        self._run_task = asyncio.create_task(self._execute(attempt_id, list(self.program)))

    async def _execute(self, run_id: str, program: list[Instruction]):
        try:
            for i, ins in enumerate(program):
                if self._stop_reason:
                    break
                self.attempt["instructionIndex"] = i
                self.changed()
                if ins.op in ("START",):
                    continue
                if ins.op == "STOP":
                    break
                if ins.op in ("FORWARD", "BACKWARD"):
                    prim = Primitive(run_id, i, uuid.uuid4().hex, "MOVE",
                                     ins.steps if ins.op == "FORWARD" else -ins.steps)
                else:
                    prim = Primitive(run_id, i, uuid.uuid4().hex, "TURN", 90 if ins.op == "RIGHT" else -90)
                ack = await self.robot.execute(prim)
                if ack.status == "ERROR":
                    self._stop_reason = self._stop_reason or (
                        StopReason.CONNECTION_LOST if not self.robot.connected else StopReason.ROBOT_FAULT)
                    self.log("error", f"robot error on card {i + 1}: {ack.error}")
                    break
                if ack.status == "STOPPED":
                    break
            await asyncio.sleep(0.4)  # let the final pose settle into the last cell
        finally:
            self._finish(self._stop_reason or StopReason.PROGRAM_COMPLETE)

    def _finish(self, reason: StopReason):
        if self.state != S.RUNNING or not self.attempt:
            return
        self.attempt["stopReason"] = reason.value
        normal = reason == StopReason.PROGRAM_COMPLETE
        s = summarize(self.puzzle.targetEntries, self.grader.events, self.puzzle.goalCell, normal)
        self.attempt["summary"] = s.__dict__
        self.attempt["endedAt"] = now_ms()
        self.state = (S.COMPLETED if normal else
                      S.FAULT if reason in (StopReason.ROBOT_FAULT, StopReason.CONNECTION_LOST) else
                      S.STOPPED)
        self.attempt_history.append(dict(self.attempt))
        try:
            self.storage.save_attempt(self.attempt["id"], self.attempt)
        except OSError as e:
            self.log("warn", f"could not save attempt: {e}")
        self.log("info" if normal else "warn",
                 f"run ended: {reason.value}{' — SUCCESS' if s.success else ''}")
        self.changed()

    async def operational_stop(self, reason: StopReason):
        if self.state == S.RUNNING:
            if self._stop_reason is None:
                self._stop_reason = reason
                self.log("warn" if reason != StopReason.INSTRUCTOR_STOP else "info",
                         f"operational stop: {reason.value}")
            await self.robot.stop(reason.value)
        elif self.state == S.RECORDING:
            await self.robot.stop(reason.value)
            if reason != StopReason.INSTRUCTOR_STOP:
                self.log("warn", f"recording halted: {reason.value}")
            await self._end_recording()

    async def reset(self):
        self._require(S.IDLE, S.SCANNING, S.PROGRAM_READY, S.COMPLETED, S.STOPPED, S.FAULT,
                      action="reset")
        self._clear_feedback()
        self.state = S.PROGRAM_READY if self.program else S.IDLE
        self._place_at_start()
        self.log("info", "attempt reset")
        self.changed()

    # ------------------------------------------------------------------ pose ingestion
    def on_pose(self, pose: RobotPose):
        self.pose = pose
        if self.detector and self.state in (S.RUNNING, S.RECORDING):
            out = self.detector.update(pose)
            for w in out.warnings:
                self.log("warn", w)
                if self.attempt:
                    self.attempt["warnings"].append(w)
            if out.entered:
                self._on_entry(out.entered, pose.timestampMs)
            if out.boundary:
                asyncio.get_event_loop().create_task(self.operational_stop(StopReason.BOUNDARY))
        self._publish("pose", pose.model_dump())

    def _on_entry(self, cell: Cell, ts: int):
        if self.state == S.RECORDING:
            self.recording["path"].append(cell.model_dump())
            if self._rec_current is not None:
                self._rec_current.observedEntries.append(cell)
            else:
                self.recording["warnings"].append(f"cell {cell.key()} entered between actions (drift?)")
        if self.grader is not None:
            ev = self.grader.on_entry(cell, ts)
            self.tile_history.setdefault(cell.key(), []).append(ev.correct)
            if self.attempt:
                self.attempt["events"].append(ev.model_dump(mode="json"))
            self.changed()

    async def _watchdog(self):
        while True:
            await asyncio.sleep(0.1)
            if self.state not in (S.RUNNING, S.RECORDING):
                continue
            if not self.robot.connected:
                await self.operational_stop(StopReason.CONNECTION_LOST)
            elif self.detector and self.detector.is_stale(now_ms()):
                await self.operational_stop(StopReason.TRACKING_LOST)

    # ------------------------------------------------------------------ recording
    async def toggle_recording(self, grade: bool = False, source: str = "ui"):
        t = now_ms()
        if source == "joystick" and t - self._last_toggle < 600:
            return  # debounce physical button bounce
        self._last_toggle = t
        if self.state == S.RECORDING:
            await self.robot.stop("recording ended")
            await self._end_recording()
            return
        self._require(S.IDLE, S.PROGRAM_READY, S.COMPLETED, S.STOPPED, action="start recording")
        self._clear_feedback()
        p = self.pose
        start = (Cell(row=int(p.y), col=int(p.x)) if p and p.trackingValid else self.puzzle.startCell)
        self.detector = CellEntryDetector(self.puzzle.rows, self.puzzle.cols, start, self.tracker_cfg)
        self.detector.last_valid_ms = t
        if grade:
            self.grader = Grader("rec-" + uuid.uuid4().hex[:6], self.puzzle.targetEntries)
        self.recording = {"actions": [], "generated": None, "warnings": [], "path": [],
                          "startCell": start.model_dump(), "graded": grade, "startedAt": t}
        self.state = S.RECORDING
        self.log("info", "recording started")
        self.changed()

    async def record_action(self, action: str) -> bool:
        self._require(S.RECORDING, action="drive")
        if self._rec_lock.locked():
            return False  # serialized: ignore input while a move is in progress
        async with self._rec_lock:
            rec = RecordedAction(action)  # type: ignore[arg-type]
            self._rec_current = rec
            kind, val = {"FORWARD": ("MOVE", 1), "BACKWARD": ("MOVE", -1),
                         "LEFT": ("TURN", -90), "RIGHT": ("TURN", 90)}[action]
            ack = await self.robot.execute(Primitive("rec", len(self.recording["actions"]),
                                                     uuid.uuid4().hex, kind, val))
            await asyncio.sleep(0.25)
            self._rec_current = None
            if ack.status == "DONE" and self.state == S.RECORDING:
                self.recording["actions"].append({"action": action,
                                                  "observedEntries": [c.model_dump() for c in rec.observedEntries]})
                self.changed()
                return True
            return False

    async def _end_recording(self):
        if self.state != S.RECORDING:
            return
        async with self._rec_lock:
            pass  # wait for an in-flight action to finish/stop
        if self.state != S.RECORDING:
            return  # another stop already ended it
        actions = [RecordedAction(a["action"], [Cell(**c) for c in a["observedEntries"]])
                   for a in self.recording["actions"]]
        gen = generate_program(actions, self.max_steps)
        self.recording["generated"] = [i.model_dump(mode="json") for i in gen.instructions]
        self.recording["warnings"] += gen.warnings
        self.state = S.IDLE if not self.program else S.PROGRAM_READY
        self.log("info", f"recording ended: {len(actions)} action(s) -> {len(gen.instructions)} blocks")
        self.changed()
