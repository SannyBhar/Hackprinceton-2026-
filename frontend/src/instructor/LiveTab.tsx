import { api } from '../api/client';
import type { Snapshot } from '../api/types';
import { Board } from '../board/Board';
import { BoardCard, Blocks, Card, ErrorBox, Feed, FeedbackLegend, TwoCol, fmtCell, useAction } from './common';

const REASON_TEXT: Record<string, string> = {
  PROGRAM_COMPLETE: 'Program finished',
  INSTRUCTOR_STOP: 'Stopped by instructor',
  BOUNDARY: 'Safety stop: rover reached the board edge',
  TRACKING_LOST: 'Safety stop: camera lost the rover',
  CONNECTION_LOST: 'Safety stop: rover connection lost',
  ROBOT_FAULT: 'Rover reported a fault',
};

export function LiveTab({ snap }: { snap: Snapshot }) {
  const { run, error } = useAction();
  const a = snap.attempt;
  const s = a?.summary;
  const target = snap.puzzle.targetEntries;
  const rows = Math.max(target.length, a?.events.length ?? 0);
  const running = snap.state === 'RUNNING';

  return (
    <TwoCol
      left={
        <>
          <Card title="Run the rover" subtitle={snap.state === 'PROGRAM_READY' ? 'Program confirmed — ready to go.' : `State: ${snap.state.replace('_', ' ').toLowerCase()}`}>
            <div className="row">
              <button className="go big" disabled={snap.state !== 'PROGRAM_READY'} onClick={() => run(() => api.run())}>▶ Run</button>
              <button className="stop big" disabled={!running} onClick={() => run(() => api.stop())}>■ Stop</button>
              <button disabled={running || snap.state === 'RECORDING'} onClick={() => run(() => api.reset())}>↺ Reset</button>
            </div>
            <ErrorBox error={error} />
            {snap.pose && !snap.pose.trackingValid && <div className="warn">Tracking lost — rover position shown is stale, not observed.</div>}
            {a && <Blocks program={a.program} active={running ? a.instructionIndex : undefined} />}
          </Card>

          {a?.stopReason && (
            <div className={`result ${s?.success ? 'success' : a.stopReason === 'PROGRAM_COMPLETE' ? '' : 'fault'}`}>
              <b>{s?.success ? '🎉 Perfect route!' : REASON_TEXT[a.stopReason] ?? a.stopReason}</b>
              {s && <div className="small">{s.correct}/{target.length} correct · {s.incorrect} wrong · {s.missing} missing · {s.extra} extra</div>}
              {s?.details.map((d, i) => <div key={i} className="small muted">{d}</div>)}
            </div>
          )}

          <Card title="Step-by-step grading" subtitle="Each entered cell is compared with the route step at the same position.">
            <table>
              <thead><tr><th>#</th><th>Expected</th><th>Rover went</th><th /></tr></thead>
              <tbody>
                {Array.from({ length: rows }, (_, i) => {
                  const ev = a?.events[i];
                  return (
                    <tr key={i} className={ev ? (ev.correct ? 'ok' : 'bad') : 'pending'}>
                      <td>{i + 1}</td>
                      <td>{fmtCell(target[i])}</td>
                      <td>{ev ? fmtCell(ev.actual) : '…'}</td>
                      <td>{ev ? (ev.correct ? '✓' : '✗') : a?.stopReason ? 'missed' : ''}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {a?.warnings.map((w, i) => <div key={i} className="warn">{w}</div>)}
          </Card>

          <Card title="Event log"><Feed snap={snap} /></Card>
        </>
      }
      right={
        <BoardCard title={snap.puzzle.name} footer={<FeedbackLegend />}>
          <Board puzzle={snap.puzzle} tiles={snap.tiles} pose={snap.pose} theme={snap.projection.theme} artworkUrl={snap.projection.artworkId ? `/api/themes/${snap.projection.artworkId}/image` : null} width="100%" height="auto" />
        </BoardCard>
      }
    />
  );
}
