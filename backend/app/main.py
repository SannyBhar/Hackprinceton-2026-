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
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .models import Instruction, ProjectionSettings, ProjectorCalibration, Puzzle
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


app = FastAPI(title="Grassroot", lifespan=lifespan)
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
    st = session.storage
    return [{**p.model_dump(mode="json"), "builtin": st.is_builtin(p.id),
             "edited": (st.dir / "puzzles" / f"{p.id}.json").exists()}
            for p in st.list_puzzles()]


@app.post("/api/puzzles")
def save_puzzle_only(p: Puzzle):
    """Save to the library without activating (allowed even while running)."""
    if p.id == session.puzzle.id:
        raise HTTPException(409, "this puzzle is active; use 'Save & use' instead")
    session.storage.save_puzzle(p)
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
    await guard(session.set_puzzle, p)
    return session.puzzle.model_dump(mode="json")


@app.put("/api/calibration/projector")
async def put_calibration(c: ProjectorCalibration):
    await guard(session.set_calibration, c)
    return {"ok": True}


@app.put("/api/projection")
def put_projection(ps: ProjectionSettings):
    session.set_projection(ps)
    return {"ok": True}


@app.post("/api/scan")
async def scan(image: Optional[UploadFile] = File(None)):
    data = await image.read() if image else None
    return (await guard(session.do_scan, data)).model_dump(mode="json")


class ProgramBody(BaseModel):
    instructions: list[Instruction]


@app.post("/api/program/confirm")
async def confirm(body: ProgramBody):
    r = await guard(session.confirm_program, body.instructions)
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
def sim_fault(body: FaultBody):
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


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    q: asyncio.Queue = asyncio.Queue()
    session.subscribers.add(q)
    try:
        await websocket.send_json({"seq": session.seq, "type": "snapshot", "payload": session.snapshot()})
        while True:
            msg = await q.get()
            await websocket.send_json(msg)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        session.subscribers.discard(q)


# Serve the built frontend (npm run build) so one process runs the whole app.
DIST = ROOT / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        return FileResponse(DIST / "index.html")
