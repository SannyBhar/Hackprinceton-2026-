"""FastAPI entry point.

Env vars:
  CA_ROBOT=sim|esp32        CA_ROBOT_URL=ws://192.168.4.1:81/   (esp32 only)
  CA_CARDS=fixture|opencv   CA_CARD_CAMERA=0
  CA_TRACKER=sim|camera     CA_TRACK_CAMERA=1
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Literal, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import StrictBool, StrictInt, BaseModel, Field

from .models import Instruction, ProjectionSettings, ProjectorCalibration, Puzzle, SessionState
from .robot.simulator import SimulatedRobot
from .session import ConflictError, InvalidError, Session
from .settings import ROOT
from .dependencies import build_session
from .runtime import running_session


session: Session


@asynccontextmanager
async def lifespan(app: FastAPI):
    global session
    session = build_session()
    async with running_session(session):
        yield


app = FastAPI(title="Greenlite", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


async def guard(fn, *a, **kw):
    try:
        r = fn(*a, **kw)
        if asyncio.iscoroutine(r):
            r = await r
        return r
    except ConflictError as e:
        raise HTTPException(409, str(e))
    except InvalidError as e:
        raise HTTPException(400, str(e))


@app.get("/api/state")
def get_state():
    return session.snapshot()


@app.get("/api/puzzles")
def list_puzzles():
    return session.storage.list_library()


@app.post("/api/puzzles")
def save_puzzle_only(p: Puzzle):
    """Save to the library without activating (allowed even while running)."""
    if p.id == session.puzzle.id:
        raise HTTPException(409, "this puzzle is active; use 'Save & use' instead")
    p = session.storage.save_puzzle(p)
    return p.model_dump(mode="json")


@app.delete("/api/puzzles/{puzzle_id}")
def delete_puzzle(puzzle_id: str):
    if puzzle_id == session.puzzle.id:
        raise HTTPException(409, "cannot delete the active puzzle; switch to another first")
    result = session.storage.delete_puzzle(puzzle_id)
    if result == "missing":
        raise HTTPException(400, "bundled example puzzles can't be deleted")
    return {"result": result}


@app.put("/api/puzzle")
async def put_puzzle(p: Puzzle):
    if session.state.value in ("RUNNING","RECORDING"):
        raise HTTPException(409,"stop before changing puzzle")
    # Reserve the persisted revision off-loop; recheck live state in set_puzzle.
    p = await asyncio.to_thread(session.storage.save_puzzle,p)
    await guard(session.set_puzzle, p)
    return session.puzzle.model_dump(mode="json")


@app.put("/api/calibration/projector")
async def put_calibration(c: ProjectorCalibration):
    await guard(session.set_calibration, c)
    return {"ok": True}


@app.put("/api/projection")
async def put_projection(ps: ProjectionSettings):
    await guard(session.set_projection, ps)
    return {"ok": True}


@app.post("/api/scan")
async def scan(image: Optional[UploadFile] = File(None)):
    data = await image.read() if image else None
    return (await guard(session.scan_async, data)).model_dump(mode="json")


class ProgramBody(BaseModel):
    instructions: list[Instruction]
    scanId: str | None = None
    reviewed: bool = False


@app.post("/api/program/confirm")
async def confirm(body: ProgramBody):
    r = await guard(session.confirm_program, body.instructions, body.scanId, body.reviewed)
    return {"ok": True, "plannedEntries": [c.model_dump() for c in r.plannedEntries]}


@app.post("/api/program/validate")
def validate(body: ProgramBody):
    from .compiler import plan
    r = plan(session.puzzle, body.instructions, session.max_steps)
    return {"ok": r.ok, "errors": r.errors, "plannedEntries": [c.model_dump() for c in r.plannedEntries]}


@app.post("/api/run")
async def run():
    await guard(session.run)
    return {"ok": True}


@app.post("/api/stop")
async def stop():
    from .models import StopReason
    await session.operational_stop(StopReason.INSTRUCTOR_STOP)
    return {"ok": True}


@app.post("/api/reset")
async def reset():
    await guard(session.reset)
    return {"ok": True}


class ToggleBody(BaseModel):
    grade: bool = False
    source: Literal["ui", "joystick"] = "ui"


@app.post("/api/recording/toggle")
async def rec_toggle(body: ToggleBody):
    await guard(session.toggle_recording, body.grade, body.source)
    return {"state": session.state.value}


class ActionBody(BaseModel):
    action: Literal["FORWARD", "BACKWARD", "LEFT", "RIGHT"]


@app.post("/api/recording/action")
async def rec_action(body: ActionBody):
    return {"accepted": await guard(session.record_action, body.action)}


class FaultBody(BaseModel):
    lateralDrift: Optional[float] = None
    trackingLossMs: Optional[int] = None
    linkUp: Optional[bool] = None


@app.post("/api/sim/fault")
async def sim_fault(body: FaultBody):
    r = session.robot
    if not isinstance(r, SimulatedRobot):
        raise HTTPException(400, "fault injection only available with the simulator")
    import time
    if body.lateralDrift is not None:
        r.lateral_drift = body.lateralDrift
    if body.trackingLossMs:
        r.tracking_lost_until = int(time.time() * 1000) + body.trackingLossMs
    if body.linkUp is not None:
        r.link_up = body.linkUp
    session.log("warn", f"simulator fault injected: {body.model_dump(exclude_none=True)}")
    session.changed()
    return {"ok": True}


# ---------------------------------------------------------------- overhead camera (markerless)
def _board_camera():
    if session.board_camera is None:
        raise HTTPException(503, "board camera service not running")
    return session.board_camera


class BoardCameraStartBody(BaseModel):
    index: int = 0


@app.post("/api/board-camera/start")
def board_camera_start(body: BoardCameraStartBody):
    try:
        import cv2  # noqa: F401
    except ImportError:
        raise HTTPException(501, "OpenCV not installed: pip install -r backend/requirements-vision.txt")
    if session.camera is not None and session.camera.role != "closed":
        # One webcam, one owner: the marker-based coordinator currently holds it.
        raise HTTPException(409, f"the shared webcam is in '{session.camera.role}' mode; close it first")
    _board_camera().start_camera(body.index)
    session.log("info", f"camera {body.index} started")
    session.changed()
    return {"ok": True}


@app.post("/api/board-camera/stop")
async def board_camera_stop():
    if session.pose_source == "camera":
        await guard(session.set_pose_source, "robot")
    _board_camera().stop_camera()
    session.log("info", "camera stopped")
    session.changed()
    return {"ok": True}


@app.get("/api/board-camera/status")
def board_camera_status():
    return _board_camera().status()


@app.get("/api/board-camera/snapshot.jpg")
async def board_camera_snapshot():
    data = await asyncio.to_thread(_board_camera().camera.jpeg, 1920, 85)
    if data is None:
        raise HTTPException(404, "no camera frame yet")
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.get("/api/board-camera/stream")
async def board_camera_stream():
    """MJPEG preview for the instructor (~12 fps, downscaled)."""
    cam = _board_camera().camera

    async def frames():
        last = -1
        while True:
            if cam.frame is not None and cam.frame_count != last:
                last = cam.frame_count
                data = await asyncio.to_thread(cam.jpeg, 960, 70)
                if data:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n"
            await asyncio.sleep(0.08)

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.post("/api/board-camera/calibrate")
async def board_camera_calibrate():
    """Show the test pattern, wait for fresh frames, find its border, then restore the board."""
    cam = _board_camera()
    if not cam.camera.running or cam.camera.frame is None:
        raise HTTPException(409, "start the camera first")
    if session.state in (SessionState.RUNNING, SessionState.RECORDING):
        raise HTTPException(409, "can't calibrate while the robot is moving")
    before = session.projection
    cam.paused = True
    try:
        session.set_projection(before.model_copy(update={"testPattern": True, "calibrating": False}))
        await asyncio.sleep(1.0)                       # projector + browser repaint
        await cam.camera.wait_new_frames(8)            # camera exposure settles on the new image
        frame = cam.camera.frame
        try:
            st = await asyncio.to_thread(cam.calibrate_from_frame, frame)
        except ValueError as e:
            raise HTTPException(400, str(e))
    finally:
        session.set_projection(before)
        cam.paused = False
    session.log("info", "camera calibrated from the projected test pattern")
    session.changed()
    return st


class PoseSourceBody(BaseModel):
    source: Literal["robot", "camera"]


@app.put("/api/pose-source")
async def pose_source(body: PoseSourceBody):
    if body.source == "camera":
        cam = _board_camera()
        if not cam.camera.running:
            raise HTTPException(409, "start the camera first")
        if cam.calibration is None:
            raise HTTPException(409, "calibrate the camera first")
    await guard(session.set_pose_source, body.source)
    return {"poseSource": session.pose_source}


@app.post("/api/manual/start")
async def manual_start():
    await guard(session.start_manual_attempt)
    return {"ok": True}


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    q: asyncio.Queue = asyncio.Queue(maxsize=512)
    session.subscribers.add(q)
    try:
        await websocket.send_json({"seq": session.seq, "type": "snapshot", "payload": session.snapshot()})
        while True:
            msg = await q.get()
            if msg is None:
                await websocket.close(code=1013)
                return
            await websocket.send_json(msg)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        session.subscribers.discard(q)


class CameraRoleBody(BaseModel):
    role: Literal["scan", "closed"]


@app.post("/api/camera/role")
async def camera_role(body: CameraRoleBody):
    if session.state.value in ("RUNNING", "RECORDING"):
        raise HTTPException(409, "stop before switching camera")
    if session.scan_busy:
        raise HTTPException(409, "scan in progress")
    if session.camera is None:
        raise HTTPException(400, "camera mode is not configured")
    if body.role != "closed" and session.board_camera is not None and session.board_camera.camera.running:
        raise HTTPException(409, "the markerless board camera is using the webcam; stop it first")
    await guard(session.reserve_device, "camera transition")
    try:
        await session.camera.switch(body.role)
        return session.camera.status()
    finally:
        session.release_device()


class HardwareCalibrationBody(BaseModel):
    action: Literal['wheel','translation','turn']
    wheel: StrictInt = Field(default=0,ge=0,le=3)
    duty: StrictInt = Field(ge=-200,le=200)
    durationMs: StrictInt = Field(default=100,ge=1,le=250)
    confirmed: StrictBool = False


@app.post('/api/hardware/calibration')
async def hardware_calibration(body: HardwareCalibrationBody):
    from .hardware import load_profile
    import uuid
    if not body.confirmed or body.duty == 0:
        raise HTTPException(400,'explicit one-shot confirmation and nonzero duty required')
    try:
        profile=load_profile()
    except (OSError,ValueError) as e:
        raise HTTPException(400,f'private hardware profile required: {e}')
    if not profile.wiringVerified or not profile.motorRatingVerified:
        raise HTTPException(409,'verify wiring, supply and motor specification before energizing outputs')
    if body.action != 'wheel' and any(p is None for p in profile.polarity):
        raise HTTPException(409,'measure and save each wheel polarity before movement trials')
    if not hasattr(session.robot,'calibration'):
        raise HTTPException(409,'calibration requires the physical robot adapter')
    await guard(session.reserve_device,'hardware calibration pulse')
    try:
        ack = await guard(session.robot.calibration, {**body.model_dump(exclude={'confirmed'}),
            'msgId':uuid.uuid4().hex,'polarity':profile.polarity})
        return ack.__dict__
    finally:
        session.release_device()


class TestMoveBody(BaseModel):
    action: Literal['FORWARD', 'BACKWARD', 'LEFT', 'RIGHT']
    confirmed: StrictBool = False


@app.post('/api/hardware/test-move')
async def hardware_test_move(body: TestMoveBody):
    """One continuous calibrated primitive for floor testing (run firmware only). No pose needed."""
    import uuid
    from .robot.base import Primitive
    if not body.confirmed:
        raise HTTPException(400, 'explicit one-shot confirmation required')
    if not hasattr(session.robot, 'calibration'):
        raise HTTPException(409, 'test moves require the physical robot adapter')
    kind, value = {'FORWARD': ('MOVE', 1), 'BACKWARD': ('MOVE', -1),
                   'LEFT': ('TURN', -90), 'RIGHT': ('TURN', 90)}[body.action]
    await guard(session.reserve_device, 'hardware test move')
    try:
        ack = await guard(session.robot.execute, Primitive('test', 0, uuid.uuid4().hex, kind, value))
        return ack.__dict__
    finally:
        session.release_device()


@app.get("/api/camera/image")
def camera_image():
    from fastapi.responses import Response
    if session.camera is None:
        raise HTTPException(400, "camera mode is not configured")
    try:
        return Response(session.camera.image(), media_type="image/jpeg", headers={"Cache-Control": "no-store"})
    except ValueError as e:
        raise HTTPException(503, str(e))


@app.delete("/api/scan")
async def clear_scan():
    if session.state.value in ("RUNNING", "RECORDING") or session.scan_busy:
        raise HTTPException(409, "stop before clearing scan")
    session.scan = None
    session.changed()
    return {"ok": True}


from .history_api import router as history_router
app.include_router(history_router(lambda: session))
from .intelligence_api import router as intelligence_router
app.include_router(intelligence_router(lambda: session))


# Serve the built frontend (npm run build) so one process runs the whole app.
DIST = ROOT / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        return FileResponse(DIST / "index.html")
