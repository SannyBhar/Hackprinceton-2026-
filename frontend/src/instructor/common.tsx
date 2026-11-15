import { useState, type ReactNode } from 'react';
import type { Cell, Instruction, Snapshot } from '../api/types';
import { FEEDBACK } from '../board/Board';

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

export function Card({ title, subtitle, step, actions, children }: {
  title: ReactNode; subtitle?: ReactNode; step?: ReactNode; actions?: ReactNode; children?: ReactNode;
}) {
  return (
    <div className="card">
      <div className="card-head">
        {step != null && <span className="step">{step}</span>}
        <div style={{ flex: 1 }}>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {actions}
      </div>
      <div className="card-body">{children}</div>
    </div>
  );
}

export function BoardCard({ title, extra, children, footer }: {
  title: ReactNode; extra?: ReactNode; children: ReactNode; footer?: ReactNode;
}) {
  return (
    <div className="board-card">
      <div className="board-head"><h2>{title}</h2><span className="spacer" />{extra}</div>
      <div className="board-frame">{children}</div>
      {footer}
    </div>
  );
}

export function FeedbackLegend() {
  return (
    <div className="legend">
      <span><i style={{ background: FEEDBACK.correct }} />✓ correct cell</span>
      <span><i style={{ background: FEEDBACK.incorrect }} />✗ wrong cell</span>
      <span><i style={{ background: `linear-gradient(135deg, ${FEEDBACK.correct} 50%, ${FEEDBACK.incorrect} 50%)` }} />
        revisit: first ◤ / latest ◢</span>
      <span><i style={{ background: '#3f6fb5', borderRadius: 99 }} />route order</span>
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
  if (!snap.feed.length) return <p className="muted small">No events yet.</p>;
  return (
    <div className="feed">
      {[...snap.feed].reverse().map((f, i) => (
        <div key={i} className={`feed-${f.level}`}>
          <span className="t">{new Date(f.t).toLocaleTimeString()}</span>{f.msg}
        </div>
      ))}
    </div>
  );
}
