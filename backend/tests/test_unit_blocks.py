"""Physical unit blocks: supplied SVG patterns, repeated IDs, ordering and no OCR."""
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest
from app.models import Instruction
from app.session import InvalidError
from app.vision.cards import OpenCvCardRecognizer, op_for_marker
from test_boundaries import make_session

ROOT=Path(__file__).resolve().parents[2]


def render_svg(path,side=180):
    np=pytest.importorskip('numpy')
    root=ET.fromstring(path.read_text())
    assert root.attrib['width']==root.attrib['height']=='2in'
    image=np.zeros((side,side),np.uint8)
    for rect in root:
        x,y,w,h=[float(rect.get(k,'0')) for k in ('x','y','width','height')]
        scale=side/6
        image[round(y*scale):round((y+h)*scale),round(x*scale):round((x+w)*scale)]=255 if rect.get('fill')=='white' else 0
    return image


@pytest.mark.parametrize('mid,op',[(0,'FORWARD'),(1,'BACKWARD'),(2,'RIGHT'),(3,'LEFT')])
@pytest.mark.parametrize('rotation',[0,1,2,3])
def test_supplied_svg_decodes_in_all_rotations(mid,op,rotation):
    cv2=pytest.importorskip('cv2');np=pytest.importorskip('numpy')
    marker=render_svg(ROOT/'assets'/'markers'/f'4x4_1000-{mid}.svg')
    expected=cv2.aruco.generateImageMarker(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_1000),mid,180)
    assert np.array_equal(marker,expected)
    frame=np.full((240,240),255,np.uint8);frame[30:210,30:210]=np.rot90(marker,rotation)
    reader=OpenCvCardRecognizer(ocr=lambda crop:pytest.fail('unit blocks must never invoke OCR'))
    result=reader.scan(cv2.imencode('.png',frame)[1].tobytes())
    assert result.unitBlocks and result.needsReview and not result.errors
    assert [(c.cardId,c.op) for c in result.cards]==[(mid,op)]
    assert result.cards[0].rawSteps==(1 if mid in (0,1) else None)
    assert result.cards[0].cropDataUrl is None and not result.cards[0].issues


def test_repeated_same_id_is_multiple_blocks_in_spatial_order():
    cv2=pytest.importorskip('cv2');np=pytest.importorskip('numpy')
    ids=[0,0,2,1,1,3]
    frame=np.full((240,30+len(ids)*210),255,np.uint8)
    for index,mid in enumerate(ids):frame[30:210,30+index*210:210+index*210]=render_svg(ROOT/'assets'/'markers'/f'4x4_1000-{mid}.svg')
    result=OpenCvCardRecognizer().scan(cv2.imencode('.png',frame)[1].tobytes())
    assert [c.cardId for c in result.cards]==ids
    assert [c.op for c in result.cards]==['FORWARD','FORWARD','RIGHT','BACKWARD','BACKWARD','LEFT']
    assert all(not c.issues for c in result.cards)
    assert [c.order for c in result.cards]==list(range(6))


def test_new_ids_do_not_silently_treat_legacy_numeric_cards_as_unit_blocks():
    assert op_for_marker(20) is None
    assert op_for_marker(10)=='START' and op_for_marker(80)=='STOP'


def test_empty_corrupt_and_unknown_scan_is_explicit():
    cv2=pytest.importorskip('cv2');np=pytest.importorskip('numpy')
    reader=OpenCvCardRecognizer()
    with pytest.raises(ValueError,match='decoded'):reader.scan(b'not an image')
    frame=np.full((240,240),255,np.uint8)
    result=reader.scan(cv2.imencode('.png',frame)[1].tobytes())
    assert result.errors and not result.cards
    frame[30:210,30:210]=cv2.aruco.generateImageMarker(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_1000),777,180)
    result=reader.scan(cv2.imencode('.png',frame)[1].tobytes())
    assert result.cards[0].op is None and result.cards[0].issues


async def test_unit_scan_review_and_server_side_single_cell_gate(tmp_path):
    s=make_session(tmp_path);await s.start()
    try:
        scan=s.do_scan()
        assert scan.unitBlocks and any(c.cardId==0 for c in scan.cards)
        program=[Instruction(op='START'),Instruction(op='FORWARD',steps=2),Instruction(op='STOP')]
        with pytest.raises(InvalidError,match='review'):s.confirm_program(program)
        with pytest.raises(InvalidError,match='one cell'):s.confirm_program(program,scan.scanId,True)
        program=[Instruction(op='START'),Instruction(op='FORWARD',steps=1),Instruction(op='FORWARD',steps=1),Instruction(op='STOP')]
        assert s.confirm_program(program,scan.scanId,True).ok
        assert len(s.program)==4
    finally:await s.close()


def test_print_generator_keeps_exact_size_and_supplied_patterns(tmp_path):
    import runpy
    module=runpy.run_path(str(ROOT/'tools'/'make_cards.py'))
    sheet=module['generate'](tmp_path)
    assert 'width:2in;height:2in' in sheet.read_text()
    for mid,op in [(0,'FORWARD'),(1,'BACKWARD'),(2,'RIGHT'),(3,'LEFT')]:
        assert (tmp_path/f'card_{op}_{mid}.svg').read_bytes()==(ROOT/'assets'/'markers'/f'4x4_1000-{mid}.svg').read_bytes()
    assert (tmp_path/'card_START_10.svg').is_file() and (tmp_path/'card_STOP_80.svg').is_file()
    assert not list(tmp_path.glob('marker_*'))


async def test_repeated_fixture_blocks_execute_and_grade_in_order(tmp_path):
    import asyncio
    from app.robot.simulator import SimulatedRobot
    from app.session import Session
    from app.storage import Storage,FIXTURES
    from app.vision.cards import FixtureCardRecognizer
    s=Session(SimulatedRobot(speed_cells_s=8,turn_deg_s=900,tick_s=.01,noise=0),FixtureCardRecognizer(FIXTURES/'scans'),Storage(tmp_path))
    await s.start()
    try:
        s.set_puzzle(next(p for p in s.storage.list_puzzles() if p.id=='fire-station'))
        await asyncio.sleep(.1)
        scan=s.do_scan()
        program=[Instruction(op=c.op,steps=c.rawSteps if c.op in ('FORWARD','BACKWARD') else None,cardId=c.cardId) for c in scan.cards]
        s.confirm_program(program,scan.scanId,True)
        await s.run();await asyncio.wait_for(s._run_task,5)
        assert s.attempt['stopReason']=='PROGRAM_COMPLETE'
        assert s.attempt['summary']['success']
        assert [event['correct'] for event in s.attempt['events']]==[True]*7
        assert all(command['command']['value']==1 for command in s.attempt['commands'] if command['command']['kind']=='MOVE')
    finally:await s.close()
