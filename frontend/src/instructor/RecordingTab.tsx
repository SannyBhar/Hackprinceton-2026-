import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import type { Snapshot } from '../api/types';
import { Board } from '../board/Board';
import { Blocks, ErrorBox, TwoCol, fmtCell, useAction } from './common';

type Act = 'FORWARD' | 'BACKWARD' | 'LEFT' | 'RIGHT';
const DEAD_ZONE = 0.5;

/** Browser Gamepad adapter: button 0 toggles recording (rising edge, server also debounces),
 * d-pad / left stick give discrete one-cell moves and 90° turns. */
function useGamepad(onToggle: () => void, onAct: (a: Act) => void) {
  const [name, setName] = useState<string | null>(null);
  const prev = useRef<Record<string, boolean>>({});
  useEffect(() => {
    let raf = 0;
    const loop = () => {
      const gp = navigator.getGamepads?.().find((g) => g);
      setName(gp?.id ?? null);
      if (gp) {
        const ax = gp.axes[0] ?? 0, ay = gp.axes[1] ?? 0;
        const now: Record<string, boolean> = {
          toggle: !!gp.buttons[0]?.pressed,
          FORWARD: !!gp.buttons[12]?.pressed || ay < -DEAD_ZONE,
          BACKWARD: !!gp.buttons[13]?.pressed || ay > DEAD_ZONE,
          LEFT: !!gp.buttons[14]?.pressed || ax < -DEAD_ZONE,
          RIGHT: !!gp.buttons[15]?.pressed || ax > DEAD_ZONE,
        };
        for (const k of Object.keys(now)) {
          if (now[k] && !prev.current[k]) (k === 'toggle' ? onToggle() : onAct(k as Act));
        }
        prev.current = now;
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [onToggle, onAct]);
  return name;
}

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
          <h2>Reverse-engineering mode</h2>
          <p className="muted small">
            Child drives with the joystick; the app writes the matching cards. The recording describes the
            demonstrated route — not necessarily the shortest or only solution.
          </p>
          <label className="check"><input type="checkbox" checked={grade} disabled={recording}
            onChange={(e) => setGrade(e.target.checked)} /> Also grade against this puzzle's route</label>
          <div className="row">
            <button className={recording ? 'stop big' : 'go big'} onClick={() => run(() => api.toggleRecording(grade, 'ui'))}>
              {recording ? 'Stop recording ■' : 'Start recording ●'}
            </button>
          </div>
          <p className="muted small">Gamepad: {pad ?? 'none detected (press a button)'} · Keyboard: arrows drive, Space toggles.</p>
          <div className="dpad">
            <span /><button disabled={!recording} onClick={() => stableAct('FORWARD')}>↑<br />FWD</button><span />
            <button disabled={!recording} onClick={() => stableAct('LEFT')}>↺<br />LEFT</button>
            <span />
            <button disabled={!recording} onClick={() => stableAct('RIGHT')}>↻<br />RIGHT</button>
            <span /><button disabled={!recording} onClick={() => stableAct('BACKWARD')}>↓<br />BACK</button><span />
          </div>
          <ErrorBox error={error} />
          <h3>Recorded actions ({rec.actions.length})</h3>
          <div className="small muted">{rec.actions.map((a) => `${a.action}${a.observedEntries.length ? '→' + a.observedEntries.map(fmtCell).join('') : ''}`).join(' · ') || '—'}</div>
          {rec.generated && (
            <>
              <h3>Generated program</h3>
              <Blocks program={rec.generated} />
              <div className="row">
                <button onClick={exportJson}>Export JSON</button>
                <button onClick={() => run(() => api.confirm(rec.generated!))}>Load as confirmed program</button>
              </div>
            </>
          )}
          {rec.warnings.map((w, i) => <div key={i} className="warn small">{w}</div>)}
        </>
      }
      right={
        <Board puzzle={snap.puzzle} tiles={snap.tiles} pose={snap.pose} theme={snap.projection.theme}
               highlight={rec.path} width="100%" height="auto" />
      }
    />
  );
}
