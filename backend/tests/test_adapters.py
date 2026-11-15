"""Adapter seams run without hardware or optional OpenCV installation."""
from contextlib import contextmanager
import sys
from types import SimpleNamespace
import pytest
from app.dependencies import build_session
from app.settings import Settings
from app.vision.camera import OpenCvCameraSource
from app.vision.cards import OpenCvCardRecognizer


def test_settings_legacy_and_precedence(tmp_path):
    cfg = Settings.from_env({'CA_ROBOT': 'esp32', 'CA_DATA_DIR': str(tmp_path),
                             'GRASSROOT_ROBOT': 'sim', 'CA_CARDS': 'fixture'})
    s = build_session(cfg)
    assert s.robot.name == 'simulator'
    assert s.recognizer.name == 'fixture'
    assert s.storage.dir == tmp_path
    assert Settings.from_env({'CA_ROBOT': 'esp32'}).robot == 'esp32'
    assert Settings.from_env({}).track_camera == 1


def test_camera_releases_on_consumer_failure(monkeypatch):
    released = []
    cap = SimpleNamespace(release=lambda: released.append(True))
    monkeypatch.setitem(sys.modules, 'cv2', SimpleNamespace(VideoCapture=lambda index: cap))
    with pytest.raises(RuntimeError):
        with OpenCvCameraSource().open(0, 'scan') as reader:
            assert reader is cap
            raise RuntimeError('processing failed')
    assert released == [True]


def test_card_capture_uses_injected_source_and_five_frames(monkeypatch):
    reads, roles = [], []
    @contextmanager
    def open_camera(index, role):
        roles.append((index, role))
        yield SimpleNamespace(read=lambda: (reads.append(True) is None, 'frame'))
    monkeypatch.setitem(sys.modules, 'cv2', SimpleNamespace(
        imencode=lambda ext, frame: (True, SimpleNamespace(tobytes=lambda: b'png'))))
    reader = OpenCvCardRecognizer(camera=SimpleNamespace(open=open_camera))
    assert reader._grab() == b'png'
    assert len(reads) == 5 and roles == [(0, 'scan')]


async def test_runtime_owns_board_camera_and_session_shutdown(tmp_path, monkeypatch):
    import asyncio
    from app import runtime
    from app.settings import Settings
    s = build_session(Settings(data_dir=tmp_path))
    closed, stopped = [], []
    async def run():
        try:
            await asyncio.Event().wait()
        finally:
            closed.append(True)
    def build(session, settings):
        session.board_camera = SimpleNamespace(run=run, stop_camera=lambda: stopped.append(True),
                                               status=lambda: {})
        return session.board_camera
    monkeypatch.setattr(runtime, 'build_board_camera', build)
    async with runtime.running_session(s):
        await asyncio.sleep(0)
        assert s.pose is not None
    assert closed == [True] and stopped == [True]   # tracking loop cancelled, webcam released
    assert all(t.done() for t in s._bg)
    assert s.robot._idle_task.cancelled()


async def test_dead_transport_stop_does_not_break_cleanup():
    from app.robot.esp32_ws import Esp32WebSocketRobot
    class Dead:
        async def send(self,*args):raise OSError('connection closed')
    r=Esp32WebSocketRobot('ws://unused');r._ws=Dead();r.continuous_supported=True
    await r.stop('operator stop')
    assert not r.connected and not r.continuous_supported
