"""Theme/progress application boundary. Recommendations never activate themselves."""
import asyncio
import re
from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field
from .learning import progress,recommend,SKILLS
from .session import ConflictError


class ThemeBody(BaseModel):
    text:str=Field(min_length=1,max_length=500)


class SkillEvidence(BaseModel):
    skill:str
    correct:bool


def router(get_session):
    api=APIRouter(prefix='/api')

    def themes():
        service=get_session().themes
        if service is None:raise HTTPException(503,'theme service starting')
        return service

    @api.get('/themes')
    async def list_themes():return await themes().list()

    @api.post('/themes')
    async def create_theme(body:ThemeBody):
        try:return await themes().create(body.text)
        except ValueError as e:raise HTTPException(409,str(e))

    @api.post('/themes/{id}/accept')
    async def accept(id:str):
        try:return await themes().accept(id)
        except ConflictError as e:raise HTTPException(409,str(e))
        except ValueError as e:raise HTTPException(400,str(e))

    @api.delete('/themes/{id}')
    async def cancel(id:str):
        await themes().cancel(id);return {'ok':True}

    @api.get('/themes/{id}/image')
    async def image(id:str):
        if not re.fullmatch('[a-f0-9]{32}',id):raise HTTPException(404,'image not found')
        path=themes().dir/(id+'.png')
        if not path.exists():raise HTTPException(404,'image not found')
        return FileResponse(path,media_type='image/png')

    @api.get('/students/{id}/progress')
    async def student_progress(id:str):
        s=get_session()
        student=await asyncio.to_thread(s.storage.get_record,'students',id)
        if not student:raise HTTPException(404,'student not found')
        attempts=await asyncio.to_thread(s.storage.list_attempts)
        report=await asyncio.to_thread(progress,attempts,id)
        report['synthetic']=student['synthetic']
        await asyncio.to_thread(s.storage.put_record,'skill_estimates',id,report)
        return report

    @api.get('/students/{id}/recommendations')
    async def recommendations(id:str):
        report=await student_progress(id)
        return recommend(report)

    @api.post('/attempts/{id}/evidence')
    async def annotate(id:str,body:SkillEvidence):
        s=get_session()
        if body.skill not in SKILLS:raise HTTPException(400,'unknown skill')
        attempts=await asyncio.to_thread(s.storage.list_attempts)
        a=next((a for a in attempts if a['id']==id),None)
        if not a:raise HTTPException(404,'attempt not found')
        if a.get('stopReason')!='PROGRAM_COMPLETE':raise HTTPException(409,'operationally interrupted attempts are excluded')
        a.setdefault('skillEvidence',{})[body.skill]=body.correct
        await asyncio.to_thread(s.storage.save_attempt,id,a)
        return {'ok':True}

    return api
