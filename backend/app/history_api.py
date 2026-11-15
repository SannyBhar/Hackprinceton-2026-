"""History/student/recording routes bound to the single existing session."""
import asyncio
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .models import Instruction
from .joystick import JoystickSample
from .errors import ConflictError


class StudentBody(BaseModel):
    name: str = Field(min_length=1,max_length=80)
    synthetic: bool = False


class RecordingOptions(BaseModel):
    grade: bool = False


class SelectionBody(BaseModel):
    studentId: str | None = None


class RecordingImport(BaseModel):
    generated: list[Instruction]
    actions: list[dict] = []
    path: list[dict] = []
    warnings: list[str] = []
    rawInputs: list[dict] = []
    segments: list[dict] = []
    approximate: bool = True


class ReplayBody(BaseModel):
    reviewed: bool = False


def router(get_session):
    api=APIRouter(prefix='/api')

    @api.get('/students')
    async def students():
        return await asyncio.to_thread(get_session().storage.list_records,'students')

    @api.post('/students')
    async def create_student(body:StudentBody):
        record={'id':uuid.uuid4().hex,'name':body.name,'synthetic':body.synthetic}
        await asyncio.to_thread(get_session().storage.put_record,'students',record['id'],record)
        return record

    @api.put('/student')
    async def select_student(body:SelectionBody):
        from .errors import ConflictError,InvalidError
        try: get_session().select_student(body.studentId)
        except (ConflictError,InvalidError) as e: raise HTTPException(409,str(e))
        return {'ok':True}

    @api.get('/attempts')
    async def attempts(studentId:str|None=None):
        records=await asyncio.to_thread(get_session().storage.list_attempts)
        return [r for r in records if studentId is None or r.get('studentId')==studentId]

    @api.get('/recordings')
    async def recordings():
        return await asyncio.to_thread(get_session().storage.list_records,'recordings')

    @api.post('/recordings/import')
    async def import_recording(body:RecordingImport):
        record=body.model_dump(mode="json")
        record['id']=uuid.uuid4().hex
        record['warnings'].append('Imported recording; source observations not verified')
        await asyncio.to_thread(get_session().storage.put_record,'recordings',record['id'],record)
        return record

    @api.post('/recordings/{id}/confirm')
    async def replay(id:str,body:ReplayBody):
        s=get_session()
        if not body.reviewed: raise HTTPException(400,'review the approximate recording before replay')
        record=await asyncio.to_thread(s.storage.get_record,'recordings',id)
        if not record: raise HTTPException(404,'recording not found')
        from .errors import ConflictError,InvalidError
        try:
            s.scan=None
            s.confirm_program([Instruction.model_validate(i) for i in record['generated']])
        except (ConflictError,InvalidError,ValueError) as e: raise HTTPException(400,str(e))
        return {'ok':True}

    @api.put('/recording/options')
    async def options(body:RecordingOptions):
        s=get_session()
        if s.state.value in ('RUNNING','RECORDING'):raise HTTPException(409,'stop before changing recording options')
        s.recording_grade=body.grade
        return {'ok':True}

    @api.post('/joystick/sample')
    async def sample(body:JoystickSample):
        s=get_session()
        if s.robot.name!='simulator': raise HTTPException(409,'real joystick input is accepted only through configured USB serial')
        try: await s.joystick.sample(body,source='browser-simulator')
        except (ValueError,ConflictError) as e: raise HTTPException(409,str(e))
        return {'ok':True}

    return api
