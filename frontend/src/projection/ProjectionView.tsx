import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { useSession } from '../api/useSession';
import { Board, CELL } from '../board/Board';
import { isConvexClockwise, rectToQuad, toMatrix3d, type Pt } from '../calibration/homography';

const LABELS = ['TL', 'TR', 'BR', 'BL'];

/** Fullscreen passive output for the projector. Contains only board graphics.
 *
 * The board is rendered once in canonical pixels (cols*CELL x rows*CELL) and the
 * ENTIRE layer is perspective-warped with a CSS matrix3d onto the calibrated quad.
 * Calibration (drag handles / arrow keys) happens right here on the projected
 * image, toggled from the instructor Setup screen or with the C key.
 */
export function ProjectionView() {
  const { snap, connected } = useSession();
  const [vp, setVp] = useState({ w: window.innerWidth, h: window.innerHeight });
  const [drag, setDrag] = useState<Pt[] | null>(null);
  const [active, setActive] = useState(0);
  const [hint, setHint] = useState(true);
  const hideTimer = useRef<number>();

  useEffect(() => {
    const onResize = () => setVp({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  // Auto-hide cursor + hint when not interacting.
  useEffect(() => {
    const poke = () => {
      setHint(true);
      window.clearTimeout(hideTimer.current);
      hideTimer.current = window.setTimeout(() => setHint(false), 2500);
    };
    poke();
    window.addEventListener('mousemove', poke);
    return () => window.removeEventListener('mousemove', poke);
  }, []);

  useEffect(() => { if (snap) setActive(snap.projection.activeCorner); }, [snap?.projection.activeCorner]);

  const cal = snap?.calibration;
  const ps = snap?.projection;
  const corners: Pt[] = drag ?? (cal ? cal.corners.map((c) => [c.x * vp.w, c.y * vp.h] as Pt) : []);

  const save = useCallback(async (pts: Pt[]) => {
    if (!cal) return;
    await api.saveCalibration({
      ...cal,
      corners: pts.map(([x, y]) => ({ x: x / vp.w, y: y / vp.h })),
      viewportWidth: vp.w,
      viewportHeight: vp.h,
    }).catch((e) => console.error(e));
    setDrag(null);
  }, [cal, vp]);

  // The fullscreen projection window IS the projector output: adopt its size so the
  // laptop calibration pad has the right aspect. Corners are fractions, so they keep
  // pointing at the same spots on the projector raster. Non-fullscreen previews never write.
  const [isFull, setIsFull] = useState(!!document.fullscreenElement);
  useEffect(() => {
    const on = () => setIsFull(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', on);
    return () => document.removeEventListener('fullscreenchange', on);
  }, []);
  useEffect(() => {
    if (!cal || !isFull) return;
    if (cal.viewportWidth === vp.w && cal.viewportHeight === vp.h) return;
    const t = window.setTimeout(() => {
      api.saveCalibration({ ...cal, viewportWidth: vp.w, viewportHeight: vp.h }).catch(() => {});
    }, 400); // wait for the fullscreen resize to settle
    return () => window.clearTimeout(t);
  }, [isFull, vp.w, vp.h, cal?.viewportWidth, cal?.viewportHeight]);

  // Keyboard: F fullscreen, C calibrate, T test pattern, 1-4 corner, arrows nudge (shift = 10px).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!snap || !ps) return;
      if (e.key === 'f' || e.key === 'F') {
        if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen();
      } else if (e.key === 'c' || e.key === 'C') {
        api.setProjection({ ...ps, calibrating: !ps.calibrating });
      } else if (e.key === 't' || e.key === 'T') {
        api.setProjection({ ...ps, testPattern: !ps.testPattern });
      } else if (ps.calibrating && ['1', '2', '3', '4'].includes(e.key)) {
        api.setProjection({ ...ps, activeCorner: Number(e.key) - 1 });
      } else if (ps.calibrating && e.key.startsWith('Arrow')) {
        e.preventDefault();
        const step = e.shiftKey ? 10 : 1;
        const d = { ArrowUp: [0, -step], ArrowDown: [0, step], ArrowLeft: [-step, 0], ArrowRight: [step, 0] }[e.key]!;
        const pts = corners.map((p, i) => (i === active ? [p[0] + d[0], p[1] + d[1]] : p) as Pt);
        save(pts);
      } else if (e.key === 'Escape' && ps.calibrating) {
        api.setProjection({ ...ps, calibrating: false });
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [snap, ps, corners, active, save]);

  if (!snap || !cal || !ps) {
    return <div className="proj-root"><div className="proj-msg">Connecting to CodeAnywhere…</div></div>;
  }

  const W = snap.puzzle.cols * CELL;
  const H = snap.puzzle.rows * CELL;
  const convex = isConvexClockwise(corners);
  let transform = 'none';
  try { if (convex) transform = toMatrix3d(rectToQuad(W, H, corners)); } catch { /* degenerate */ }
  const mismatch = cal.viewportWidth !== vp.w || cal.viewportHeight !== vp.h;

  const onPointerDown = (i: number) => (e: React.PointerEvent) => {
    (e.target as Element).setPointerCapture(e.pointerId);
    setActive(i);
    setDrag(corners.map((p) => [...p] as Pt));
  };
  const onPointerMove = (i: number) => (e: React.PointerEvent) => {
    if (!drag) return;
    setDrag(drag.map((p, j) => (j === i ? [e.clientX, e.clientY] : p) as Pt));
  };
  const onPointerUp = () => { if (drag) save(drag); };

  return (
    <div className={`proj-root ${ps.calibrating || hint ? '' : 'proj-hide-cursor'}`}>
      <div
        className="proj-board"
        style={{ width: W, height: H, transform, visibility: convex ? 'visible' : 'hidden' }}
      >
        <Board
          puzzle={snap.puzzle}
          tiles={snap.tiles}
          pose={snap.pose}
          theme={ps.theme}
          showGrid={cal.showGrid || ps.calibrating}
          showIndices={false}
          showRobot={false} // the real rover sits on the board; never project one
          markerMask={cal.markerMask}
          testPattern={ps.testPattern}
          width={W}
          height={H}
        />
      </div>

      {ps.calibrating && (
        <>
          <svg className="proj-overlay" width={vp.w} height={vp.h}>
            <polygon points={corners.map((p) => p.join(',')).join(' ')} fill="none"
                     stroke={convex ? '#22d3ee' : '#ef4444'} strokeWidth={2} strokeDasharray="8 6" />
          </svg>
          {corners.map(([x, y], i) => (
            <div key={i}
                 className={`proj-handle ${i === active ? 'active' : ''}`}
                 style={{ left: x, top: y }}
                 onPointerDown={onPointerDown(i)}
                 onPointerMove={onPointerMove(i)}
                 onPointerUp={onPointerUp}>
              <span>{LABELS[i]}</span>
            </div>
          ))}
          <div className="proj-banner">
            <b>Calibrating projection</b> — drag the 4 handles onto the physical board corners.
            Keys: <kbd>1</kbd>–<kbd>4</kbd> select corner, arrows nudge (<kbd>Shift</kbd> ×10),
            <kbd>T</kbd> test pattern, <kbd>Esc</kbd> done.
            {!convex && <div className="warn">Corners are crossed or out of order (TL→TR→BR→BL clockwise).</div>}
            {mismatch && (
              <div className="warn">
                Saved for {cal.viewportWidth}×{cal.viewportHeight}; this output is {vp.w}×{vp.h}. Re-check alignment —
                the next adjustment saves for this size.
              </div>
            )}
          </div>
        </>
      )}

      {!ps.calibrating && mismatch && (
        <div className="proj-corner-warn">Calibration was saved for a different output size — recalibrate.</div>
      )}
      {!connected && <div className="proj-corner-warn">Reconnecting…</div>}
      {hint && !ps.calibrating && !document.fullscreenElement && (
        <button className="proj-fs" onClick={() => document.documentElement.requestFullscreen()}>
          Fullscreen (F)
        </button>
      )}
    </div>
  );
}
