import asyncio
import json
import time
import pytest
from app.sqlite_store import SQLiteStorage
from app.storage import Storage
from app.models import Instruction, RobotPose
from app.joystick import direction, reconstruct, JoystickSample
from test_boundaries import make_session


def test_sqlite_import_idempotent_and_library_revert(tmp_path):
    legacy=Storage(tmp_path); p=legacy.list_puzzles()[0]
    legacy.save_puzzle(p.model_copy(update={'name':'Edited'}))
    legacy.save_attempt('old',{'id':'old','startedAt':1,'program':[],'events':[]})
    store=SQLiteStorage(tmp_path)
    assert store.list_puzzles()[0].name=='Edited'
    assert store.list_attempts()[0]['stopReason']=='INTERRUPTED'
    assert store.delete_puzzle(p.id)=='reverted'
    assert store.list_puzzles()[0].name==p.name
    again=SQLiteStorage(tmp_path)
    assert len(again.list_attempts())==1
    assert len(again.import_report['skipped'])==2
    assert (tmp_path/'puzzles'/f'{p.id}.json').exists()


def test_sqlite_attempt_evidence_and_records(tmp_path):
    store=SQLiteStorage(tmp_path)
    r={'id':'a','startedAt':1,'endedAt':2,'events':[{'index':0,'correct':True}], 'commands':[{'ack':'DONE'}]}
    store.save_attempt('a',r);store.save_attempt('a',r)
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM visit_events').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM command_events').fetchone()[0]==1
    store.put_record('students','s',{'id':'s','name':'Learner','synthetic':False})
    assert SQLiteStorage(tmp_path).get_record('students','s')['name']=='Learner'


def test_dominant_axis_and_invalid_input():
    assert direction(.1,-.1)==('STOP',0.)
    assert direction(.3,-.9)==('FORWARD',.9)
    assert direction(-.9,.2)==('LEFT',.9)
    with pytest.raises(ValueError):JoystickSample(seq=1,timestampMs=0,x=float('nan'),y=0)


def test_reverse_reconstruction_intent_and_uncertainty(tmp_path):
    s=make_session(tmp_path)
    pose=lambda y,h=0:dict(timestampMs=0,x=.5,y=y,headingDeg=h,trackingValid=True)
    result=reconstruct(s.puzzle,[{'action':'BACKWARD','poses':[pose(2.5),pose(3.5)]},
                                 {'action':'RIGHT','poses':[pose(3.5),pose(3.5,90)]}])
    assert [(i['op'],i['steps']) for i in result['generated']]==[('START',None),('BACKWARD',1),('RIGHT',None),('STOP',None)]
    uncertain=reconstruct(s.puzzle,[{'action':'FORWARD','poses':[pose(4.5),pose(4.2)]}])
    assert uncertain['approximate'] and uncertain['warnings']


async def test_continuous_input_release_and_stale_stop(tmp_path):
    s=make_session(tmp_path); await s.start()
    try:
        t=int(time.time()*1000)
        await s.joystick.sample(JoystickSample(seq=0,timestampMs=t,x=0,y=0,button=True))
        assert s.joystick.active
        await s.joystick.sample(JoystickSample(seq=1,timestampMs=t+50,x=0,y=-.4))
        await asyncio.sleep(.05)
        await s.joystick.sample(JoystickSample(seq=2,timestampMs=t+100,x=0,y=0))
        y=s.robot.y;await asyncio.sleep(.05)
        assert s.robot.y==pytest.approx(y)
        s.joystick.last_received=int(time.monotonic()*1000)-1000
        watch=asyncio.create_task(s.joystick.watchdog())
        await asyncio.sleep(.1);watch.cancel();await asyncio.gather(watch,return_exceptions=True)
        assert not s.joystick.active and s.recording['stopReason']=='stale joystick input'
        assert s.recording['approximate']
    finally:await s.close()


def test_library_edits_allocate_distinct_immutable_versions(tmp_path):
    store=SQLiteStorage(tmp_path)
    original=store.list_puzzles()[0]
    one=store.save_puzzle(original.model_copy(update={'name':'first edit'}))
    two=store.save_puzzle(original.model_copy(update={'name':'second edit'}))
    assert two.version>one.version>original.version
    assert store.save_puzzle(two).version==two.version
    with store.connect() as db:
        first=db.execute('SELECT body FROM puzzle_versions WHERE id=? AND version=?',(one.id,one.version)).fetchone()[0]
    assert json.loads(first)['name']=='first edit'
