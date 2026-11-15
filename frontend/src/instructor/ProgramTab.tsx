import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import type { Cell, Instruction, Op, Snapshot } from '../api/types';
import { Board } from '../board/Board';
import { BoardCard, Blocks, Card, ErrorBox, OP_ICON, TwoCol, useAction } from './common';

type Row = {
  op: Op | null; steps: number | null; cardId: number | null;
  rawSteps: number | null; confidence: number | null; crop: string | null;
  issues: string[]; reviewed: boolean;
};

const needsNumber = (op: Op | null) => op === 'FORWARD' || op === 'BACKWARD';

export function ProgramTab({ snap, onRun }: { snap: Snapshot; onRun: () => void }) {
  const { run, error, busy } = useAction();
  const [rows, setRows] = useState<Row[]>([]);
  const [check, setCheck] = useState<{ ok: boolean; errors: string[]; plannedEntries?: Cell[] } | null>(null);

  // New scan -> new review rows. Raw OCR stays visible; confirmed value is separate.
  useEffect(() => {
    if (!snap.scan) return;
    setRows(snap.scan.cards.map((c) => ({
      op: c.op, cardId: c.cardId, rawSteps: c.rawSteps, confidence: c.stepsConfidence, crop: c.cropDataUrl,
      steps: c.rawSteps, issues: c.issues, reviewed: c.issues.length === 0 && !needsNumber(c.op),
    })));
  }, [snap.scan?.scanId]);

  const program: Instruction[] = useMemo(() => rows.filter((r) => r.op).map((r) => (
    needsNumber(r.op) ? { op: r.op!, steps: r.steps, cardId: r.cardId } : { op: r.op!, cardId: r.cardId }
  )), [rows]);

  const unresolved = rows.filter((r) => !r.reviewed).length;
  const missingNumbers = rows.some((r) => needsNumber(r.op) && (r.steps == null || Number.isNaN(r.steps)));

  useEffect(() => {
    if (!program.length || missingNumbers) { setCheck(null); return; }
    const t = setTimeout(() => {
      api.validate(program).then(setCheck).catch(() => setCheck(null));
    }, 150);
    return () => clearTimeout(t);
  }, [JSON.stringify(program), missingNumbers]);

  const setRow = (i: number, patch: Partial<Row>) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const add = (op: Op) => setRows((rs) => [...rs, { op, steps: needsNumber(op) ? null : null, cardId: null, rawSteps: null,
    confidence: null, crop: null, issues: [], reviewed: true }]);
  const move = (i: number, d: number) => setRows((rs) => {
    const j = i + d; if (j < 0 || j >= rs.length) return rs;
    const c = [...rs]; [c[i], c[j]] = [c[j], c[i]]; return c;
  });

  const canEdit = !['RUNNING', 'RECORDING'].includes(snap.state);
  const canConfirm = canEdit && rows.length > 0 && unresolved === 0 && !missingNumbers && check?.ok;

  return (
    <TwoCol
      left={
        <>
          <Card step="1" title="Scan the cards" subtitle="For physical scans, select Scan camera first; review every numeric value.">
            <div className="row">
              <button disabled={!canEdit || busy} onClick={() => run(() => api.clearScan())}>Manual program / clear scan</button>
              <button className="primary" disabled={!canEdit || busy} onClick={() => run(() => api.scan())}>📷 Scan cards</button>
              {snap.scan && <span className="muted small">Scan {snap.scan.scanId} · {snap.scan.source}</span>}
            </div>
            {snap.scan?.errors.map((e, i) => <div key={i} className="error">{e}</div>)}
          </Card>

          <Card step="2" title="Check what was read" subtitle="Fix any card or number. Highlighted rows need a look before confirming.">
            {rows.length === 0 ? <p className="muted small">No cards yet — scan, or add cards by hand below.</p> : (
              <table className="review">
                <thead><tr><th>#</th><th>Card</th><th>Steps</th><th>Read as</th><th /></tr></thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i} className={r.reviewed ? '' : 'needs-review'}>
                      <td>{i + 1}</td>
                      <td>
                        <select value={r.op ?? ''} onChange={(e) => setRow(i, { op: (e.target.value || null) as Op | null, reviewed: true })}>
                          <option value="">??</option>
                          {Object.keys(OP_ICON).map((o) => <option key={o} value={o}>{OP_ICON[o]} {o}</option>)}
                        </select>
                      </td>
                      <td>
                        {needsNumber(r.op) && (
                          <input type="number" className="steps" min={1} max={snap.maxSteps} value={r.steps ?? ''}
                                 placeholder="?" onChange={(e) => setRow(i, { steps: e.target.value === '' ? null : Number(e.target.value), reviewed: true })} />
                        )}
                      </td>
                      <td className="small">
                        {r.crop && <img src={r.crop} className="crop" />}
                        {needsNumber(r.op) && (r.rawSteps != null ? `${r.rawSteps} · ${Math.round((r.confidence ?? 0) * 100)}%` : 'unreadable')}
                        {r.issues.map((x, k) => <div key={k} className="issue">{x}</div>)}
                        {!r.reviewed && <button className="ghost" onClick={() => setRow(i, { reviewed: true })}>✓ Looks right</button>}
                      </td>
                      <td className="nowrap">
                        <button className="ghost icon" onClick={() => move(i, -1)}>↑</button>
                        <button className="ghost icon" onClick={() => move(i, 1)}>↓</button>
                        <button className="ghost icon danger-text" onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))}>✕</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <div className="row">
              {(Object.keys(OP_ICON) as Op[]).map((o) => <button key={o} className="icon" onClick={() => add(o)}>{OP_ICON[o]} {o}</button>)}
              {rows.length > 0 && <button className="ghost" onClick={() => setRows([])}>Clear</button>}
            </div>
            {unresolved > 0 && <div className="warn">{unresolved} card(s) need review before confirming.</div>}
            {missingNumbers && <div className="warn">Every FORWARD/BACKWARD needs a confirmed step count.</div>}
            {check && !check.ok && check.errors.map((e, i) => <div key={i} className="error">{e}</div>)}
          </Card>

          <Card step="3" title="Confirm & run" subtitle="Confirming freezes the program — moving cards afterwards has no effect.">
            <div className="row">
              <button className="primary" disabled={!canConfirm || busy} onClick={() => run(() => api.confirm(program, snap.scan?.scanId, true))}>
                Confirm program
              </button>
              <button className="go" disabled={snap.state !== 'PROGRAM_READY' || busy}
                      onClick={() => run(async () => { await api.run(); onRun(); })}>▶ Run</button>
              {['COMPLETED', 'STOPPED', 'FAULT'].includes(snap.state) && (
                <button onClick={() => run(() => api.reset())}>↺ Reset rover</button>
              )}
            </div>
            {snap.program && <Blocks program={snap.program} />}
            <ErrorBox error={error} />
          </Card>
        </>
      }
      right={
        <BoardCard title={snap.puzzle.name}
                   extra={<span className="muted small">Dotted line = where this program would drive</span>}>
          <Board puzzle={snap.puzzle} tiles={snap.tiles} pose={snap.pose} theme={snap.projection.theme}
                 plannedEntries={check?.ok ? check.plannedEntries : snap.plannedEntries} width="100%" height="auto" />
        </BoardCard>
      }
    />
  );
}
