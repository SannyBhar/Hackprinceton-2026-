import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Corner, Snapshot } from '../api/types';
import { Board } from '../board/Board';
import { CalibrationPad, keystone } from '../calibration/CalibrationPad';
import { THEMES } from '../board/themes';
import { BoardCard, Card, ErrorBox, Feed, TwoCol, useAction } from './common';
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
  // Slider moves fire fast; skip the busy/error wrapper and let the server state echo back.
  const sendCorners = (corners: Corner[]) => { api.saveCalibration({ ...cal, corners }).catch(() => {}); };
  const moving = snap.state === 'RUNNING' || snap.state === 'RECORDING';
  const [tl, tr, br, bl] = cal.corners;
  const keyAmt = 1 - (tr.x - tl.x) / Math.max(1e-6, br.x - bl.x);
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
          {snap.camera && <Card title="Shared webcam" subtitle={`${snap.camera.role} · ${snap.camera.ready ? 'ready' : 'not ready'}`}>
            <div className="row">
              <button disabled={moving} onClick={() => run(() => api.cameraRole('scan'))}>Scan camera</button>
              <button disabled={moving} onClick={() => run(() => api.cameraRole('track'))}>Arena tracking</button>
              <button disabled={moving} onClick={() => run(() => api.calibrateCamera())}>Validate camera calibration</button>
              <button disabled={moving} onClick={() => run(() => api.cameraRole('closed'))}>Close camera</button>
            </div>
            <p>After scanning, return the camera to the arena. Show all four corner markers and the robot marker, then validate. Any repositioning requires revalidation.</p>
            <CameraPreview />
            {snap.camera.error && <div className="error">{snap.camera.error}</div>}
          </Card>}
          <Card step="1" title="Projector window"
                subtitle="Open it, drag it to the projector display, press F for fullscreen.">
            <div className="row">
              <button className="primary" onClick={openProjectionWindow}>Open projection ↗</button>
              <button className={ps.testPattern ? 'toggle-on' : ''} onClick={() => setPs({ testPattern: !ps.testPattern })}>
                {ps.testPattern ? '✓ ' : ''}Test pattern
              </button>
            </div>
          </Card>

          <Card step="2" title="Line up the corners"
                subtitle="Watch the floor and drag each corner here until the projected grid sits square on your play area.">
            <ol className="small" style={{ margin: '0 0 4px', paddingLeft: 18, color: 'var(--ink-2)' }}>
              <li>Mark the 4 corners of a square play area on the floor (tape works).</li>
              <li><b>Fill output</b>, then use <b>Keystone</b> to pull the far corners in until the sides look parallel.</li>
              <li>Drag each corner onto its tape mark. Select a corner and use arrow keys (<kbd>Shift</kbd> = ×10) for the last few pixels.</li>
            </ol>
            <CalibrationPad cal={cal} puzzle={snap.puzzle} active={ps.activeCorner} disabled={moving}
                            onActive={(i) => setPs({ activeCorner: i })} />
            <label className="field">Keystone (far edge narrower ↔ wider) · {Math.round(keyAmt * 100)}%
              <input type="range" min={-0.3} max={0.7} step={0.005} value={keyAmt} disabled={moving}
                     onChange={(e) => sendCorners(keystone(cal.corners, Number(e.target.value)))} />
            </label>
            <div className="row">
              <div className="seg">
                {LABELS.map((l, i) => (
                  <button key={l} className={ps.activeCorner === i ? 'on' : ''} onClick={() => setPs({ activeCorner: i })}>{l}</button>
                ))}
              </div>
              <div className="dpad small">
                <span /><button onClick={() => nudge(0, -1)}>↑</button><span />
                <button onClick={() => nudge(-1, 0)}>←</button>
                <select value={step} onChange={(e) => setStep(Number(e.target.value))} style={{ padding: '2px', fontSize: '.75rem' }}>
                  {[1, 5, 20].map((s) => <option key={s} value={s}>{s}px</option>)}
                </select>
                <button onClick={() => nudge(1, 0)}>→</button>
                <span /><button onClick={() => nudge(0, 1)}>↓</button><span />
              </div>
            </div>
            <div className="row">
              <button onClick={() => setCorners([{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 1, y: 1 }, { x: 0, y: 1 }])}>Fill output</button>
              <button className="ghost" onClick={() => setCorners([{ x: 0.1, y: 0.1 }, { x: 0.9, y: 0.1 }, { x: 0.9, y: 0.9 }, { x: 0.1, y: 0.9 }])}>Reset inset</button>
              <button className={ps.calibrating ? 'toggle-on' : 'ghost'} onClick={() => setPs({ calibrating: !ps.calibrating })}>
                {ps.calibrating ? '✓ ' : ''}Handles on projection
              </button>
            </div>
            <p className="muted small" style={{ margin: 0 }}>
              Saved for a {cal.viewportWidth}×{cal.viewportHeight} projector output and survives restarts.
              {moving && ' Calibration is locked while the rover is moving.'}
            </p>
          </Card>

          <Card step="3" title="Look">
            <label className="field">Board theme
              <select value={ps.theme} onChange={(e) => setPs({ theme: e.target.value })}>
                {Object.entries(THEMES).map(([id, t]) => <option key={id} value={id}>{t.name}</option>)}
              </select>
            </label>
            <label className="field">Dark zone over corner markers · {Math.round(cal.markerMask * 100)}% of a cell
              <input type="range" min={0} max={0.6} step={0.05} value={cal.markerMask}
                     onChange={(e) => run(() => api.saveCalibration({ ...cal, markerMask: Number(e.target.value) }))} />
            </label>
            <label className="check"><input type="checkbox" checked={cal.showGrid}
              onChange={(e) => run(() => api.saveCalibration({ ...cal, showGrid: e.target.checked }))} /> Grid lines</label>
          </Card>

          <Card title="Rover" subtitle={`${snap.robot.adapter} · ${snap.robot.connected ? 'connected' : 'not connected'}`}>
            {sim ? (
              <>
                <p className="muted small" style={{ margin: 0 }}>Rehearse safety stops with the simulator:</p>
                <div className="row">
                  <button onClick={() => run(() => api.simFault({ lateralDrift: -0.35 }))}>Drift left</button>
                  <button onClick={() => run(() => api.simFault({ lateralDrift: 0 }))}>No drift</button>
                  <button onClick={() => run(() => api.simFault({ trackingLossMs: 2000 }))}>Lose tracking 2s</button>
                  <button onClick={() => run(() => api.simFault({ linkUp: !snap.robot.connected }))}>
                    {snap.robot.connected ? 'Drop link' : 'Restore link'}
                  </button>
                </div>
              </>
            ) : <p className="muted small">Physical rover. Fault injection is simulator-only.</p>}
            <ErrorBox error={error} />
          </Card>

          <Card title="Event log"><Feed snap={snap} /></Card>
        </>
      }
      right={
        <BoardCard title="Board preview" extra={<span className="muted small">Projection shows this warped onto your corners — without the rover</span>}>
          <Board puzzle={snap.puzzle} tiles={snap.tiles} pose={snap.pose} theme={ps.theme} roverAtStart
                 showGrid={cal.showGrid} markerMask={cal.markerMask} testPattern={ps.testPattern} width="100%" height="auto" />
        </BoardCard>
      }
    />
  );
}

function CameraPreview() {
  const [image, setImage] = useState('');
  useEffect(() => {
    const timer = window.setInterval(() => setImage(`/api/camera/image?t=${Date.now()}`), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return image ? <img alt="Shared webcam preview" src={image} style={{ width: '100%' }} /> : null;
}
