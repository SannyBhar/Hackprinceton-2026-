"""Authoritative session state machine. Instructor and projection clients only render this."""
from __future__ import annotations

import asyncio
import time
import uuid
import math
import copy
from typing import Any, Optional

from .errors import ConflictError, InvalidError
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
        saved = storage.get_record("settings", "session") or {}
        self.puzzle = next((p for p in puzzles if p.id == saved.get("activePuzzleId")), puzzles[0])
        self.student_id = saved.get("studentId")
        self.projection = ProjectionSettings.model_validate(saved.get("projection", {}))
        self.scan: Optional[ScanResult] = None
        self.program: Optional[list[Instruction]] = None
        self.plan: Optional[PlanResult] = None
        self.attempt: Optional[dict] = None
        self.attempt_history: list[dict] = storage.list_attempts()
        self.grader: Optional[Grader] = None
        self.tile_history: dict[str, list[bool]] = {}
        self.pose: Optional[RobotPose] = None
        self.detector: Optional[CellEntryDetector] = None
        self.feed: list[dict] = []
        self.recording: dict[str, Any] = {"actions": [], "generated": None, "warnings": [], "path": []}
        self.recording_grade = False
        self._rec_current: Optional[RecordedAction] = None
        self._rec_lock = asyncio.Lock()
        self._last_toggle = 0
        self._bg: list[asyncio.Task] = []
        self._run_task: Optional[asyncio.Task] = None
        self._stop_reason: Optional[StopReason] = None

        from .joystick import ContinuousRecorder
        self.joystick = ContinuousRecorder(self)
        self._validated_artwork = None
        self.themes = None
        self.camera = None
        self.scan_busy = False
        self.device_operation = None
        self.session_id = uuid.uuid4().hex
        self._io_tasks: set[asyncio.Task] = set()
        self._writer_lock = asyncio.Lock()
        self.seq = 0
        self.subscribers: set[asyncio.Queue] = set()
        self.robot.on_pose = self.on_pose
        if hasattr(self.robot,"on_status"):
            self.robot.on_status = self.changed

    # ------------------------------------------------------------------ plumbing
    async def start(self):
        await self.robot.start()
        self.robot.place(self.puzzle.startCell.row, self.puzzle.startCell.col,
                         HEADING_DEG[self.puzzle.startHeading])
        self._bg = [asyncio.create_task(self._watchdog())]

    async def close(self):
        await self.robot.stop("application shutdown")
        tasks = self._bg + ([self._run_task] if self._run_task else [])
        if self.joystick._neutral_task and not self.joystick._neutral_task.done():
            tasks.append(self.joystick._neutral_task)
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if self._io_tasks:
            await asyncio.gather(*self._io_tasks, return_exceptions=True)
        if hasattr(self.robot, "close"):
            await self.robot.close()

    def _publish(self, type_: str, payload: Any):
        self.seq += 1
        if type_ == "snapshot":
            payload = {**payload, "seq":self.seq}
        msg = {"sessionId":self.session_id, "runId":self.attempt["id"] if self.attempt else None,
               "seq": self.seq, "type": type_, "payload": payload}
        for q in list(self.subscribers):
            if q.qsize() > 500:  # slow client: drop it, it will reconnect and resnapshot
                self.subscribers.discard(q)
                while not q.empty(): q.get_nowait()
                q.put_nowait(None)
            else:
                q.put_nowait(msg)

    def persist(self, method, *args):
        frozen = copy.deepcopy(args)
        async def write():
            async with self._writer_lock:
                try:
                    await asyncio.to_thread(method, *frozen)
                except Exception as e:
                    self.log("warn", f"persistence failed: {e}")
                    self.changed()
        task = asyncio.create_task(write())
        self._io_tasks.add(task)
        task.add_done_callback(self._io_tasks.discard)

    def select_student(self, student_id):
        if self.state in (S.RUNNING, S.RECORDING):
            raise ConflictError("stop before changing student")
        if student_id and not self.storage.get_record("students", student_id):
            raise InvalidError("student does not exist")
        self.student_id = student_id
        self._save_settings()
        self.changed()

    def _save_settings(self):
        self.persist(self.storage.put_record, "settings", "session", {
            "activePuzzleId": self.puzzle.id, "studentId": self.student_id, "projection": self.projection.model_dump(mode="json")})

    def changed(self):
        self._publish("snapshot", self.snapshot())

    def log(self, level: str, msg: str):
        self.feed.append({"t": now_ms(), "level": level, "msg": msg})
        self.feed = self.feed[-60:]

    def snapshot(self) -> dict:
        tiles = {k: reduce_tile(h, self.tile_policy).to_dict() for k, h in self.tile_history.items()}
        return {
            "studentId": self.student_id,
            "sessionId": self.session_id,
            "joystick": self.joystick.status(),
            "deviceOperation": self.device_operation,
            "camera": self.camera.status() if self.camera else None,
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
            "robot": {"adapter": self.robot.name, "connected": self.robot.connected,
                      "continuousSupported": getattr(self.robot, "continuous_supported", False),
                      "readiness": getattr(self.robot, "readiness", {"ready": True, "mode": "simulator"})},
            "recording": self.recording,
            "feed": self.feed[-25:],
            "tilePolicy": self.tile_policy,
            "maxSteps": self.max_steps,
        }

    def reserve_device(self, operation):
        self._require(S.IDLE, S.SCANNING, S.PROGRAM_READY, S.COMPLETED, S.STOPPED, S.FAULT, action=operation)
        if self.scan_busy:
            raise ConflictError("scan in progress")
        self.device_operation = operation
        self.changed()

    def release_device(self):
        self.device_operation = None
        self.changed()

    def _require(self, *states: SessionState, action: str):
        if self.device_operation:
            raise ConflictError(f"cannot {action}: {self.device_operation} pending")
        if self.state not in states:
            raise ConflictError(f"cannot {action} while {self.state.value}")

    # ------------------------------------------------------------------ puzzle / calibration
    def set_puzzle(self, p: Puzzle):
        self._require(S.IDLE, S.SCANNING, S.PROGRAM_READY, S.COMPLETED, S.STOPPED, S.FAULT,
                      action="change puzzle")
        if p.id == self.puzzle.id and p != self.puzzle:
            p = p.model_copy(update={"version": max(p.version, self.puzzle.version + 1)})
        if self.camera and (p.rows, p.cols) != (self.puzzle.rows, self.puzzle.cols):
            self.camera.invalidate()
        self.puzzle = p
        if self.projection.artworkId:
            from .models import puzzle_hash
            if self.projection.artworkHash != puzzle_hash(p):
                self.projection = self.projection.model_copy(update={"artworkId":None,"artworkHash":None})
        self._save_settings()
        self.persist(self.storage.save_puzzle, p)
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
        self.persist(self.storage.save_calibration, c)
        self.changed()

    def set_projection(self, ps: ProjectionSettings):
        if self.state in (S.RUNNING, S.RECORDING) and (ps.theme != self.projection.theme or ps.artworkId != self.projection.artworkId or ps.calibrating or ps.testPattern != self.projection.testPattern):
            raise ConflictError("theme and calibration changes require stopped motors")
        if ps.artworkId and ps.artworkId != self.projection.artworkId:
            if self._validated_artwork != (ps.artworkId, ps.artworkHash):
                raise InvalidError("use the artwork acceptance endpoint")
        elif ps.artworkId:
            ps = ps.model_copy(update={"artworkHash":self.projection.artworkHash})
        self.projection = ps
        self._save_settings()
        self.changed()

    # ------------------------------------------------------------------ scanning / program
    async def scan_async(self, image: Optional[bytes] = None) -> ScanResult:
        self._require(S.IDLE, S.SCANNING, S.PROGRAM_READY, S.COMPLETED, S.STOPPED, action="scan")
        if self.scan_busy:
            raise ConflictError("scan already in progress")
        self.scan_busy = True
        self.state = S.SCANNING
        self.program, self.plan = None, None
        self.changed()
        try:
            if self.camera:
                if self.camera.role != "scan":
                    raise ConflictError("switch camera to scan role first")
                image = image or self.camera.image()
            result = await asyncio.to_thread(self.recognizer.scan, image)
            self.scan = result
            return result
        except ConflictError:
            raise
        except Exception as e:
            self.scan = ScanResult(scanId=uuid.uuid4().hex, source=self.recognizer.name, cards=[], errors=[str(e)])
            return self.scan
        finally:
            self.scan_busy = False
            self.changed()

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

    def confirm_program(self, program: list[Instruction], scan_id: str | None = None, reviewed: bool = False) -> PlanResult:
        self._require(S.IDLE, S.SCANNING, S.PROGRAM_READY, S.COMPLETED, S.STOPPED,
                      action="confirm a program")
        if self.scan_busy:
            raise ConflictError("wait for scan to finish")
        if self.scan is not None:
            if scan_id != self.scan.scanId or not reviewed:
                raise InvalidError("review the current scan and confirm its scanId")
            if not self.scan.cards or self.scan.errors:
                raise InvalidError("scan is invalid; rescan or explicitly clear it for manual programming")
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
        if self.scan_busy:
            raise ConflictError("scan is in progress")
        if self.camera and not self.camera.ready():
            raise ConflictError("arena camera calibration and tracking must be ready")
        if p is None or not p.trackingValid or not 0 <= now_ms() - p.timestampMs <= self.tracker_cfg.stale_ms:
            raise ConflictError("robot pose not observed; cannot confirm start position")
        cell = Cell(row=math.floor(p.y), col=math.floor(p.x))
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
        if hasattr(self.robot, 'preflight'):
            self.robot.preflight(sum(i.op not in ('START','STOP') for i in self.program))
        attempt_id = uuid.uuid4().hex[:10]
        self._clear_feedback()
        self.grader = Grader(attempt_id, self.puzzle.targetEntries)
        self.detector = CellEntryDetector(self.puzzle.rows, self.puzzle.cols,
                                          self.puzzle.startCell, self.tracker_cfg)
        self.detector.last_valid_ms = now_ms()  # arm the stale watchdog from Run time
        self.attempt = {
            "id": attempt_id, "source": self.robot.name, "studentId": self.student_id, "startedAt": now_ms(), "puzzleId": self.puzzle.id,
            "puzzleSnapshot": self.puzzle.model_dump(mode="json"), "commands": [],
            "scanReview": self.scan.model_dump(mode="json") if self.scan else None,
            "puzzleVersion": self.puzzle.version,
            "program": [i.model_dump(mode="json") for i in self.program],  # frozen copy
            "instructionIndex": -1, "events": [], "warnings": [], "stopReason": None,
            "summary": None,
        }
        self._stop_reason = None
        self.state = S.RUNNING
        self.log("info", f"run {attempt_id} started")
        self.changed()
        self.persist(self.storage.save_attempt, attempt_id, self.attempt)
        self._run_task = asyncio.create_task(self._execute(attempt_id, copy.deepcopy(self.program)))

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
                requested = now_ms()
                ack = await self.robot.execute(prim)
                self.attempt["commands"].append({"command": prim.to_dict(), "ack": ack.__dict__, "requestedAt": requested, "acknowledgedAt": now_ms()})
                self.persist(self.storage.save_attempt, self.attempt["id"], self.attempt)
                if ack.status == "ERROR":
                    self._stop_reason = self._stop_reason or (
                        StopReason.CONNECTION_LOST if not self.robot.connected else StopReason.ROBOT_FAULT)
                    self.log("error", f"robot error on card {i + 1}: {ack.error}")
                    break
                if ack.status == "STOPPED":
                    if self._stop_reason is None:
                        self._stop_reason = StopReason.ROBOT_FAULT
                        self.log("error", f"device stopped on card {i + 1}: {ack.error or 'unexplained stop'}")
                    break
            await asyncio.sleep(0.4)  # let the final pose settle into the last cell
        except asyncio.CancelledError:
            self._stop_reason = self._stop_reason or StopReason.INSTRUCTOR_STOP
            raise
        except Exception as e:
            self._stop_reason = self._stop_reason or StopReason.ROBOT_FAULT
            self.log("error", f"execution fault: {e}")
            await self.robot.stop("execution fault")
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
        self.persist(self.storage.save_attempt, self.attempt["id"], self.attempt)
        self.log("info" if normal else "warn",
                 f"run ended: {reason.value}{' — SUCCESS' if s.success else ''}")
        self.changed()

    async def operational_stop(self, reason: StopReason):
        if self.joystick.active:
            await self.joystick.end(reason.value)
            return
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
        else:
            # Calibration/device transitions may hold ownership while session is idle.
            await self.robot.stop(reason.value)

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
        if self.pose and pose.timestampMs < self.pose.timestampMs:
            return  # never ingest an older observation after a newer one
        self.joystick.observe(pose)
        self.pose = pose
        if self.detector and self.state in (S.RUNNING, S.RECORDING):
            out = self.detector.update(pose)
            for w in out.warnings:
                self.log("warn", w)
                if self.attempt:
                    self.attempt["warnings"].append(w)
            if out.skipped:
                asyncio.create_task(self.operational_stop(StopReason.TRACKING_UNCERTAIN))
            elif out.entered:
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
            if self.joystick.active:
                await self.joystick.end("instructor recording stop")
                return
            await self.robot.stop("recording ended")
            await self._end_recording()
            return
        self._require(S.IDLE, S.PROGRAM_READY, S.COMPLETED, S.STOPPED, action="start recording")
        self._check_start_pose()
        if hasattr(self.robot, 'preflight'):
            self.robot.preflight(1)
        self._clear_feedback()
        p = self.pose
        start = (Cell(row=math.floor(p.y), col=math.floor(p.x)) if p and p.trackingValid else self.puzzle.startCell)
        self.detector = CellEntryDetector(self.puzzle.rows, self.puzzle.cols, start, self.tracker_cfg)
        self.detector.last_valid_ms = t
        if grade:
            self.grader = Grader("rec-" + uuid.uuid4().hex[:6], self.puzzle.targetEntries)
        self.recording = {"actions": [], "generated": None, "warnings": [], "path": [],
                          "id": uuid.uuid4().hex, "studentId": self.student_id,
                          "startHeading": self.puzzle.startHeading, "startCell": start.model_dump(), "graded": grade, "startedAt": t}
        self.state = S.RECORDING
        self.log("info", "recording started")
        self.changed()

    async def record_action(self, action: str) -> bool:
        self._require(S.RECORDING, action="drive")
        if self.joystick.active:
            raise ConflictError("continuous input owns the control lease")
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
        if self.grader:
            self.recording["visitEvents"] = [e.model_dump(mode="json") for e in self.grader.events]
            self.recording["summary"] = summarize(self.puzzle.targetEntries,self.grader.events,self.puzzle.goalCell,True).__dict__
        self.recording["endedAt"] = now_ms()
        self.persist(self.storage.put_record, "recordings", self.recording["id"], self.recording)
        self.state = S.IDLE if not self.program else S.PROGRAM_READY
        self.log("info", f"recording ended: {len(actions)} action(s) -> {len(gen.instructions)} blocks")
        self.changed()
