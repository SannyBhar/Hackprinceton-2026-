import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Attempt, Recording, Snapshot, Student } from '../api/types';
import { Blocks, Card, ErrorBox, useAction } from './common';

function download(name: string, data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
  const a=document.createElement('a'); a.href=url; a.download=name; a.click(); URL.revokeObjectURL(url);
}

export function HistoryTab({snap}: {snap:Snapshot}) {
  const [students,setStudents]=useState<Student[]>([]);
  const [attempts,setAttempts]=useState<Attempt[]>([]);
  const [recordings,setRecordings]=useState<Recording[]>([]);
  const [name,setName]=useState('');
  const [details,setDetails]=useState<Attempt|null>(null);
  const {run,error}=useAction();
  const refresh=async()=>{ const [s,a,r]=await Promise.all([api.students(),api.attempts(snap.studentId??undefined),api.recordings()]); setStudents(s);setAttempts(a);setRecordings(r); };
  useEffect(()=>{run(refresh);},[snap.studentId,snap.attemptHistory.length]);
  return <>
    <Card title="Local students and saved history" subtitle="Local aliases only; no cloud accounts. Synthetic learners are labeled separately.">
      <select aria-label="Student" value={snap.studentId??''} disabled={['RUNNING','RECORDING'].includes(snap.state)} onChange={e=>run(()=>api.selectStudent(e.target.value||null))}>
        <option value="">Unassigned session</option>{students.map(s=><option key={s.id} value={s.id}>{s.name}{s.synthetic?' (synthetic)':''}</option>)}
      </select>
      <input aria-label="Student alias" value={name} maxLength={80} onChange={e=>setName(e.target.value)} placeholder="Local student alias" />
      <button disabled={!name.trim()} onClick={()=>run(async()=>{await api.createStudent(name.trim());setName('');await refresh();})}>Add student</button>
      <button onClick={()=>run(refresh)}>Refresh history</button>
      <button onClick={()=>download('greenlite-puzzle.json',snap.puzzle)}>Export active puzzle</button>
      <label>Import puzzle JSON <input type="file" accept="application/json" onChange={e=>{const f=e.target.files?.[0];if(f)run(async()=>{await api.savePuzzleOnly(JSON.parse(await f.text()));await refresh();});}} /></label>
      <label>Import recording JSON <input type="file" accept="application/json" onChange={e=>{const f=e.target.files?.[0];if(f)run(async()=>{await api.importRecording(JSON.parse(await f.text()));await refresh();});}} /></label>
      <ErrorBox error={error} />
    </Card>
    <Card title="Attempts">
      {attempts.length===0 && <p>No saved attempts for this selection.</p>}
      {attempts.slice().reverse().map(a=><div className="row" key={a.id}><span>{new Date(a.startedAt).toLocaleString()} · {a.source??'legacy'} · {a.stopReason??'in progress'} · {a.summary?.correct??0} correct</span><button onClick={()=>setDetails(a)}>Details</button><button onClick={()=>download(`attempt-${a.id}.json`,a)}>Export</button></div>)}
      {details && <><Blocks program={details.program}/>
        {details.stopReason==='PROGRAM_COMPLETE' && <div><p>Instructor-observed skill evidence (do not attribute hardware faults to the learner):</p>{['direction','distance','sequencing','spatial'].map(skill=><span key={skill}>{skill} <button onClick={()=>run(()=>api.annotateSkill(details.id,skill,true))}>Observed correct</button><button onClick={()=>run(()=>api.annotateSkill(details.id,skill,false))}>Observed incorrect</button></span>)}</div>}<pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(details,null,2)}</pre></>}
    </Card>
    <Card title="Recordings" subtitle="Continuous reconstructions are approximate. Review the code and warnings before loading; loading does not move the robot.">
      {recordings.map((r,i)=><div key={r.id??i}><p>{r.id} · {r.approximate?'Approximate continuous':'Discrete recording'}</p>{r.generated&&<Blocks program={r.generated}/>} {r.warnings.map((w,j)=><p className="warn" key={j}>{w}</p>)}
        <button onClick={()=>download(`recording-${r.id}.json`,r)}>Export raw recording</button>
        <button disabled={!r.id||['RUNNING','RECORDING'].includes(snap.state)} onClick={()=>{if(window.confirm('I reviewed this generated program and its uncertainty warnings. Load without running?'))run(()=>api.confirmRecording(r.id!,true));}}>Review & load program</button>
      </div>)}
    </Card>
  </>;
}
