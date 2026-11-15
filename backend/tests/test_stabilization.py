"""Regression coverage for hardware stabilization; no physical acceptance claimed."""
import asyncio
import json
import time
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from app import main
from app.ai.themes import ThemeJobs
from app.hardware import HardwareProfile
from app.joystick import JoystickSample
from app.models import Instruction, SessionState, StopReason
from app.robot.base import Ack, Primitive
from app.robot.esp32_ws import Esp32WebSocketRobot
from app.session import ConflictError
from test_boundaries import make_session


async def test_unexplained_stopped_ack_is_operational_fault(tmp_path):
    s=make_session(tmp_path)
    await s.start()
    try:
        s.robot.execute=AsyncMock(return_value=Ack('x','STOPPED'))
        s.confirm_program([Instruction(op='START'),Instruction(op='FORWARD',steps=1),Instruction(op='STOP')])
        await s.run(); await s._run_task
        assert s.attempt['stopReason']=='ROBOT_FAULT'
        assert s.state==SessionState.FAULT
        assert not s.attempt['summary']['success']
    finally: await s.close()


async def test_stop_ack_preserves_latched_instructor_reason(tmp_path):
    s=make_session(tmp_path);await s.start()
    try:
        async def execute(p):
            s._stop_reason=StopReason.INSTRUCTOR_STOP
            return Ack(p.msgId,'STOPPED')
        s.robot.execute=execute
        s.confirm_program([Instruction(op='START'),Instruction(op='FORWARD',steps=1),Instruction(op='STOP')])
        await s.run();await s._run_task
        assert s.attempt['stopReason']=='INSTRUCTOR_STOP'
    finally:await s.close()


async def test_camera_reserves_before_await_and_stop_bypasses(tmp_path,monkeypatch):
    s=make_session(tmp_path);await s.start()
    entered,release=asyncio.Event(),asyncio.Event()
    class Camera:
        async def switch(self,role):entered.set();await release.wait()
        def status(self):return {'role':'scan'}
    s.camera=Camera();monkeypatch.setattr(main,'session',s,raising=False)
    task=asyncio.create_task(main.camera_role(main.CameraRoleBody(role='scan')))
    try:
        await entered.wait()
        assert s.snapshot()['deviceOperation']=='camera transition'
        with pytest.raises(ConflictError):await s.run()
        with pytest.raises(ConflictError):await s.toggle_recording()
        with pytest.raises(ConflictError):s.set_puzzle(s.puzzle)
        with pytest.raises(ConflictError):s.reserve_device('another operation')
        await asyncio.wait_for(s.operational_stop(StopReason.INSTRUCTOR_STOP),.1)
        release.set();await task
        assert s.device_operation is None
    finally:release.set();await asyncio.gather(task,return_exceptions=True);await s.close()


async def test_camera_failed_transition_releases_owner(tmp_path,monkeypatch):
    s=make_session(tmp_path)
    s.camera=type('Camera',(),{'switch':AsyncMock(side_effect=ValueError('camera gone')),'status':lambda self:{}})()
    monkeypatch.setattr(main,'session',s,raising=False)
    with pytest.raises(ValueError):await main.camera_role(main.CameraRoleBody(role='scan'))
    assert s.device_operation is None


async def test_live_joystick_snapshot_not_settings(tmp_path):
    s=make_session(tmp_path)
    s.joystick.connected=True;s.joystick.error='sample error'
    assert s.snapshot()['joystick']['connected']
    assert s.snapshot()['joystick']['error']=='sample error'
    s._save_settings();await asyncio.gather(*s._io_tasks)
    assert 'joystick' not in s.storage.get_record('settings','session')


def serial_sample(j,seq=0,button=False,x=0,y=0,**extra):
    elapsed=int(time.monotonic()*1000-j.sync_sent)
    return JoystickSample(protocolVersion=2,bootId='boot-a',syncId=j.sync_id,
        syncTimestampMs=1000,seq=seq,timestampMs=1000+elapsed+seq,x=x,y=y,button=button,**extra)


def test_serial_age_replay_boot_identity_and_neutral_rearm(tmp_path):
    j=make_session(tmp_path).joystick;j.reset_connection()
    j.ingest(serial_sample(j,button=True,y=-.5));assert not j.armed
    j.ingest(serial_sample(j,seq=1));assert j.armed
    with pytest.raises(ValueError,match='replayed'):j.ingest(serial_sample(j,seq=1))
    with pytest.raises(ValueError,match='rebooted'):j.ingest(serial_sample(j,seq=2).model_copy(update={'bootId':'boot-b'}))
    j.sync_sent-=1000
    with pytest.raises(ValueError,match='delayed'):j.ingest(serial_sample(j,seq=2).model_copy(update={'timestampMs':1002}))
    old=j.sync_id;j.reset_connection()
    j.ingest(serial_sample(j).model_copy(update={'syncId':old}));assert not j.connected
    with pytest.raises(ValueError,match='firmware v2'):j.ingest(JoystickSample(seq=0,timestampMs=0,x=0,y=0))
    j.ingest(serial_sample(j,button=True));assert not j.armed
    j.ingest(serial_sample(j,seq=1));assert j.armed


async def test_physical_samples_cannot_bypass_serial_sync(tmp_path):
    s=make_session(tmp_path);s.robot.name='esp32'
    with pytest.raises(ValueError,match='protocol v2'):
        await s.joystick.sample(JoystickSample(seq=0,timestampMs=0,x=0,y=0))


async def test_serial_acquisition_keeps_latest_axes_and_all_button_edges(tmp_path):
    s=make_session(tmp_path);await s.start();j=s.joystick;j.reset_connection()
    try:
        j.ingest(serial_sample(j))
        j.ingest(serial_sample(j,seq=1,button=True))
        j.ingest(serial_sample(j,seq=2))
        j.ingest(serial_sample(j,seq=3,button=True))
        assert len(j.edges)==3
        consumer=asyncio.create_task(j.consume())
        for _ in range(20):
            if not j.edges and s.recording.get('stopReason'):break
            await asyncio.sleep(.01)
        assert s.recording['stopReason']=='button stop'
        assert not j.active
        consumer.cancel();await asyncio.gather(consumer,return_exceptions=True)
        j.reset_connection();j.ingest(serial_sample(j))
        for seq in range(1,10):j.ingest(serial_sample(j,seq=seq,y=-.5))
        assert j.latest[0].seq==9 and not j.edges
        j.edge_limit=1
        j.ingest(serial_sample(j,seq=10,button=True))
        with pytest.raises(ValueError,match='overflow'):j.ingest(serial_sample(j,seq=11))
    finally:await s.close()


async def test_acquisition_does_not_wait_for_drive_ack(tmp_path):
    s=make_session(tmp_path);await s.start();j=s.joystick;j.reset_connection()
    gate,entered=asyncio.Event(),asyncio.Event()
    async def drive(*args):entered.set();await gate.wait();return {'status':'DONE'}
    s.robot.drive=drive
    try:
        j.ingest(serial_sample(j));j.ingest(serial_sample(j,seq=1,button=True))
        consumer=asyncio.create_task(j.consume());await asyncio.sleep(.02)
        j.ingest(serial_sample(j,seq=2,y=-.5));await entered.wait()
        for seq in range(3,9):j.ingest(serial_sample(j,seq=seq,y=-.3))
        j.ingest(serial_sample(j,seq=9,button=True))
        assert j.latest[0].seq==9 and len(j.edges)>=1
        gate.set();await asyncio.sleep(.05)
        assert not j.active
        consumer.cancel();await asyncio.gather(consumer,return_exceptions=True)
    finally:gate.set();await s.close()


async def test_atomic_theme_limit_and_completed_handle_cleanup(tmp_path):
    s=make_session(tmp_path)
    class Slow:
        async def generate(self,*args):await asyncio.sleep(100)
    jobs=ThemeJobs(s,tmp_path,Slow())
    results=await asyncio.gather(*(jobs.create(str(i)) for i in range(3)),return_exceptions=True)
    assert sum(isinstance(r,ValueError) for r in results)==1
    assert len(jobs.tasks)==2
    await jobs.close();await asyncio.sleep(0)
    assert not jobs.tasks


async def test_theme_cancel_before_coroutine_starts_is_persisted(tmp_path):
    s=make_session(tmp_path);jobs=ThemeJobs(s,tmp_path)
    job=await jobs.create('cancel immediately');await jobs.cancel(job['id'])
    assert s.storage.get_record('theme_assets',job['id'])['status']=='CANCELLED'


def test_profile_never_guesses_calibration():
    profile=HardwareProfile()
    assert not profile.calibrated and profile.msPerCell is None
    for invalid in ([1,1,0,1],[True,1,1,1]):
        with pytest.raises(ValueError):HardwareProfile(polarity=invalid)
    with pytest.raises(ValueError):HardwareProfile(msPerCell=1.5)


async def test_readiness_and_ledger_block_unready_motion(tmp_path,monkeypatch):
    robot=Esp32WebSocketRobot('ws://unused')
    robot._ws=object()
    with pytest.raises(ConflictError):robot.preflight(1)
    ack=await robot.execute(Primitive('r',0,'id','MOVE',1))
    assert ack.status=='ERROR'
    profile=HardwareProfile(wiringVerified=True,motorRatingVerified=True,acknowledged=True,
        polarity=[1,1,1,1],msPerCell=100,msPer90=100,driveDuty=20,turnDuty=20)
    path=tmp_path/'hardware.local.json';path.write_text(profile.model_dump_json())
    monkeypatch.setenv('GRASSROOT_HARDWARE_PROFILE',str(path))
    robot.readiness={'ready':True,'remainingCommands':2,'profileId':profile.profile_id}
    robot.preflight(2)
    with pytest.raises(ConflictError,match='slots'):robot.preflight(3)
    path.write_text(HardwareProfile().model_dump_json())
    with pytest.raises(ConflictError,match='changed'):robot.preflight(1)


async def test_calibration_gates_and_duration_bounds(tmp_path,monkeypatch):
    s=make_session(tmp_path);monkeypatch.setattr(main,'session',s,raising=False)
    profile=tmp_path/'hardware.local.json';profile.write_text(HardwareProfile().model_dump_json())
    monkeypatch.setenv('GRASSROOT_HARDWARE_PROFILE',str(profile))
    for invalid in (0,251,1.2,True):
        with pytest.raises(ValueError):main.HardwareCalibrationBody(action='wheel',duty=20,durationMs=invalid)
    body=main.HardwareCalibrationBody(action='wheel',duty=20,confirmed=True)
    assert body.durationMs==100
    with pytest.raises(HTTPException,match=''):await main.hardware_calibration(body)
    profile.write_text(HardwareProfile(wiringVerified=True,motorRatingVerified=True).model_dump_json())
    with pytest.raises(HTTPException) as exc:
        await main.hardware_calibration(body.model_copy(update={'action':'translation'}))
    assert 'polarity' in exc.value.detail or 'polarities' in exc.value.detail
    s.robot.calibration=AsyncMock(return_value=Ack('pulse','DONE'))
    result=await main.hardware_calibration(body)
    assert result['status']=='DONE'
    command=s.robot.calibration.call_args.args[0]
    assert command['durationMs']==100
    assert s.device_operation is None


async def test_stop_preempts_idle_calibration_owner(tmp_path):
    s=make_session(tmp_path);s.robot.stop=AsyncMock()
    s.reserve_device('hardware calibration pulse')
    await asyncio.wait_for(s.operational_stop(StopReason.INSTRUCTOR_STOP),.1)
    s.robot.stop.assert_awaited_once_with('INSTRUCTOR_STOP')
    assert s.device_operation=='hardware calibration pulse'


async def test_neutral_preempts_pending_drive_ack(tmp_path):
    s=make_session(tmp_path);j=s.joystick;j.reset_connection()
    s.robot.stop=AsyncMock()
    j.ingest(serial_sample(j));j.active=True
    j.ingest(serial_sample(j,seq=1,y=-.5));j.ingest(serial_sample(j,seq=2))
    await asyncio.sleep(0)
    s.robot.stop.assert_awaited_once_with('neutral input')


def test_run_build_rejects_unmeasured_and_accepts_explicit_compile_fixture(tmp_path,monkeypatch):
    import runpy
    class Env:
        def __init__(self):self.defines=[]
        def GetProjectOption(self,key,default):return 'run'
        def __getitem__(self,key):return str(tmp_path/'firmware')
        def Append(self,**kw):self.defines=kw['CPPDEFINES']
    path=tmp_path/'hardware.local.json';monkeypatch.setenv('GRASSROOT_HARDWARE_PROFILE',str(path))
    profile=HardwareProfile();path.write_text(profile.model_dump_json());env=Env()
    globals={'Import':lambda name:None,'env':env}
    with pytest.raises(ValueError,match='verification|verified'):
        runpy.run_path('../firmware/hardware_profile.py',init_globals=globals)
    # Compile-only fixture numbers, NOT measurements or an uploadable profile.
    profile=HardwareProfile(wiringVerified=True,motorRatingVerified=True,acknowledged=True,
        polarity=[1,-1,1,-1],msPerCell=100,msPer90=100,driveDuty=20,turnDuty=20)
    path.write_text(profile.model_dump_json())
    runpy.run_path('../firmware/hardware_profile.py',init_globals=globals)
    assert ('GRASSROOT_HARDWARE_MODE',2) in env.defines
    assert any(k=='PROFILE_ID' and profile.profile_id in str(v) for k,v in env.defines)


@pytest.mark.parametrize('outputs,calibrated,matching,expected',[(False,False,True,False),(True,False,True,False),(True,True,False,False),(True,True,True,True)])
async def test_firmware_hello_distinguishes_connection_from_readiness(tmp_path,monkeypatch,outputs,calibrated,matching,expected):
    import websockets
    profile=HardwareProfile(wiringVerified=True,motorRatingVerified=True,acknowledged=True,
        polarity=[1,1,1,1],msPerCell=100,msPer90=100,driveDuty=20,turnDuty=20)
    path=tmp_path/'hardware.local.json';path.write_text(profile.model_dump_json())
    monkeypatch.setenv('GRASSROOT_HARDWARE_PROFILE',str(path))
    wait=asyncio.Event()
    class Socket:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):return False
        async def send(self,raw):assert json.loads(raw)['type']=='hb'
        async def close(self):pass
        async def __aiter__(self):
            yield json.dumps(dict(type='hello',protocolVersion=2,outputsEnabled=outputs,calibrated=calibrated,
                mode='run' if calibrated else 'disabled',remainingCommands=128,
                profileId=profile.profile_id if matching else 'different-profile'))
            await wait.wait()
    monkeypatch.setattr(websockets,'connect',lambda *args,**kwargs:Socket())
    robot=Esp32WebSocketRobot('ws://test');updates=[];robot.on_status=lambda:updates.append(robot.readiness.copy())
    await robot.start()
    try:
        for _ in range(20):
            if updates:break
            await asyncio.sleep(.01)
        assert robot.connected and robot.readiness['ready'] is expected
        assert robot.readiness['remainingCommands']==128
    finally:await robot.close()


async def test_serial_overflow_stops_and_flushes_reconnect_input(tmp_path,monkeypatch):
    import sys
    from types import SimpleNamespace
    s=make_session(tmp_path);await s.start();await s.toggle_recording();j=s.joystick;j.active=True;j.edge_limit=0
    s.robot.stop=AsyncMock()
    events=[]
    class Device:
        count=0
        def reset_input_buffer(self):events.append('flush')
        def write(self,raw):events.append(json.loads(raw))
        def readline(self):
            sample=serial_sample(j,seq=self.count,button=self.count>0)
            self.count+=1
            return sample.model_dump_json().encode()+b'\n'
        def close(self):events.append('close')
    monkeypatch.setitem(sys.modules,'serial',SimpleNamespace(Serial=lambda *args,**kw:Device()))
    task=asyncio.create_task(j.serial_loop('fake-port'))
    try:
        for _ in range(100):
            if j.error and 'overflow' in j.error:break
            await asyncio.sleep(.01)
        assert 'overflow' in j.error
        assert not j.active and not j.armed and not j.connected
        s.robot.stop.assert_awaited()
        assert events[0]=='flush' and events[1]['protocolVersion']==2
    finally:
        task.cancel();await asyncio.gather(task,return_exceptions=True);await s.close()
    assert 'close' in events


def test_local_ocr_reports_uncalibrated_candidate_and_review(monkeypatch):
    import sys
    from contextlib import nullcontext
    from types import SimpleNamespace
    from app.vision.ocr import LocalHandwritingOcr
    from app.vision.cards import finalize
    from app.models import ScannedCard
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(inference_mode=nullcontext))
    monkeypatch.setitem(sys.modules,'transformers',SimpleNamespace(TrOCRProcessor=None,VisionEncoderDecoderModel=None))
    monkeypatch.setitem(sys.modules,'PIL',SimpleNamespace(Image=SimpleNamespace(fromarray=lambda crop:SimpleNamespace(convert=lambda mode:crop))))
    class Processor:
        def __call__(self,**kw):return SimpleNamespace(pixel_values='fixture-pixels')
        def batch_decode(self,*args,**kw):return ['3']
    reader=LocalHandwritingOcr();reader._processor=Processor();reader._model=SimpleNamespace(generate=lambda *a,**kw:'fixture-output')
    number,confidence=reader(object())
    assert number==3 and confidence is None
    result=finalize([ScannedCard(order=0,cardId=20,op='FORWARD',rawSteps=number,stepsConfidence=confidence)],'opencv')
    assert result.needsReview and any('uncalibrated' in issue for issue in result.cards[0].issues)
