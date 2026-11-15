import asyncio
import time
import pytest
from fastapi.testclient import TestClient
from app import main
from app.models import Instruction, RobotPose, ProjectionSettings
from app.session import ConflictError, InvalidError
from app.robot.base import Primitive
from test_boundaries import make_session


@pytest.mark.parametrize('value', [True, 1.2, '2', -1])
def test_strict_distance(value):
    if value == -1:
        from app.compiler import validate_syntax
        assert validate_syntax([Instruction(op='START'), Instruction(op='FORWARD', steps=value), Instruction(op='STOP')])
    else:
        with pytest.raises(ValueError):
            Instruction(op='FORWARD', steps=value)


async def test_duplicate_inflight_only_moves_once():
    from app.robot.simulator import SimulatedRobot
    r = SimulatedRobot(speed_cells_s=30, tick_s=.005, noise=0)
    r.place(4, 0, 0)
    p = Primitive('r', 0, 'duplicate', 'MOVE', 1)
    a, b = await asyncio.gather(r.execute(p), r.execute(p))
    assert {a.status, b.status} == {'DONE', 'DUPLICATE'}
    assert r.y == pytest.approx(3.5)


async def test_start_pose_and_control_guards(tmp_path):
    s = make_session(tmp_path)
    await s.start()
    try:
        s.confirm_program([Instruction(op='START'), Instruction(op='STOP')])
        s.pose = s.pose.model_copy(update={'timestampMs': int(time.time()*1000)-2000})
        with pytest.raises(ConflictError):
            await s.run()
        with pytest.raises(ConflictError):
            await s.toggle_recording()
        s.state = s.state.__class__.RUNNING
        with pytest.raises(ConflictError):
            s.set_projection(ProjectionSettings(theme='space'))
    finally:
        await s.close()


def test_library_and_review_api(tmp_path, monkeypatch):
    s = make_session(tmp_path)
    monkeypatch.setattr(main, 'build_session', lambda: s)
    with TestClient(main.app) as c:
        library = c.get('/api/puzzles').json()
        assert all('builtin' in p and 'edited' in p for p in library)
        original = library[1]
        edited = {**original, 'name': 'custom title'}
        assert c.post('/api/puzzles', json=edited).status_code == 200
        assert c.delete('/api/puzzles/'+original['id']).json()['result'] == 'reverted'
        new = {**edited, 'id': 'my-copy'}
        assert c.post('/api/puzzles', json=new).status_code == 200
        assert c.delete('/api/puzzles/my-copy').json()['result'] == 'deleted'
        scan = c.post('/api/scan').json()
        body = {'instructions': [{'op': 'START'}, {'op': 'STOP'}]}
        assert c.post('/api/program/confirm', json=body).status_code == 400
        assert c.post('/api/program/confirm', json={**body, 'scanId': scan['scanId'], 'reviewed': True}).status_code == 200
        assert c.delete('/api/scan').status_code == 200
        assert c.post('/api/program/confirm', json=body).status_code == 200
