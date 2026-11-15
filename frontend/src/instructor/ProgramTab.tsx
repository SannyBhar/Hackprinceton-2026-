import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import type { Cell, Instruction, Op, Snapshot } from '../api/types';
import { unitInstruction, reviewBlocks, reviewedBlock as bookend, type ReviewBlock as Row } from '../api/unitBlocks';
import { Board } from '../board/Board';
import { BoardCard, Blocks, Card, ErrorBox, OP_ICON, TwoCol, useAction } from './common';

export function ProgramTab({ snap, onRun }: { snap: Snapshot; onRun: () => void }) {
  const { run, error, busy, setError } = useAction();
  const [rows, setRows] = useState<Row[]>([]);
  const [check, setCheck] = useState<{ok:boolean;errors:string[];plannedEntries?:Cell[]}|null>(null);

  useEffect(() => {
    if (!snap.scan) return;
    setRows(reviewBlocks(snap.scan));
  }, [snap.scan?.scanId]);

  const program: Instruction[] = useMemo(()=>rows.filter(r=>r.op).map(r=>unitInstruction(r.op!,r.cardId)),[rows]);
  const unresolved = rows.filter(r=>!r.reviewed || !r.op).length;
  useEffect(()=>{
    if (!program.length) {setCheck(null);return;}
    let disposed=false;
    setCheck(null);
    const t=setTimeout(()=>{
      api.validate(program).then(result=>{if(!disposed){setCheck(result);setError(null);}})
        .catch(e=>{if(!disposed){setCheck(null);setError(e.message);}});
    },150);
    return ()=>{disposed=true;clearTimeout(t);};
  },[JSON.stringify(program)]);

  const setRow=(i:number,patch:Partial<Row>)=>setRows(rs=>rs.map((r,j)=>j===i?{...r,...patch}:r));
  const move=(i:number,d:number)=>setRows(rs=>{
    const j=i+d;if(j<0||j>=rs.length)return rs;
    const next=[...rs];[next[i],next[j]]=[next[j],next[i]];return next;
  });
  const canEdit=!['RUNNING','RECORDING'].includes(snap.state) && !snap.deviceOperation;
  const canConfirm=canEdit && rows.length>0 && unresolved===0 && check?.ok;

  return <TwoCol left={<>
    <Card step="1" title="Scan the blocks" subtitle="One FORWARD/BACKWARD block moves one cell. Arrange blocks left to right with white gaps; no handwritten numbers.">
      <div className="row">
        <button disabled={!canEdit||busy} onClick={()=>run(async()=>{await api.clearScan();setRows([]);})}>Manual program / clear scan</button>
        <button className="primary" disabled={!canEdit||busy} onClick={()=>run(()=>api.scan())}>📷 Scan cards</button>
        {snap.scan&&<span className="muted small">Scan {snap.scan.scanId} · {snap.scan.source}</span>}
      </div>
      <p className="muted small">START and STOP are added around a scanned row when absent. Check every block and its order before confirming.</p>
      {snap.scan?.errors.map((e,i)=><div key={i} className="error">{e}</div>)}
    </Card>
    <Card step="2" title="Check what was read" subtitle="Repeated copies are separate blocks. Correct, reorder or remove a block before confirming.">
      {rows.length===0?<p className="muted small">No blocks yet — scan, or add blocks below.</p>:<table className="review">
        <thead><tr><th>#</th><th>Block</th><th>Read as</th><th /></tr></thead>
        <tbody>{rows.map((r,i)=><tr key={i} className={r.reviewed?'':'needs-review'}>
          <td>{i+1}</td><td><select aria-label={`Block ${i+1}`} disabled={!canEdit} value={r.op??''} onChange={e=>setRow(i,{op:(e.target.value||null) as Op|null,reviewed:true})}>
            <option value="">??</option>{Object.keys(OP_ICON).map(o=><option key={o} value={o}>{OP_ICON[o]} {o}</option>)}
          </select></td>
          <td className="small">{r.cardId==null?'Program control':`Marker ${r.cardId}`}
            {r.issues.map((issue,k)=><div key={k} className="issue">{issue}</div>)}
            {!r.reviewed&&<button disabled={!canEdit} className="ghost" onClick={()=>setRow(i,{reviewed:true})}>✓ Looks right</button>}
          </td><td className="nowrap">
            <button disabled={!canEdit} aria-label={`Move block ${i+1} up`} className="ghost icon" onClick={()=>move(i,-1)}>↑</button>
            <button disabled={!canEdit} aria-label={`Move block ${i+1} down`} className="ghost icon" onClick={()=>move(i,1)}>↓</button>
            <button disabled={!canEdit} aria-label={`Remove block ${i+1}`} className="ghost icon danger-text" onClick={()=>setRows(rs=>rs.filter((_,j)=>j!==i))}>✕</button>
          </td>
        </tr>)}</tbody>
      </table>}
      <div className="row">
        {(Object.keys(OP_ICON) as Op[]).map(op=><button disabled={!canEdit} key={op} className="icon" onClick={()=>setRows(rs=>[...rs,bookend(op)])}>{OP_ICON[op]} {op}</button>)}
        {rows.length>0&&<button disabled={!canEdit} className="ghost" onClick={()=>setRows([])}>Clear</button>}
        {unresolved>0&&<button disabled={!canEdit||rows.some(r=>!r.op)} onClick={()=>setRows(rs=>rs.map(r=>({...r,reviewed:true})))}>I checked every block and its order</button>}
      </div>
      {unresolved>0&&<div className="warn">{unresolved} block(s) need review before confirming.</div>}
      {check&&!check.ok&&check.errors.map((e,i)=><div key={i} className="error">{e}</div>)}
    </Card>
    <Card step="3" title="Confirm & run" subtitle="Confirming freezes the program — moving blocks afterwards has no effect.">
      <div className="row">
        <button className="primary" disabled={!canConfirm||busy} onClick={()=>run(()=>api.confirm(program,snap.scan?.scanId,true))}>Confirm program</button>
        <button className="go" disabled={snap.state!=='PROGRAM_READY'||busy||!canEdit} onClick={()=>run(async()=>{await api.run();onRun();})}>▶ Run</button>
        {['COMPLETED','STOPPED','FAULT'].includes(snap.state)&&<button disabled={!canEdit} onClick={()=>run(()=>api.reset())}>↺ Reset rover</button>}
      </div>
      {snap.program&&<Blocks program={snap.program}/>}<ErrorBox error={error}/>
    </Card>
  </>} right={<BoardCard title={snap.puzzle.name} extra={<span className="muted small">Dotted line = where this program would drive</span>}>
    <Board puzzle={snap.puzzle} tiles={snap.tiles} pose={snap.pose} theme={snap.projection.theme} artworkUrl={snap.projection.artworkId?`/api/themes/${snap.projection.artworkId}/image`:null}
      plannedEntries={check?.ok?check.plannedEntries:snap.plannedEntries} width="100%" height="auto"/>
  </BoardCard>}/>;
}
