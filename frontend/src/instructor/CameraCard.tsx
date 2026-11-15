import { useState } from 'react';
import { api } from '../api/client';
import type { Snapshot } from '../api/types';
import { applyH, type Pt } from '../calibration/homography';
import { Card, ErrorBox, useAction } from './common';

/** Overhead webcam: start it, calibrate it from the projected test pattern, and switch the
 * robot's position to come from the camera. Shows the live view with the mapped grid and
 * where the camera thinks the robot is. */
export function CameraCard({ snap, step }: { snap: Snapshot; step?: string }) {
  const { run, error, busy } = useAction();
  const cam = snap.boardCamera;
  const [index, setIndex] = useState<number>(cam?.cameraIndex ?? 0);
  const [streamKey, setStreamKey] = useState(0);
  if (!cam) return null;

  const moving = snap.state === 'RUNNING' || snap.state === 'RECORDING';
  const usingCamera = snap.poseSource === 'camera';
  const { rows, cols } = snap.puzzle;
  const det = cam.detection;
  const robotCell = det.found && det.x != null && det.y != null ? `row ${Math.floor(det.y)}, column ${Math.floor(det.x)}` : null;
  const margin = det.found && det.area && det.runnerUp ? det.area / det.runnerUp : null;

  // Overlay geometry (camera image normalised 0..1).
  const H = cam.boardToImage;
  const map = (u: number, v: number): Pt => (H ? applyH(H, [u, v]) : [u, v]);
  const lines: [Pt, Pt][] = [];
  if (H) {
    for (let i = 0; i <= cols; i++) lines.push([map(i / cols, 0), map(i / cols, 1)]);
    for (let j = 0; j <= rows; j++) lines.push([map(0, j / rows), map(1, j / rows)]);
  }
  const robotPt = det.found && det.x != null && det.y != null ? map(det.x / cols, det.y / rows) : null;
  const [fw, fh] = cam.frameSize ?? [16, 9];

  return (
    <Card step={step} title="Overhead camera"
          subtitle="Tracks the robot on the board so tiles light up as it enters each cell. No markers needed.">
      <div className="row">
        <label className="field">Camera
          <select value={index} disabled={cam.running} onChange={(e) => setIndex(Number(e.target.value))}>
            {[0, 1, 2, 3].map((i) => <option key={i} value={i}>Camera {i}</option>)}
          </select>
        </label>
        {cam.running
          ? <button disabled={busy || moving} onClick={() => run(() => api.boardCameraStop())}>Stop camera</button>
          : <button className="primary" disabled={busy} onClick={() => run(async () => { await api.boardCameraStart(index); setStreamKey(Date.now()); })}>Start camera</button>}
        {cam.running && <span className="chip">{cam.fps.toFixed(0)} fps · {cam.latencyMs} ms</span>}
      </div>
      {cam.error && <div className="error">{cam.error}</div>}

      {cam.running && (
        <div style={{ position: 'relative', borderRadius: 10, overflow: 'hidden', background: '#000' }}>
          <img src={`/api/board-camera/stream?k=${streamKey}`} alt="Live camera view"
               style={{ display: 'block', width: '100%', aspectRatio: `${fw} / ${fh}` }} />
          <svg viewBox="0 0 1 1" preserveAspectRatio="none"
               style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
            {lines.map(([a, b], i) => (
              <line key={i} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="#f5c400" strokeWidth={1.5}
                    vectorEffect="non-scaling-stroke" opacity={0.8} />
            ))}
            {robotPt && (
              <>
                <line x1={robotPt[0] - 0.02} y1={robotPt[1]} x2={robotPt[0] + 0.02} y2={robotPt[1]}
                      stroke="#ff2bd6" strokeWidth={4} vectorEffect="non-scaling-stroke" />
                <line x1={robotPt[0]} y1={robotPt[1] - 0.035} x2={robotPt[0]} y2={robotPt[1] + 0.035}
                      stroke="#ff2bd6" strokeWidth={4} vectorEffect="non-scaling-stroke" />
              </>
            )}
          </svg>
        </div>
      )}

      {cam.running && (
        <>
          <div className="row">
            <button disabled={busy || moving} onClick={() => run(() => api.boardCameraCalibrate())}>
              {cam.calibrated ? 'Recalibrate from projection' : 'Calibrate from projection'}
            </button>
            <span className="muted small">
              {cam.calibrated ? `Calibrated ${new Date(cam.calibratedAt!).toLocaleTimeString()}` : 'Not calibrated yet'}
            </span>
          </div>
          <p className="muted small" style={{ margin: 0 }}>
            Calibrating flashes the test pattern for about two seconds. Keep people off the board and the room dim.
            Recalibrate whenever the camera or projector moves.
          </p>
        </>
      )}

      {cam.running && cam.calibrated && (
        <div className={`note ${det.found ? 'ok' : 'warn'}`}>
          {det.found
            ? <>Robot seen in <b>{robotCell}</b>{margin && margin < 3 ? ' — but something else on the board looks similar; clear the board' : ''}.</>
            : det.reason ?? 'Robot not seen on the board.'}
        </div>
      )}

      <div className="row">
        <span className="muted small">Robot position from</span>
        <div className="seg">
          <button className={!usingCamera ? 'on' : ''} disabled={busy || moving}
                  onClick={() => run(() => api.setPoseSource('robot'))}>{snap.robot.adapter === 'simulator' ? 'Simulator' : 'Robot'}</button>
          <button className={usingCamera ? 'on' : ''} disabled={busy || moving || !cam.running || !cam.calibrated}
                  onClick={() => run(() => api.setPoseSource('camera'))}>Camera</button>
        </div>
      </div>
      {usingCamera && (
        <p className="muted small" style={{ margin: 0 }}>
          Without a marker the camera sees position but not which way the robot faces, so turns in place aren't
          detected. Use a bright board theme: dark themes hide the robot.
        </p>
      )}
      <ErrorBox error={error} />
    </Card>
  );
}
