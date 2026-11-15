import { useEffect, useRef, useState } from 'react';
import { useGamepad, type Act } from './useGamepad';
import { api } from '../api/client';
import type { Snapshot } from '../api/types';
import { Board } from '../board/Board';
import { BoardCard, Blocks, Card, ErrorBox, TwoCol, fmtCell, useAction } from './common';

export function RecordingTab({ snap }: { snap: Snapshot }) {
  const { run, error } = useAction();
  const [grade, setGrade] = useState(false);
  const recording = snap.state === 'RECORDING';
  const rec = snap.recording;

  const toggle = useRef(() => {});
  const act = useRef((_: Act) => {});
  toggle.current = () => run(() => api.toggleRecording(grade, 'joystick'));
  act.current = (a: Act) => { if (recording) run(() => api.recordAction(a)); };
  const stableToggle = useRef(() => toggle.current()).current;
  const stableAct = useRef((a: Act) => act.current(a)).current;
  const pad = useGamepad(stableToggle, stableAct);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).tagName === 'INPUT') return;
      const m: Record<string, Act> = { ArrowUp: 'FORWARD', ArrowDown: 'BACKWARD', ArrowLeft: 'LEFT', ArrowRight: 'RIGHT' };
      if (m[e.key]) { e.preventDefault(); stableAct(m[e.key]); }
      if (e.key === ' ') { e.preventDefault(); stableToggle(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [stableAct, stableToggle]);

  const exportJson = () => {
    const blob = new Blob([JSON.stringify({ puzzleId: snap.puzzle.id, generated: rec.generated, path: rec.path,
      actions: rec.actions, warnings: rec.warnings }, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `recording-${Date.now()}.json`;
    a.click();
  };

  return (
    <TwoCol
      left={
        <>
          <Card title="Drive to write code"
                subtitle="A student drives with the joystick; the app writes the matching cards. It shows the route they drove — not necessarily the only solution.">
            <label className="check"><input type="checkbox" checked={grade} disabled={recording}
              onChange={(e) => setGrade(e.target.checked)} /> Also grade against this puzzle's route</label>
            <div className="row">
              <button className={recording ? 'stop big' : 'go big'} onClick={() => run(() => api.toggleRecording(grade, 'ui'))}>
                {recording ? '■ Stop recording' : '● Start recording'}
              </button>
            </div>
            <div className="row" style={{ gap: 18 }}>
              <div className="dpad">
                <span /><button disabled={!recording} onClick={() => stableAct('FORWARD')}>↑<br />FWD</button><span />
                <button disabled={!recording} onClick={() => stableAct('LEFT')}>↺<br />LEFT</button>
                <span />
                <button disabled={!recording} onClick={() => stableAct('RIGHT')}>↻<br />RIGHT</button>
                <span /><button disabled={!recording} onClick={() => stableAct('BACKWARD')}>↓<br />BACK</button><span />
              </div>
              <div className="small muted" style={{ flex: 1, minWidth: 140 }}>
                <div><b>Gamepad:</b> {pad ?? 'none yet — press any button'}</div>
                <div style={{ marginTop: 6 }}><kbd>←</kbd><kbd>↑</kbd><kbd>→</kbd><kbd>↓</kbd> drive</div>
                <div style={{ marginTop: 4 }}><kbd>Space</kbd> start / stop</div>
              </div>
            </div>
            <ErrorBox error={error} />
          </Card>

          <Card title={`Recorded moves (${rec.actions.length})`}>
            <div className="small muted">{rec.actions.map((a) => `${a.action}${a.observedEntries.length ? ' → ' + a.observedEntries.map(fmtCell).join('') : ''}`).join(' · ') || 'Nothing recorded yet.'}</div>
            {rec.warnings.map((w, i) => <div key={i} className="warn">{w}</div>)}
          </Card>

          {rec.generated && (
            <Card title="Generated cards" subtitle="Rebuild this with physical cards, or load it to replay.">
              <Blocks program={rec.generated} />
              <div className="row">
                <button onClick={exportJson}>⇩ Export JSON</button>
                <button className="primary" onClick={() => run(() => api.confirm(rec.generated!))}>Load as program</button>
              </div>
            </Card>
          )}
        </>
      }
      right={
        <BoardCard title={snap.puzzle.name} extra={recording ? <span className="state state-RECORDING">● REC</span> : undefined}>
          <Board puzzle={snap.puzzle} tiles={snap.tiles} pose={snap.pose} theme={snap.projection.theme}
                 highlight={rec.path} width="100%" height="auto" />
        </BoardCard>
      }
    />
  );
}
