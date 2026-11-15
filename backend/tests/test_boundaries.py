"""Characterization of boundaries touched by the structural refactor."""
import json
from fastapi.testclient import TestClient
from app import main
from app.models import Instruction, StopReason
from app.robot.simulator import SimulatedRobot
from app.session import Session
from app.storage import FIXTURES, Storage
from app.vision.cards import FixtureCardRecognizer


def make_session(tmp_path):
    return Session(SimulatedRobot(noise=0), FixtureCardRecognizer(FIXTURES / 'scans'), Storage(tmp_path))


def test_http_and_reconnect_contract(tmp_path, monkeypatch):
    s = make_session(tmp_path)
    monkeypatch.setattr(main, 'build_session', lambda: s)
    with TestClient(main.app) as client:
        snap = client.get('/api/state').json()
        assert snap['state'] == 'IDLE'
        assert client.post('/api/run').status_code == 409
        program = {'instructions': [{'op': 'START'}, {'op': 'STOP'}]}
        assert client.post('/api/program/validate', json=program).json() == {'ok': True, 'errors': [], 'plannedEntries': []}
        assert client.post('/api/program/confirm', json=program).json() == {'ok': True, 'plannedEntries': []}
        for _ in range(2):
            with client.websocket_connect('/ws') as ws:
                msg = ws.receive_json()
                assert msg['type'] == 'snapshot'
                assert msg['seq'] == msg['payload']['seq']
                assert msg['payload']['attempt'] is None
                assert msg['payload']['state'] == 'PROGRAM_READY'
                client.put('/api/projection', json={**snap['projection'], 'theme': 'space'})
                update = ws.receive_json()
                while update['type'] != 'snapshot':
                    update = ws.receive_json()
                assert update['seq'] > msg['seq']
                assert update['payload']['projection']['theme'] == 'space'


async def test_explicit_stop_remains_operational(tmp_path):
    s = make_session(tmp_path)
    await s.start()
    try:
        s.confirm_program([Instruction(op='START'), Instruction(op='FORWARD', steps=2), Instruction(op='STOP')])
        await s.run()
        await s.operational_stop(StopReason.INSTRUCTOR_STOP)
        await s._run_task
        assert s.attempt['stopReason'] == 'INSTRUCTOR_STOP'
        assert not s.attempt['summary']['success']
    finally:
        await s.close()


def test_json_storage_representation(tmp_path):
    store = Storage(tmp_path)
    p = store.list_puzzles()[0]
    store.save_puzzle(p)
    store.save_attempt('example', {'events': [], 'puzzleVersion': p.version})
    assert json.loads((tmp_path / 'puzzles' / f'{p.id}.json').read_text()) == p.model_dump(mode='json')
    assert json.loads((tmp_path / 'attempts/example.json').read_text()) == {'events': [], 'puzzleVersion': p.version}
    assert store.list_puzzles()[0] == p
