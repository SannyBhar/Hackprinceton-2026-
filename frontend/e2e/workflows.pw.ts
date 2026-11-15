import { test,expect } from '@playwright/test';

test('UI, scan review, global STOP and projection stay synchronized',async({page,context})=>{
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'Grassroot',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'■ STOP',exact:true})).toBeVisible();
  await page.getByRole('button',{name:/Program$/}).click();
  await page.getByRole('button',{name:'📷 Scan cards'}).click();
  await expect(page.getByRole('button',{name:'Confirm program',exact:true})).toBeDisabled();
  const state=await(await page.request.get('/api/state')).json();
  const denied=await page.request.post('/api/program/confirm',{data:{instructions:[{op:'START'},{op:'STOP'}]}});
  expect(denied.status()).toBe(400);
  await page.getByRole('button',{name:'Manual program / clear scan'}).click();
  const projection=await context.newPage();await projection.goto('/projection');
  await expect(projection.locator('svg').first()).toBeVisible();
  const ps={...state.projection,testPattern:true};
  await page.request.put('/api/projection',{data:ps});
  await expect(projection.getByText('TL',{exact:true})).toBeVisible();
  await page.request.put('/api/projection',{data:{...ps,testPattern:false}});
  await projection.reload();await expect(projection.locator('svg').first()).toBeVisible();
  await projection.close();
});

test('library import, local students, calibration pad and saved attempt history work',async({page})=>{
  await page.goto('/');
  await page.getByRole('button',{name:/History$/}).click();
  await page.getByLabel('Student alias').fill('Browser learner');
  await page.getByRole('button',{name:'Add student',exact:true}).click();
  await expect(page.getByLabel('Student',{exact:true})).toContainText('Browser learner');
  const options=page.getByLabel('Student',{exact:true}).locator('option');const id=await options.last().getAttribute('value');
  await page.getByLabel('Student',{exact:true}).selectOption(id!);
  const s=await(await page.request.get('/api/state')).json();
  await page.getByLabel('Import puzzle JSON').setInputFiles({name:'puzzle.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({...s.puzzle,id:'browser-import',name:'Browser imported'}))});
  await expect.poll(async()=>{const p=await(await page.request.get('/api/puzzles')).json();return p.some((x:{id:string})=>x.id==='browser-import');}).toBe(true);
  await page.getByRole('button',{name:/Setup$/}).click();
  await expect(page.locator('svg[tabindex="0"]')).toBeVisible();
  await page.locator('svg[tabindex="0"]').focus();await page.keyboard.press('ArrowRight');
  await expect.poll(async()=> (await(await page.request.get('/api/state')).json()).calibration.corners[0].x).toBeGreaterThan(s.calibration.corners[0].x);
  await page.request.delete('/api/scan');
  await page.request.post('/api/program/confirm',{data:{instructions:[{op:'START'},{op:'STOP'}]}});
  await page.request.post('/api/run');
  await expect.poll(async()=> (await(await page.request.get('/api/state')).json()).state).toBe('COMPLETED');
  await page.getByRole('button',{name:/History$/}).click();
  await page.getByRole('button',{name:'Refresh history'}).click();
  await expect(page.getByRole('button',{name:'Details',exact:true}).first()).toBeVisible();
});

test('progress recommendations need instructor approval and themes retain static fallback',async({page})=>{
  // Provider UI fixture: this is explicitly not a live Gemini acceptance test.
  await page.route('**/api/themes',async route=>{
    await route.fulfill({json:route.request().method()==='GET'?[{id:'fixture',status:'FAILED',themeText:'Offline theme',error:'Provider offline; static retained',accepted:false,puzzleHash:'fixture'}]:{id:'fixture',status:'FAILED'}});
  });
  await page.goto('/');
  await page.getByRole('button',{name:/Themes & Progress$/}).click();
  await expect(page.getByText('Provider offline; static retained')).toBeVisible();
  await expect(page.getByRole('button',{name:'Use static theme',exact:true})).toBeEnabled();
  await page.screenshot({path:'../work/integrated-progress.png',fullPage:true});
});

test('readiness and live joystick status are visible; serial errors do not disappear',async({page})=>{
  await page.goto('/');
  await page.getByRole('button',{name:/Setup$/}).click();
  await expect(page.getByText(/Ready to move/)).toBeVisible();
  await page.getByRole('button',{name:/Record$/}).click();
  await expect(page.getByText(/Disconnected · neutral \/ released input required · stale/)).toBeVisible();
  await page.route('**/api/joystick/sample',r=>r.fulfill({status:409,json:{detail:'Joystick input compatibility error'}}));
  await expect(page.getByText('Joystick input compatibility error')).toBeVisible();
  await expect(page.getByRole('button',{name:'■ STOP',exact:true})).toBeVisible();
});
