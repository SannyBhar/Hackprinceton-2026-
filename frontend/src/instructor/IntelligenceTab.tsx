import { useEffect,useState } from 'react';
import { api } from '../api/client';
import type { Snapshot,ThemeJob,ProgressReport,Recommendation } from '../api/types';
import { Board } from '../board/Board';
import { Card,ErrorBox,useAction } from './common';

export function IntelligenceTab({snap}:{snap:Snapshot}) {
  const [text,setText]=useState('Underwater adventure');
  const [jobs,setJobs]=useState<ThemeJob[]>([]);
  const [report,setReport]=useState<ProgressReport|null>(null);
  const [suggestions,setSuggestions]=useState<Recommendation[]>([]);
  const {run,error}=useAction();
  const moving=['RUNNING','RECORDING'].includes(snap.state);
  useEffect(()=>{
    let disposed=false;
    const refresh=()=>api.themes().then(j=>{if(!disposed)setJobs(j);}).catch(()=>{});
    refresh();const timer=window.setInterval(refresh,2000);
    return ()=>{disposed=true;window.clearInterval(timer);};
  },[]);
  const progress=async()=>{if(!snap.studentId)return;setReport(await api.progress(snap.studentId));setSuggestions(await api.recommendations(snap.studentId));};
  useEffect(()=>{setReport(null);setSuggestions([]);run(progress);},[snap.studentId]);
  return <>
    <Card title="Decorative AI themes" subtitle="Nano Banana artwork changes appearance only. Preview and accept while stopped. Static themes remain available offline.">
      <input aria-label="Theme description" value={text} maxLength={500} onChange={e=>setText(e.target.value)} />
      <button disabled={!text.trim()} onClick={()=>run(async()=>{await api.generateTheme(text);setJobs(await api.themes());})}>Generate artwork</button>
      <button disabled={moving} onClick={()=>run(()=>api.setProjection({...snap.projection,artworkId:null,artworkHash:null}))}>Use static theme</button>
      {jobs.slice().reverse().map(j=><div key={j.id}><p>{j.themeText} · {j.status}{j.accepted?' · accepted':''}</p>
        {j.error&&<p className="warn">{j.error}</p>}
        {j.url&&<Board puzzle={snap.puzzle} theme={snap.projection.theme} artworkUrl={j.url} width="100%" height="auto" />}
        {j.status==='READY'&&<button disabled={moving} onClick={()=>run(()=>api.acceptTheme(j.id))}>Accept for matching puzzle</button>}
        {j.status==='GENERATING'&&<button onClick={()=>run(()=>api.cancelTheme(j.id))}>Cancel generation</button>}
      </div>)}
    </Card>
    <Card title="Progress and next challenge" subtitle="Select a student in History. Recommendations require instructor approval and never move the robot.">
      <button disabled={!snap.studentId} onClick={()=>run(progress)}>Refresh progress</button>
      {report&&<>
        <p>{report.synthetic?'SYNTHETIC DEMONSTRATION DATA':'Actual recorded attempts'} · {report.limitations}</p>
        <div className="row">{report.skills.map(s=><label key={s.skill}>{s.skill} <meter min={0} max={1} value={s.estimate}/>{Math.round(s.estimate*100)}% · {s.evidenceCount} observations{s.uncertain?' · uncertain':''}</label>)}</div>
        <p>{report.excludedOperationalOrUnattributed} operational/unattributed attempts excluded.</p>
        <div aria-label="Attempt accuracy trend">{report.trend.map(t=><div key={t.attemptId} className="row"><span>{new Date(t.startedAt).toLocaleString()}</span><meter min={0} max={Math.max(1,t.entries)} value={t.correct}/><span>{t.correct}/{t.entries}</span></div>)}</div>
      </>}
      {suggestions.map(r=><div key={r.puzzle.id}><p>{r.explanation}</p><Board puzzle={r.puzzle} roverAtStart width={350} />
        <button disabled={moving} onClick={()=>run(()=>api.savePuzzle(r.puzzle))}>Approve & load challenge</button>
      </div>)}
    </Card><ErrorBox error={error}/>
  </>;
}
