import { useState, type ReactNode } from 'react';
import type { Cell, Instruction, Snapshot } from '../api/types';

export function useAction() {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try { await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  return { run, error, busy, setError };
}

export function ErrorBox({ error }: { error: string | null }) {
  return error ? <div className="error">{error}</div> : null;
}

export function TwoCol({ left, right }: { left: ReactNode; right: ReactNode }) {
  return (
    <div className="two-col">
      <section className="panel">{left}</section>
      <section className="stage">{right}</section>
    </div>
  );
}

export const fmtCell = (c: Cell | null | undefined) => (c ? `(${c.row},${c.col})` : '—');

export const OP_ICON: Record<string, string> = {
  START: '▶', STOP: '■', FORWARD: '↑', BACKWARD: '↓', LEFT: '↺', RIGHT: '↻',
};

export function Blocks({ program, active }: { program: Instruction[]; active?: number }) {
  return (
    <div className="blocks">
      {program.map((ins, i) => (
        <div key={i} className={`block op-${ins.op} ${i === active ? 'active' : ''}`}>
          <span className="icon">{OP_ICON[ins.op]}</span>
          <span>{ins.op}</span>
          {ins.steps != null && <span className="steps">{ins.steps}</span>}
        </div>
      ))}
    </div>
  );
}

export function Feed({ snap }: { snap: Snapshot }) {
  return (
    <div className="feed">
      {[...snap.feed].reverse().map((f, i) => (
        <div key={i} className={`feed-${f.level}`}>
          <span className="t">{new Date(f.t).toLocaleTimeString()}</span> {f.msg}
        </div>
      ))}
    </div>
  );
}
