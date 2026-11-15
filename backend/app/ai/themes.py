"""Decorative Nano Banana jobs. This module cannot command motors or change puzzles."""
import asyncio
import base64
import hashlib
import io
import json
import os
import time
import uuid
from pathlib import Path
import httpx


from ..models import puzzle_hash


def reference_png(puzzle):
    from PIL import Image, ImageDraw
    image=Image.new('RGB',(puzzle.cols*64,puzzle.rows*64),'white');draw=ImageDraw.Draw(image)
    for cell in [puzzle.startCell,*puzzle.targetEntries]:
        draw.rectangle((cell.col*64,cell.row*64,(cell.col+1)*64,(cell.row+1)*64),fill='#cbd5e1')
    for col in range(puzzle.cols+1):draw.line((col*64,0,col*64,image.height),fill='#334155')
    for row in range(puzzle.rows+1):draw.line((0,row*64,image.width,row*64),fill='#334155')
    stream=io.BytesIO();image.save(stream,format='PNG');return stream.getvalue()


class GeminiThemeProvider:
    def __init__(self):
        self.model=os.environ.get('GRASSROOT_THEME_MODEL','gemini-nano-banana-2.1')

    async def generate(self,prompt,reference):
        key=os.environ.get('GEMINI_API_KEY')
        if not key: raise ValueError('GEMINI_API_KEY is not configured; use cached/static artwork')
        async with httpx.AsyncClient(timeout=90) as client:
            response=await client.post('https://generativelanguage.googleapis.com/v1beta/interactions',
                headers={'x-goog-api-key':key,'Api-Revision':'2026-05-20'},
                json={'model':self.model,'store':False,'input':[
                    {'type':'text','text':prompt},
                    {'type':'image','mime_type':'image/png','data':base64.b64encode(reference).decode()}],
                    'response_format':{'type':'image','mime_type':'image/png'}})
            if response.status_code>=400:
                raise ValueError(f'image provider HTTP {response.status_code}; static theme retained')
            payload=response.json()
        image=payload.get('output_image')
        if not image:
            for step in payload.get('steps',[]):
                if step.get('type')!='model_output':continue
                for part in step.get('content',[]):
                    if part.get('type')=='image' and part.get('data'):image=part
        if not image or not image.get('data'):raise ValueError('image provider returned no image')
        if len(image['data'])>20_000_000:raise ValueError('generated image too large')
        return base64.b64decode(image['data'],validate=True)


class ThemeJobs:
    def __init__(self,session,data_dir:Path,provider=None):
        self.session,self.dir=session,data_dir/'theme_assets'
        self.dir.mkdir(parents=True,exist_ok=True)
        self.provider=provider or GeminiThemeProvider()
        self.tasks={}

    async def list(self):
        return await asyncio.to_thread(self.session.storage.list_records,'theme_assets')

    async def create(self,text):
        if len([t for t in self.tasks.values() if not t.done()])>=2:raise ValueError('two artwork jobs already active')
        puzzle=self.session.puzzle.model_copy(deep=True)
        job={'id':uuid.uuid4().hex,'status':'GENERATING','themeText':text,'puzzleId':puzzle.id,
             'puzzleVersion':puzzle.version,'puzzleHash':puzzle_hash(puzzle),'createdAt':int(time.time()*1000),
             'model':getattr(self.provider,'model','test-provider'),'provider':'Gemini','promptVersion':1,'accepted':False,'error':None}
        await self.save(job)
        self.tasks[job['id']]=asyncio.create_task(self._generate(job,puzzle))
        return job

    async def save(self,job):
        await asyncio.to_thread(self.session.storage.put_record,'theme_assets',job['id'],dict(job))

    async def _generate(self,job,puzzle):
        try:
            layout={k:v for k,v in puzzle.model_dump(mode='json').items() if k not in ('name',)}
            prompt=('Create age-appropriate flat top-down decorative maze artwork. No text, no extra routes, '
                    'no red/green grading colors. Leave corner marker regions and robot marker unobstructed. '
                    'The app overlays exact routes/grid; artwork cannot redefine geometry. Theme: '+job['themeText']+
                    '\nAuthoritative layout: '+json.dumps(layout))
            reference=await asyncio.to_thread(reference_png,puzzle)
            raw=await asyncio.wait_for(self.provider.generate(prompt,reference),95)
            width,height=await asyncio.to_thread(self._validate_save,job['id'],raw,puzzle)
            job.update(status='READY',width=width,height=height,url=f"/api/themes/{job['id']}/image")
        except asyncio.CancelledError:
            job.update(status='CANCELLED',error='generation cancelled')
        except Exception as e:
            job.update(status='FAILED',error=str(e))
        finally:
            await self.save(job)
            self.session.changed()

    def _validate_save(self,id,raw,puzzle):
        from PIL import Image,ImageOps
        if len(raw)>15_000_000:raise ValueError('image exceeds size limit')
        image=Image.open(io.BytesIO(raw))
        if image.format not in ('PNG','JPEG','WEBP') or image.width*image.height>16_000_000:
            raise ValueError('unsupported image size/format')
        image.load()
        image=ImageOps.fit(image.convert('RGB'),(puzzle.cols*100,puzzle.rows*100))
        tmp=self.dir/(id+'.tmp');image.save(tmp,format='PNG');tmp.replace(self.dir/(id+'.png'))
        return image.size

    async def accept(self,id):
        from ..errors import ConflictError
        if self.session.state.value in ('RUNNING','RECORDING'):raise ConflictError('stop before accepting artwork')
        job=await asyncio.to_thread(self.session.storage.get_record,'theme_assets',id)
        if not job or job['status']!='READY':raise ValueError('artwork is not ready')
        if job['puzzleHash']!=puzzle_hash(self.session.puzzle):raise ValueError('puzzle changed; regenerate artwork')
        # Recheck after I/O so a concurrently started run cannot be modified.
        if self.session.state.value in ('RUNNING','RECORDING'):raise ConflictError('stop before accepting artwork')
        ps=self.session.projection.model_copy(update={'artworkId':id,'artworkHash':job['puzzleHash']})
        self.session._validated_artwork = (id,job["puzzleHash"])
        self.session.set_projection(ps)
        job.update(accepted=True,acceptedAt=int(time.time()*1000));await self.save(job)
        return job

    async def cancel(self,id):
        task=self.tasks.get(id)
        if task and not task.done():task.cancel();await asyncio.gather(task,return_exceptions=True)

    async def close(self):
        for task in self.tasks.values():task.cancel()
        await asyncio.gather(*self.tasks.values(),return_exceptions=True)
