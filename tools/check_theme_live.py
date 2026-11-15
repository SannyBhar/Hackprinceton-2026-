"""Explicit live-provider acceptance, with separate cache/offline acceptance checks.
Run with backend on PYTHONPATH and GEMINI_API_KEY in the private environment.
This sends one paid provider request. Does not authorize motors or modify real session data.
"""
import asyncio
import os
import tempfile
from pathlib import Path
from app.ai.themes import ThemeJobs
from app.dependencies import build_session
from app.settings import Settings


async def main():
    if not os.environ.get('GEMINI_API_KEY'):
        raise SystemExit('BLOCKED: configure GEMINI_API_KEY privately in the process environment')
    with tempfile.TemporaryDirectory(prefix='grassroot-theme-acceptance-') as directory:
        # Isolated simulator session; no camera, serial or physical robot is opened.
        session=build_session(Settings(data_dir=Path(directory),robot='sim',cards='fixture',tracker='sim'))
        service=ThemeJobs(session,Path(directory))
        try:
            job=await service.create('Friendly woodland, simple flat top-down texture')
            await service.tasks[job['id']]
            saved=session.storage.get_record('theme_assets',job['id'])
            if saved['status']!='READY':raise SystemExit('LIVE FAILED: '+str(saved.get('error')))
            assert (service.dir/(job['id']+'.png')).is_file()
            # New service has no running provider task: preview/accept use the disk cache.
            restarted=ThemeJobs(session,Path(directory))
            await restarted.accept(job['id'])
            assert session.projection.artworkId==job['id']
            class Offline:
                async def generate(self,*args):raise ValueError('explicit offline acceptance probe')
            restarted.provider=Offline()
            failed=await restarted.create('Offline test');await restarted.tasks[failed['id']]
            assert session.storage.get_record('theme_assets',failed['id'])['status']=='FAILED'
            assert session.projection.artworkId==job['id']
            session.set_projection(session.projection.model_copy(update={'artworkId':None,'artworkHash':None}))
            assert session.projection.artworkId is None
            print('PASS: one live generated image; cached preview/accept; offline cache retention and static fallback')
        finally:
            await service.close()
            if session._io_tasks:await asyncio.gather(*session._io_tasks)


if __name__=='__main__':asyncio.run(main())
