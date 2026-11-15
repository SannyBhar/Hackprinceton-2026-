import { useId, useRef, useState } from 'react';
import type { Cell, Puzzle, RobotPose, TileState } from '../api/types';
import { cellKey, sameCell } from '../api/types';
import { Rover } from './Rover';
import { DEFAULT_THEME, THEMES } from './themes';

export const CELL = 100; // canonical board pixels per cell (projection warps this whole layer)
const GAP = 4;           // gap between tiles = visible grid line

export const FEEDBACK = { correct: '#24a159', incorrect: '#dc4a3d' };

export type PaintPhase = 'start' | 'move' | 'end';

type Props = {
  puzzle: Puzzle;
  tiles?: Record<string, TileState>;
  pose?: RobotPose | null;
  plannedEntries?: Cell[];
  theme?: string;
  showGrid?: boolean;
  showIndices?: boolean;
  showRobot?: boolean;
  roverAtStart?: boolean;     // draw the rover parked on the start cell when there's no live pose
  markerMask?: number;        // fraction of a cell kept black at each corner (projection)
  testPattern?: boolean;
  highlight?: Cell[];         // cells to outline (editor cursor, recorded path)
  onCellClick?: (c: Cell) => void;
  onPaint?: (c: Cell, phase: PaintPhase) => void; // click-and-drag editing (mouse + touch)
  width?: number | string;
  height?: number | string;
  className?: string;
};

const center = (c: Cell): [number, number] => [(c.col + 0.5) * CELL, (c.row + 0.5) * CELL];
const HEADING_ROT: Record<string, number> = { N: 0, E: 90, S: 180, W: 270 };

export function Board(p: Props) {
  const { puzzle } = p;
  const W = puzzle.cols * CELL;
  const H = puzzle.rows * CELL;
  const theme = THEMES[p.theme ?? DEFAULT_THEME] ?? THEMES[DEFAULT_THEME];
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '');
  const svgRef = useRef<SVGSVGElement>(null);
  const painting = useRef<string | null>(null);
  const [hover, setHover] = useState<Cell | null>(null);

  if (p.testPattern) return <TestPattern puzzle={puzzle} width={p.width} height={p.height} />;

  const route = [puzzle.startCell, ...puzzle.targetEntries];
  const routeSet = new Set(route.map(cellKey));
  const routePts = route.map((c) => center(c).join(',')).join(' ');
  const indexLabels = new Map<string, number[]>();
  puzzle.targetEntries.forEach((c, i) => {
    const k = cellKey(c);
    indexLabels.set(k, [...(indexLabels.get(k) ?? []), i + 1]);
  });
  const cells: Cell[] = [];
  for (let r = 0; r < puzzle.rows; r++) for (let c = 0; c < puzzle.cols; c++) cells.push({ row: r, col: c });

  // ---- pointer -> cell (works with letterboxing and touch via pointer capture)
  const cellAt = (e: React.PointerEvent): Cell | null => {
    const svg = svgRef.current;
    const ctm = svg?.getScreenCTM();
    if (!svg || !ctm) return null;
    const pt = new DOMPoint(e.clientX, e.clientY).matrixTransform(ctm.inverse());
    const c = { row: Math.floor(pt.y / CELL), col: Math.floor(pt.x / CELL) };
    return c.row >= 0 && c.row < puzzle.rows && c.col >= 0 && c.col < puzzle.cols ? c : null;
  };
  const interactive = !!(p.onPaint || p.onCellClick);
  const handlers = interactive ? {
    onPointerDown: (e: React.PointerEvent<SVGSVGElement>) => {
      const c = cellAt(e);
      if (!c) return;
      if (p.onPaint) {
        e.currentTarget.setPointerCapture(e.pointerId);
        painting.current = cellKey(c);
        p.onPaint(c, 'start');
      } else p.onCellClick?.(c);
    },
    onPointerMove: (e: React.PointerEvent<SVGSVGElement>) => {
      const c = cellAt(e);
      setHover(c);
      if (c && p.onPaint && painting.current && painting.current !== cellKey(c)) {
        painting.current = cellKey(c);
        p.onPaint(c, 'move');
      }
    },
    onPointerUp: (e: React.PointerEvent<SVGSVGElement>) => {
      if (painting.current && p.onPaint) {
        const c = cellAt(e);
        if (c) p.onPaint(c, 'end');
      }
      painting.current = null;
    },
    onPointerLeave: () => setHover(null),
  } : {};

  const g = (n: string) => `${n}${uid}`;

  return (
    <svg
      ref={svgRef}
      className={p.className}
      viewBox={`0 0 ${W} ${H}`}
      // Numeric sizes go on attributes; CSS sizes like '100%'/'auto' must go in style.
      width={typeof p.width === 'string' ? undefined : (p.width ?? W)}
      height={typeof p.height === 'string' ? undefined : (p.height ?? H)}
      preserveAspectRatio="xMidYMid meet"
      style={{
        display: 'block', touchAction: interactive ? 'none' : undefined, cursor: interactive ? 'pointer' : undefined,
        width: typeof p.width === 'string' ? p.width : undefined,
        height: typeof p.height === 'string' ? p.height : undefined,
      }}
      {...handlers}
    >
      <defs>
        <linearGradient id={g('tile')} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={theme.tileTop} /><stop offset="1" stopColor={theme.tileBottom} />
        </linearGradient>
        <linearGradient id={g('route')} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={theme.routeTop} /><stop offset="1" stopColor={theme.routeBottom} />
        </linearGradient>
        <linearGradient id={g('gloss')} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity={theme.gloss} />
          <stop offset="1" stopColor="#fff" stopOpacity={0} />
        </linearGradient>
        <radialGradient id={g('pad')}>
          <stop offset="0" stopColor={theme.start} stopOpacity={0.35} />
          <stop offset="1" stopColor={theme.start} stopOpacity={0.08} />
        </radialGradient>
      </defs>

      {/* Layer 1: background artwork (prepared theme; AI artwork slots in here) */}
      <rect width={W} height={H} fill={(p.showGrid ?? true) ? theme.ground : theme.tileBottom} />
      {cells.map((c) => {
        const k = cellKey(c);
        const onRoute = routeSet.has(k);
        const scenery = !onRoute && puzzle.sceneryCells.some((s) => sameCell(s, c));
        const s = CELL - GAP * 2;
        return (
          <g key={`t${k}`} transform={`translate(${c.col * CELL + GAP},${c.row * CELL + GAP})`}>
            <rect width={s} height={s} rx={9} fill={`url(#${g(onRoute ? 'route' : 'tile')})`}
                  stroke={theme.tileStroke} strokeWidth={1.5} />
            {theme.gloss > 0 && <rect x={5} y={4} width={s - 10} height={s * 0.42} rx={7} fill={`url(#${g('gloss')})`} />}
            <rect x={1} y={s - 5} width={s - 2} height={4} rx={2} fill="#000" opacity={0.04} />
            {scenery && <g transform={`translate(${-GAP},${-GAP})`}>{theme.scenery(c)}</g>}
          </g>
        );
      })}

      {/* Layer 2: exact route cues (app-rendered, never derived from artwork) */}
      {route.length > 1 && (
        <>
          <polyline points={routePts} fill="none" stroke={theme.road} strokeWidth={34} opacity={0.5}
                    strokeLinejoin="round" strokeLinecap="round" />
          <polyline points={routePts} fill="none" stroke={theme.roadLine} strokeWidth={4}
                    strokeDasharray="2 14" strokeLinejoin="round" strokeLinecap="round" opacity={0.9} />
        </>
      )}

      {/* Layer 3: start / goal indicators and labels */}
      <g transform={`translate(${center(puzzle.startCell).join(',')})`}>
        <circle r={38} fill={`url(#${g('pad')})`} stroke={theme.start} strokeWidth={3} strokeDasharray="6 6" />
        <path d="M0,-34 L10,-22 L-10,-22 Z" fill={theme.start}
              transform={`rotate(${HEADING_ROT[puzzle.startHeading]})`} />
      </g>
      {route.length > 1 && (
        <g transform={`translate(${center(puzzle.goalCell).join(',')})`}><CheckeredFlag /></g>
      )}
      {(p.showIndices ?? true) && [...indexLabels].map(([k, idx]) => {
        const [r, c] = k.split(',').map(Number);
        const label = idx.join(',');
        const w = 14 + label.length * 9;
        return (
          <g key={`ix${k}`} transform={`translate(${c * CELL + 10},${r * CELL + 10})`}>
            <rect width={w} height={22} rx={11} fill={theme.badgeBg} opacity={0.92} />
            <text x={w / 2} y={16} textAnchor="middle" fontSize={14} fontWeight={800} fill={theme.badgeFg}
                  fontFamily="Nunito, system-ui, sans-serif">{label}</text>
          </g>
        );
      })}

      {/* Layer 4: live correctness feedback (always on top, symbols + colour) */}
      {p.tiles && Object.entries(p.tiles).map(([k, t]) => <FeedbackTile key={`fb${k}`} k={k} t={t} />)}

      {p.plannedEntries && p.plannedEntries.length > 0 && (
        <polyline points={[puzzle.startCell, ...p.plannedEntries].map((c) => center(c).join(',')).join(' ')}
                  fill="none" stroke="#3f6fb5" strokeWidth={6} strokeDasharray="3 11"
                  strokeLinecap="round" strokeLinejoin="round" opacity={0.9} />
      )}

      {p.highlight?.map((c, i) => (
        <rect key={`hl${i}`} x={c.col * CELL + 7} y={c.row * CELL + 7} width={CELL - 14} height={CELL - 14}
              fill="none" stroke="#3f6fb5" strokeWidth={5} rx={11} opacity={0.85} />
      ))}
      {interactive && hover && (
        <rect x={hover.col * CELL + GAP} y={hover.row * CELL + GAP} width={CELL - GAP * 2} height={CELL - GAP * 2}
              rx={9} fill="#5b8fd1" opacity={0.14} pointerEvents="none" />
      )}

      {/* Rover: live pose when we have one; otherwise (editor) parked on the start, facing its heading. */}
      {(p.showRobot ?? true) && !p.pose && p.roverAtStart && (
        <g transform={`translate(${center(puzzle.startCell).join(',')}) rotate(${HEADING_ROT[puzzle.startHeading]}) scale(0.95)`}>
          <Rover />
        </g>
      )}
      {(p.showRobot ?? true) && p.pose && (
        <g transform={`translate(${p.pose.x * CELL},${p.pose.y * CELL}) rotate(${p.pose.headingDeg}) scale(0.95)`}
           opacity={p.pose.trackingValid ? 1 : 0.55}>
          <Rover stale={!p.pose.trackingValid} />
        </g>
      )}

      {p.markerMask ? <MarkerMasks W={W} H={H} size={p.markerMask * CELL} /> : null}
    </svg>
  );
}

/** Checkered finish flag on a pole, centred on the goal cell. */
function CheckeredFlag() {
  const cols = 4, rows = 3, sq = 8;
  const x0 = -6, y0 = -30;
  const squares = [];
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const wave = Math.sin((c / cols) * Math.PI) * 3; // gentle ripple
    squares.push(
      <rect key={`${r}${c}`} x={x0 + c * sq} y={y0 + r * sq + wave} width={sq + 0.4} height={sq + 0.4}
            fill={(r + c) % 2 ? '#ffffff' : '#111111'} />,
    );
  }
  return (
    <g>
      <circle r={34} fill="#fff" opacity={0.75} />
      <circle r={34} fill="none" stroke="#111" strokeWidth={2} strokeDasharray="4 4" opacity={0.5} />
      <ellipse cx={-8} cy={26} rx={10} ry={3} fill="#000" opacity={0.15} />
      <line x1={-8} y1={26} x2={-8} y2={-32} stroke="#3a3a3a" strokeWidth={4} strokeLinecap="round" />
      <circle cx={-8} cy={-33} r={3} fill="#f5c400" stroke="#3a3a3a" strokeWidth={1.5} />
      <g stroke="#111" strokeWidth={1.5}>
        {squares}
      </g>
    </g>
  );
}

function FeedbackTile({ k, t }: { k: string; t: TileState }) {
  if (t.kind === 'unvisited') return null;
  const [r, c] = k.split(',').map(Number);
  const x = c * CELL + GAP, y = r * CELL + GAP, s = CELL - GAP * 2;
  const col = (ok: boolean | null) => (ok ? FEEDBACK.correct : FEEDBACK.incorrect);
  const sym = (ok: boolean | null) => (ok ? '✓' : '✗');
  const font = 'Nunito, system-ui, sans-serif';
  if (t.kind === 'solid') {
    return (
      <g>
        <rect x={x} y={y} width={s} height={s} rx={9} fill={col(t.left)} opacity={0.9} />
        <text x={x + s / 2} y={y + s / 2 + 16} textAnchor="middle" fontSize={46} fontWeight={900}
              fill="#fff" fontFamily={font}>{sym(t.left)}</text>
      </g>
    );
  }
  // split: diagonal from bottom-left to top-right. Left triangle touches top-left (FIRST),
  // right triangle touches bottom-right (LATEST).
  return (
    <g>
      <polygon points={`${x},${y} ${x + s},${y} ${x},${y + s}`} fill={col(t.left)} opacity={0.92} />
      <polygon points={`${x + s},${y} ${x + s},${y + s} ${x},${y + s}`} fill={col(t.right)} opacity={0.92} />
      <line x1={x} y1={y + s} x2={x + s} y2={y} stroke="#fff" strokeWidth={4} />
      <text x={x + s * 0.3} y={y + s * 0.42} textAnchor="middle" fontSize={30} fontWeight={900}
            fill="#fff" fontFamily={font}>{sym(t.left)}</text>
      <text x={x + s * 0.7} y={y + s * 0.86} textAnchor="middle" fontSize={30} fontWeight={900}
            fill="#fff" fontFamily={font}>{sym(t.right)}</text>
    </g>
  );
}

function MarkerMasks({ W, H, size }: { W: number; H: number; size: number }) {
  // Projector emits no light here so the physical ArUco corner markers stay readable.
  return (
    <g fill="#000">
      <rect x={0} y={0} width={size} height={size} />
      <rect x={W - size} y={0} width={size} height={size} />
      <rect x={W - size} y={H - size} width={size} height={size} />
      <rect x={0} y={H - size} width={size} height={size} />
    </g>
  );
}

function TestPattern({ puzzle, width, height }: { puzzle: Puzzle; width?: number | string; height?: number | string }) {
  const W = puzzle.cols * CELL, H = puzzle.rows * CELL;
  const L = 40;
  const corner = (x: number, y: number, dx: number, dy: number, label: string) => (
    <g key={label}>
      <path d={`M${x + dx * L},${y} L${x},${y} L${x},${y + dy * L}`} stroke="#facc15" strokeWidth={8} fill="none" />
      <text x={x + dx * 50} y={y + dy * 60 + (dy > 0 ? 0 : 20)} fill="#facc15" fontSize={26} fontWeight={800}
            textAnchor={dx > 0 ? 'start' : 'end'} fontFamily="system-ui">{label}</text>
    </g>
  );
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={width ?? W} height={height ?? H} style={{ display: 'block' }}>
      <rect width={W} height={H} fill="#000" />
      <g stroke="#fff" strokeWidth={3}>
        {Array.from({ length: puzzle.cols + 1 }, (_, i) => <line key={`v${i}`} x1={i * CELL} y1={0} x2={i * CELL} y2={H} />)}
        {Array.from({ length: puzzle.rows + 1 }, (_, i) => <line key={`h${i}`} x1={0} y1={i * CELL} x2={W} y2={i * CELL} />)}
      </g>
      <rect x={4} y={4} width={W - 8} height={H - 8} fill="none" stroke="#22d3ee" strokeWidth={8} />
      <line x1={W / 2 - 30} y1={H / 2} x2={W / 2 + 30} y2={H / 2} stroke="#f0f" strokeWidth={4} />
      <line x1={W / 2} y1={H / 2 - 30} x2={W / 2} y2={H / 2 + 30} stroke="#f0f" strokeWidth={4} />
      {corner(0, 0, 1, 1, 'TL')}{corner(W, 0, -1, 1, 'TR')}{corner(W, H, -1, -1, 'BR')}{corner(0, H, 1, -1, 'BL')}
      {Array.from({ length: puzzle.rows }, (_, r) => Array.from({ length: puzzle.cols }, (_, c) => (
        (r === 0 || r === puzzle.rows - 1) && (c === 0 || c === puzzle.cols - 1) ? null :
        <text key={`${r}-${c}`} x={c * CELL + CELL / 2} y={r * CELL + CELL / 2 + 8} fill="#888" fontSize={20}
              textAnchor="middle" fontFamily="system-ui">{r},{c}</text>
      )))}
    </svg>
  );
}
