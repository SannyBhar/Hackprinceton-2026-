import { api } from '../api/client';
import type { Snapshot } from '../api/types';
import { Board } from '../board/Board';
import { Blocks, ErrorBox, Feed, TwoCol, fmtCell, useAction } from './common';

const REASON_TEXT: Record<string, string> = {
  PROGRAM_COMPLETE: 'Program finished normally',
  INSTRUCTOR_STOP: 'Stopped by instructor',
  BOUNDARY: 'Operational stop: robot approached the board edge',
  TRACKING_LOST: 'Operational stop: camera lost the robot',
  CONNECTION_LOST: 'Operational stop: robot connection lost',
  ROBOT_FAULT: 'Robot reported a fault',
};

export function LiveTab({ snap }: { snap: Snapshot }) {
  const { run, error } = useAction();
  const a = snap.attempt;
  const s = a?.summary;
  const target = snap.puzzle.targetEntries;
  const rows = Math.max(target.length, a?.events.length ?? 0);

  return (
    <TwoCol
      left={
        <>
          <div className="row">
            <button className="go big" disabled={snap.state !== 'PROGRAM_READY'} onClick={() => run(() => api.run())}>Run ▶</button>
            <button className="stop big" onClick={() => run(() => api.stop())}>STOP ■</button>
            <button disabled={['RUNNING', 'RECORDING'].includes(snap.state)} onClick={() => run(() => api.reset())}>Reset attempt</button>
          </div>
          <ErrorBox error={error} />
          {snap.pose && !snap.pose.trackingValid && <div className="warn">Tracking lost — robot position shown is stale, not observed.</div>}

          {a && (
            <>
              <h3>Program (frozen)</h3>
              <Blocks program={a.program} active={snap.state === 'RUNNING' ? a.instructionIndex : undefined} />
            </>
          )}

          {a?.stopReason && (
            <div className={`result ${s?.success ? 'success' : a.stopReason === 'PROGRAM_COMPLETE' ? 'neutral' : 'fault'}`}>
              <b>{s?.success ? '🎉 Route matched exactly!' : REASON_TEXT[a.stopReason] ?? a.stopReason}</b>
              {s && <div>{s.correct}/{target.length} correct entries · {s.incorrect} wrong · {s.missing} missing · {s.extra} extra</div>}
              {s?.details.map((d, i) => <div key={i} className="small">{d}</div>)}
            </div>
          )}

          <h3>Ordered grading</h3>
          <table className="grading">
            <thead><tr><th>#</th><th>Target</th><th>Actual</th><th /></tr></thead>
            <tbody>
              {Array.from({ length: rows }, (_, i) => {
                const ev = a?.events[i];
                return (
                  <tr key={i} className={ev ? (ev.correct ? 'ok' : 'bad') : 'pending'}>
                    <td>{i + 1}</td>
                    <td>{fmtCell(target[i])}</td>
                    <td>{ev ? fmtCell(ev.actual) : '…'}</td>
                    <td>{ev ? (ev.correct ? '✓' : '✗') : a?.stopReason ? 'missing' : ''}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {a?.warnings.map((w, i) => <div key={i} className="warn small">{w}</div>)}
          <h3>Event log</h3>
          <Feed snap={snap} />
        </>
      }
      right={
        <Board puzzle={snap.puzzle} tiles={snap.tiles} pose={snap.pose} theme={snap.projection.theme}
               width="100%" height="auto" />
      }
    />
  );
}
