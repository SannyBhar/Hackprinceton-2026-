import { useState } from 'react';
import { api } from '../api/client';
import type { Corner, Snapshot } from '../api/types';
import { Board } from '../board/Board';
import { THEMES } from '../board/themes';
import { ErrorBox, Feed, TwoCol, useAction } from './common';
import { openProjectionWindow } from '../projection/window';

const LABELS = ['TL', 'TR', 'BR', 'BL'];

export function SetupTab({ snap }: { snap: Snapshot }) {
  const { run, error } = useAction();
  const [step, setStep] = useState(5);
  const cal = snap.calibration;
  const ps = snap.projection;
  const sim = snap.robot.adapter === 'simulator';

  const setPs = (patch: Partial<typeof ps>) => run(() => api.setProjection({ ...ps, ...patch }));
  const setCorners = (corners: Corner[]) => run(() => api.saveCalibration({ ...cal, corners }));

  const nudge = (dx: number, dy: number) => {
    const i = ps.activeCorner;
    setCorners(cal.corners.map((c, j) => (j === i
      ? { x: c.x + (dx * step) / cal.viewportWidth, y: c.y + (dy * step) / cal.viewportHeight }
      : c)));
  };

  return (
    <TwoCol
      left={
        <>
          <h2>Projector</h2>
          <p className="muted">
            The projector is a passive display. Open the projection window, move it to the projector
            (extended display), press <kbd>F</kbd> for fullscreen, then calibrate.
          </p>
          <div className="row">
            <button onClick={openProjectionWindow}>Open projection window ↗</button>
            <button className={ps.calibrating ? 'primary' : ''} onClick={() => setPs({ calibrating: !ps.calibrating })}>
              {ps.calibrating ? 'Finish calibration' : 'Calibrate corners'}
            </button>
            <button className={ps.testPattern ? 'primary' : ''} onClick={() => setPs({ testPattern: !ps.testPattern })}>
              Test pattern
            </button>
          </div>

          <h3>Corner fine-adjust</h3>
          <div className="row">
            {LABELS.map((l, i) => (
              <button key={l} className={ps.activeCorner === i ? 'primary' : ''} onClick={() => setPs({ activeCorner: i })}>{l}</button>
            ))}
            <select value={step} onChange={(e) => setStep(Number(e.target.value))}>
              {[1, 5, 20, 50].map((s) => <option key={s} value={s}>{s}px</option>)}
            </select>
          </div>
          <div className="dpad small">
            <span /><button onClick={() => nudge(0, -1)}>↑</button><span />
            <button onClick={() => nudge(-1, 0)}>←</button><span className="muted">{LABELS[ps.activeCorner]}</span>
            <button onClick={() => nudge(1, 0)}>→</button>
            <span /><button onClick={() => nudge(0, 1)}>↓</button><span />
          </div>
          <div className="row">
            <button onClick={() => setCorners([{ x: 0.1, y: 0.1 }, { x: 0.9, y: 0.1 }, { x: 0.9, y: 0.9 }, { x: 0.1, y: 0.9 }])}>Reset inset</button>
            <button onClick={() => setCorners([{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 1, y: 1 }, { x: 0, y: 1 }])}>Fill output</button>
          </div>
          <p className="muted small">
            Saved for output {cal.viewportWidth}×{cal.viewportHeight}. Corners:{' '}
            {cal.corners.map((c, i) => `${LABELS[i]}(${(c.x * 100).toFixed(1)}%, ${(c.y * 100).toFixed(1)}%)`).join(' ')}
          </p>

          <h3>Display</h3>
          <label className="field">Theme
            <select value={ps.theme} onChange={(e) => setPs({ theme: e.target.value })}>
              {Object.entries(THEMES).map(([id, t]) => <option key={id} value={id}>{t.name}</option>)}
            </select>
          </label>
          <label className="field">Corner-marker dark zone ({Math.round(cal.markerMask * 100)}% of a cell)
            <input type="range" min={0} max={0.6} step={0.05} value={cal.markerMask}
                   onChange={(e) => run(() => api.saveCalibration({ ...cal, markerMask: Number(e.target.value) }))} />
          </label>
          <label className="check"><input type="checkbox" checked={cal.showGrid}
            onChange={(e) => run(() => api.saveCalibration({ ...cal, showGrid: e.target.checked }))} /> Grid lines</label>
          <label className="check"><input type="checkbox" checked={ps.showRobot}
            onChange={(e) => setPs({ showRobot: e.target.checked })} /> Draw simulated robot on projection</label>

          <h2>Robot</h2>
          <p>Adapter <b>{snap.robot.adapter}</b> — {snap.robot.connected ? 'connected' : 'NOT connected'}</p>
          {sim && (
            <>
              <h3>Simulator fault injection</h3>
              <div className="row">
                <button onClick={() => run(() => api.simFault({ lateralDrift: -0.35 }))}>Drift left</button>
                <button onClick={() => run(() => api.simFault({ lateralDrift: 0 }))}>No drift</button>
                <button onClick={() => run(() => api.simFault({ trackingLossMs: 2000 }))}>Lose tracking 2s</button>
                <button onClick={() => run(() => api.simFault({ linkUp: !snap.robot.connected }))}>
                  {snap.robot.connected ? 'Drop link' : 'Restore link'}
                </button>
              </div>
            </>
          )}
          <ErrorBox error={error} />
          <h3>Event log</h3>
          <Feed snap={snap} />
        </>
      }
      right={
        <>
          <p className="muted">Canonical board (unwarped). The projector shows this exact composition warped onto your corners.</p>
          <Board puzzle={snap.puzzle} tiles={snap.tiles} pose={snap.pose} theme={ps.theme}
                 showGrid markerMask={cal.markerMask} testPattern={ps.testPattern} width="100%" height="auto" />
        </>
      }
    />
  );
}
