import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import type { Corner, ProjectorCalibration, Puzzle } from '../api/types';
import { applyH, isConvexClockwise, rectToQuad, type Pt } from './homography';

const LABELS = ['TL', 'TR', 'BR', 'BL'];
const PAD_W = 1000;

/** Laptop-side corner calibration.
 *
 * The rectangle is a miniature of the projector's whole output; the four handles are where
 * the board's corners are drawn in that output. Drag a handle (or select it and use the
 * arrow keys) while watching the floor: the projection updates live. With a projector
 * tilted downward the far edge of the image spreads wider, so the far (top) handles get
 * pulled inward until the projected grid is square on the floor.
 */
export function CalibrationPad({ cal, puzzle, active, onActive, disabled }: {
  cal: ProjectorCalibration; puzzle: Puzzle; active: number;
  onActive: (i: number) => void; disabled?: boolean;
}) {
  const padH = Math.round(PAD_W * (cal.viewportHeight / cal.viewportWidth));
  const [local, setLocal] = useState<Corner[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const dragging = useRef<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const lastSent = useRef(0);
  const pending = useRef<number | undefined>();

  const corners = local ?? cal.corners;
  const pts: Pt[] = corners.map((c) => [c.x * PAD_W, c.y * padH]);
  const convex = isConvexClockwise(pts);

  // Server is the source of truth once we're not mid-drag.
  useEffect(() => { if (dragging.current === null) setLocal(null); }, [cal]);

  const send = (cs: Corner[], force = false) => {
    if (!isConvexClockwise(cs.map((c) => [c.x * PAD_W, c.y * padH]))) return;
    const doSend = () => {
      lastSent.current = Date.now();
      api.saveCalibration({ ...cal, corners: cs }).then(() => setError(null)).catch((e) => setError(e.message));
    };
    window.clearTimeout(pending.current);
    if (force || Date.now() - lastSent.current > 70) doSend();       // ~14 updates/s while dragging
    else pending.current = window.setTimeout(doSend, 70);
  };

  const toNorm = (e: React.PointerEvent): Corner | null => {
    const ctm = svgRef.current?.getScreenCTM();
    if (!ctm) return null;
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(ctm.inverse());
    const clamp = (v: number) => Math.min(1, Math.max(0, v));
    return { x: clamp(p.x / PAD_W), y: clamp(p.y / padH) };
  };

  const onDown = (e: React.PointerEvent<SVGSVGElement>) => {
    if (disabled) return;
    const n = toNorm(e);
    if (!n) return;
    // grab the nearest handle
    let best = 0, bestD = Infinity;
    corners.forEach((c, i) => {
      const d = (c.x - n.x) ** 2 * PAD_W ** 2 + (c.y - n.y) ** 2 * padH ** 2;
      if (d < bestD) { bestD = d; best = i; }
    });
    if (Math.sqrt(bestD) > 90) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    e.currentTarget.focus();
    dragging.current = best;
    onActive(best);
  };
  const onMove = (e: React.PointerEvent) => {
    const i = dragging.current;
    if (i === null) return;
    const n = toNorm(e);
    if (!n) return;
    const next = corners.map((c, j) => (j === i ? n : c));
    setLocal(next);
    send(next);
  };
  const onUp = () => {
    if (dragging.current !== null && local) send(local, true);
    dragging.current = null;
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (disabled) return;
    if (['1', '2', '3', '4'].includes(e.key)) { onActive(Number(e.key) - 1); return; }
    if (e.key === 'Tab' && !e.shiftKey && active < 3) { e.preventDefault(); onActive(active + 1); return; }
    const d = ({ ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] } as Record<string, number[]>)[e.key];
    if (!d) return;
    e.preventDefault();
    const px = e.shiftKey ? 10 : 1; // projector pixels
    const next = corners.map((c, j) => (j === active
      ? { x: Math.min(1, Math.max(0, c.x + (d[0] * px) / cal.viewportWidth)),
          y: Math.min(1, Math.max(0, c.y + (d[1] * px) / cal.viewportHeight)) }
      : c));
    setLocal(next);
    send(next, true);
  };

  // Preview grid lines: straight lines stay straight under a homography.
  let grid: JSX.Element[] = [];
  if (convex) {
    const H = rectToQuad(puzzle.cols, puzzle.rows, pts);
    const line = (a: Pt, b: Pt, k: string, strong = false) => {
      const [x1, y1] = applyH(H, a), [x2, y2] = applyH(H, b);
      return <line key={k} x1={x1} y1={y1} x2={x2} y2={y2} stroke={strong ? '#3f6fb5' : '#7fa7d9'} strokeWidth={strong ? 4 : 2} />;
    };
    grid = [
      ...Array.from({ length: puzzle.cols + 1 }, (_, i) => line([i, 0], [i, puzzle.rows], `v${i}`, i === 0 || i === puzzle.cols)),
      ...Array.from({ length: puzzle.rows + 1 }, (_, i) => line([0, i], [puzzle.cols, i], `h${i}`, i === 0 || i === puzzle.rows)),
    ];
  }

  return (
    <div>
      <svg ref={svgRef} viewBox={`-30 -30 ${PAD_W + 60} ${padH + 60}`} tabIndex={0}
           style={{ width: '100%', display: 'block', touchAction: 'none', outline: 'none', borderRadius: 12,
                    background: 'var(--cream-2)', cursor: disabled ? 'not-allowed' : 'crosshair' }}
           onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onKeyDown={onKey}>
        <rect x={0} y={0} width={PAD_W} height={padH} rx={6} fill="#1d2737" />
        <text x={PAD_W / 2} y={padH - 14} textAnchor="middle" fill="#7d889c" fontSize={22} fontWeight={700}>
          projector output (near edge of the floor is usually at the bottom)
        </text>
        <polygon points={pts.map((p) => p.join(',')).join(' ')} fill={convex ? '#e3edf9' : '#fdecea'}
                 opacity={0.95} stroke={convex ? '#3f6fb5' : '#dc4a3d'} strokeWidth={3} />
        {grid}
        {pts.map(([x, y], i) => (
          <g key={i} transform={`translate(${x},${y})`} style={{ cursor: 'grab' }}>
            <circle r={26} fill={i === active ? '#f5c400' : '#fffdf9'} stroke="#1d2737" strokeWidth={3} />
            <text y={8} textAnchor="middle" fontSize={22} fontWeight={900} fill="#1d2737">{LABELS[i]}</text>
          </g>
        ))}
      </svg>
      {!convex && <div className="error" style={{ marginTop: 8 }}>Corners are crossed — keep them in order TL → TR → BR → BL.</div>}
      {error && <div className="error" style={{ marginTop: 8 }}>{error}</div>}
    </div>
  );
}

/** Pull the far (top) corners inward symmetrically relative to the near (bottom) corners —
 * a one-slider keystone correction for a projector tilted down at the floor. Fine-tune after. */
export function keystone(corners: Corner[], amount: number): Corner[] {
  const [, , br, bl] = corners;
  const width = br.x - bl.x;
  const inset = (width * amount) / 2;
  return [
    { x: bl.x + inset, y: corners[0].y },
    { x: br.x - inset, y: corners[1].y },
    br,
    bl,
  ];
}
