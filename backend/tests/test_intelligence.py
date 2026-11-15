import asyncio
import base64
import io
import pytest
from app.ai.themes import ThemeJobs, GeminiThemeProvider, puzzle_hash
from app.learning import progress,recommend,candidates,update,SKILLS
from app.models import Instruction
from app.compiler import plan
from test_boundaries import make_session


class FakeProvider:
    model='fixture-image'
    async def generate(self,prompt,reference):
        assert 'Authoritative layout' in prompt
        assert 'Learner' not in prompt
        from PIL import Image
        image=Image.new('RGB',(200,200),'navy');raw=io.BytesIO();image.save(raw,format='PNG');return raw.getvalue()


async def test_theme_cache_guard_and_motor_independence(tmp_path):
    s=make_session(tmp_path)
    service=ThemeJobs(s,tmp_path,FakeProvider())
    job=await service.create('Underwater')
    await service.tasks[job['id']]
    job=(await service.list())[0]
    assert job['status']=='READY'
    initial=s.puzzle.model_dump_json()
    await service.accept(job['id'])
    assert s.puzzle.model_dump_json()==initial
    assert s.projection.artworkId==job['id']
    s.puzzle=s.puzzle.model_copy(update={'version':s.puzzle.version+1})
    with pytest.raises(ValueError,match='puzzle changed'):await service.accept(job['id'])
    await asyncio.gather(*s._io_tasks)


async def test_theme_failure_and_cancel(tmp_path):
    s=make_session(tmp_path)
    class Broken:
        async def generate(self,*args):raise ValueError('offline')
    service=ThemeJobs(s,tmp_path,Broken())
    job=await service.create('Space');await service.tasks[job['id']]
    assert (await service.list())[0]['status']=='FAILED'
    assert s.projection.artworkId is None
    class Slow:
        async def generate(self,*args):await asyncio.sleep(100)
    service.provider=Slow();job=await service.create('Sea');await asyncio.sleep(0)
    await service.cancel(job['id'])
    records=await service.list()
    assert next(x for x in records if x['id']==job['id'])['status']=='CANCELLED'


async def test_real_provider_without_key_is_explicit_failure(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    with pytest.raises(ValueError,match='not configured'):
        await GeminiThemeProvider().generate('theme',b'png')


def test_learning_reproducible_and_operational_faults_excluded(tmp_path):
    s=make_session(tmp_path)
    program=[Instruction(op='START'),Instruction(op='FORWARD',steps=1),Instruction(op='STOP')]
    planned=plan(s.puzzle,program).plannedEntries
    a={'id':'a','studentId':'learner','startedAt':1,'stopReason':'PROGRAM_COMPLETE','puzzleSnapshot':s.puzzle.model_dump(mode='json'),
       'program':[i.model_dump() for i in program],'events':[{'actual':c.model_dump()} for c in planned],
       'summary':{'success':False,'correct':0,'entries':1},'skillEvidence':{'distance':False}}
    fault={**a,'id':'fault','stopReason':'BOUNDARY'}
    report=progress([a,fault],'learner')
    assert report==progress([a,fault],'learner')
    assert report['excludedOperationalOrUnattributed']==1
    assert next(x for x in report['skills'] if x['skill']=='direction')['evidenceCount']==0
    assert recommend(report)==recommend(report)
    assert update(.5,True)>update(.5,False)
    for skill in SKILLS:
        for candidate in candidates(skill):
            from app.models import Puzzle
            puzzle=Puzzle.model_validate(candidate['puzzle'])
            result=plan(puzzle,[Instruction.model_validate(i) for i in candidate['referenceProgram']])
            assert result.ok and result.plannedEntries==puzzle.targetEntries


async def test_theme_http_provider_request_contract(monkeypatch):
    import httpx
    from PIL import Image
    raw=io.BytesIO();Image.new('RGB',(50,50),'navy').save(raw,format='PNG')
    encoded=base64.b64encode(raw.getvalue()).decode()
    calls=[]
    def handle(request):
        import json
        payload=json.loads(request.content)
        assert request.headers['Api-Revision']=='2026-05-20'
        assert payload['store'] is False and payload['input'][1]['type']=='image'
        calls.append(request.url)
        return httpx.Response(200,json={'steps':[{'type':'model_output','content':[{'type':'image','data':encoded,'mime_type':'image/png'}]}]})
    client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
    monkeypatch.setenv('GEMINI_API_KEY','test-placeholder')
    monkeypatch.setattr('app.ai.themes.httpx.AsyncClient',lambda **kw:client)
    assert await GeminiThemeProvider().generate('decorative',b'reference')==raw.getvalue()
    assert len(calls)==1
