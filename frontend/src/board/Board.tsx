import type { Cell, Puzzle, RobotPose, TileState } from '../api/types';
import { cellKey, sameCell } from '../api/types';
import { THEMES } from './themes';

export const CELL = 100; // canonical board pixels per cell (projection warps this whole layer)

export const FEEDBACK = { correct: '#16a34a', incorrect: '#dc2626' };

type Props = {
  puzzle: Puzzle;
  tiles?: Record<string, TileState>;
  pose?: RobotPose | null;
  plannedEntries?: Cell[];
  theme?: string;
  showGrid?: boolean;
  showIndices?: boolean;
  showRobot?: boolean;
  markerMask?: number;        // fraction of a cell kept black at each corner (projection)
  testPattern?: boolean;
  highlight?: Cell[];         // editor: cells to outline
  onCellClick?: (c: Cell) => void;
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
  const theme = THEMES[p.theme ?? 'city'] ?? THEMES.city;

  if (p.testPattern) return <TestPattern puzzle={puzzle} width={p.width} height={p.height} />;

  const route = [puzzle.startCell, ...puzzle.targetEntries];
  const routePts = route.map((c) => center(c).join(',')).join(' ');
  const routeSet = new Set(route.map(cellKey));
  const indexLabels = new Map<string, number[]>();
  puzzle.targetEntries.forEach((c, i) => {
    const k = cellKey(c);
    indexLabels.set(k, [...(indexLabels.get(k) ?? []), i + 1]);
  });

  const cells: Cell[] = [];
  for (let r = 0; r < puzzle.rows; r++) for (let c = 0; c < puzzle.cols; c++) cells.push({ row: r, col: c });

  return (
    <svg
      className={p.className}
      viewBox={`0 0 ${W} ${H}`}
      width={p.width ?? W}
      height={p.height ?? H}
      preserveAspectRatio="xMidYMid meet"
      style={{ display: 'block' }}
    >
      {/* Layer 1: decorative background artwork (prepared theme; AI artwork slots in here) */}
      <rect width={W} height={H} fill={theme.ground} />
      {cells.map((c) => {
        const k = cellKey(c);
        const scenery = puzzle.sceneryCells.some((s) => sameCell(s, c));
        if (routeSet.has(k)) return null;
        return (
          <g key={`bg${k}`} transform={`translate(${c.col * CELL},${c.row * CELL})`}>
            <rect x={3} y={3} width={CELL - 6} height={CELL - 6} rx={10} fill={theme.tile} />
            {scenery && theme.scenery(c)}
          </g>
        );
      })}

      {/* Layer 2: exact route cues + grid (app-rendered, never derived from artwork) */}
      {[...new Map(route.map((c) => [cellKey(c), c] as const)).values()].map((c) => (
        <rect key={`rt${cellKey(c)}`} x={c.col * CELL + 2} y={c.row * CELL + 2}
              width={CELL - 4} height={CELL - 4} rx={8} fill={theme.routeTile} />
      ))}
      <polyline points={routePts} fill="none" stroke={theme.road} strokeWidth={34}
                strokeLinejoin="round" strokeLinecap="round" />
      <polyline points={routePts} fill="none" stroke={theme.roadLine} strokeWidth={4}
                strokeDasharray="14 12" strokeLinejoin="round" strokeLinecap="round" />
      {(p.showGrid ?? true) && (
        <g stroke={theme.grid} strokeWidth={2}>
          {Array.from({ length: puzzle.cols + 1 }, (_, i) => (
            <line key={`v${i}`} x1={i * CELL} y1={0} x2={i * CELL} y2={H} />
          ))}
          {Array.from({ length: puzzle.rows + 1 }, (_, i) => (
            <line key={`h${i}`} x1={0} y1={i * CELL} x2={W} y2={i * CELL} />
          ))}
        </g>
      )}

      {/* Layer 3: start / goal indicators and labels */}
      <g transform={`translate(${center(puzzle.startCell).join(',')})`}>
        <circle r={30} fill={theme.start} stroke="#fff" strokeWidth={5} />
        <path d="M0,-22 L13,6 L0,0 L-13,6 Z" fill="#fff"
              transform={`rotate(${HEADING_ROT[puzzle.startHeading]})`} />
      </g>
      <g transform={`translate(${center(puzzle.goalCell).join(',')})`}>
        <circle r={32} fill="#fff" />
        <circle r={24} fill={theme.goal} />
        <circle r={14} fill="#fff" />
        <circle r={7} fill={theme.goal} />
      </g>
      {(p.showIndices ?? true) && [...indexLabels].map(([k, idx]) => {
        const [r, c] = k.split(',').map(Number);
        return (
          <text key={`ix${k}`} x={c * CELL + 8} y={r * CELL + 22} fontSize={18} fontWeight={700}
                fill={theme.label} fontFamily="system-ui, sans-serif">{idx.join(',')}</text>
        );
      })}

      {/* Layer 4: live correctness feedback (always on top, symbols + colour) */}
      {p.tiles && Object.entries(p.tiles).map(([k, t]) => <FeedbackTile key={`fb${k}`} k={k} t={t} />)}

      {p.plannedEntries && p.plannedEntries.length > 0 && (
        <polyline points={[puzzle.startCell, ...p.plannedEntries].map((c) => center(c).join(',')).join(' ')}
                  fill="none" stroke="#2563eb" strokeWidth={6} strokeDasharray="4 10"
                  strokeLinecap="round" strokeLinejoin="round" opacity={0.9} />
      )}

      {p.highlight?.map((c, i) => (
        <rect key={`hl${i}`} x={c.col * CELL + 6} y={c.row * CELL + 6} width={CELL - 12} height={CELL - 12}
              fill="none" stroke="#f59e0b" strokeWidth={6} rx={10} />
      ))}

      {(p.showRobot ?? true) && p.pose && <RobotGlyph pose={p.pose} />}

      {p.markerMask ? <MarkerMasks W={W} H={H} size={p.markerMask * CELL} /> : null}

      {p.onCellClick && cells.map((c) => (
        <rect key={`hit${cellKey(c)}`} x={c.col * CELL} y={c.row * CELL} width={CELL} height={CELL}
              fill="transparent" style={{ cursor: 'pointer' }} onClick={() => p.onCellClick!(c)} />
      ))}
    </svg>
  );
}

function FeedbackTile({ k, t }: { k: string; t: TileState }) {
  if (t.kind === 'unvisited') return null;
  const [r, c] = k.split(',').map(Number);
  const x = c * CELL, y = r * CELL, s = CELL;
  const col = (ok: boolean | null) => (ok ? FEEDBACK.correct : FEEDBACK.incorrect);
  const sym = (ok: boolean | null) => (ok ? '✓' : '✗');
  if (t.kind === 'solid') {
    return (
      <g>
        <rect x={x + 2} y={y + 2} width={s - 4} height={s - 4} fill={col(t.left)} opacity={0.88}
              stroke="#fff" strokeWidth={4} />
        <text x={x + s / 2} y={y + s / 2 + 16} textAnchor="middle" fontSize={46} fontWeight={900}
              fill="#fff" fontFamily="system-ui, sans-serif">{sym(t.left)}</text>
      </g>
    );
  }
  // split: diagonal from bottom-left to top-right. Left triangle touches top-left (FIRST),
  // right triangle touches bottom-right (LATEST).
  return (
    <g>
      <polygon points={`${x},${y} ${x + s},${y} ${x},${y + s}`} fill={col(t.left)} opacity={0.9} />
      <polygon points={`${x + s},${y} ${x + s},${y + s} ${x},${y + s}`} fill={col(t.right)} opacity={0.9} />
      <line x1={x} y1={y + s} x2={x + s} y2={y} stroke="#fff" strokeWidth={4} />
      <rect x={x + 2} y={y + 2} width={s - 4} height={s - 4} fill="none" stroke="#fff" strokeWidth={4} />
      <text x={x + s * 0.3} y={y + s * 0.42} textAnchor="middle" fontSize={30} fontWeight={900}
            fill="#fff" fontFamily="system-ui, sans-serif">{sym(t.left)}</text>
      <text x={x + s * 0.7} y={y + s * 0.86} textAnchor="middle" fontSize={30} fontWeight={900}
            fill="#fff" fontFamily="system-ui, sans-serif">{sym(t.right)}</text>
    </g>
  );
}

function RobotGlyph({ pose }: { pose: RobotPose }) {
  const x = pose.x * CELL, y = pose.y * CELL;
  const stale = !pose.trackingValid;
  return (
    <g transform={`translate(${x},${y}) rotate(${pose.headingDeg})`} opacity={stale ? 0.45 : 1}>
      <rect x={-26} y={-30} width={52} height={60} rx={10} fill={stale ? '#9ca3af' : '#1d4ed8'}
            stroke="#fff" strokeWidth={4} strokeDasharray={stale ? '6 6' : undefined} />
      <path d="M0,-24 L14,0 L-14,0 Z" fill="#fff" />
      {stale && <text y={22} textAnchor="middle" fontSize={22} fill="#fff" transform="rotate(0)">?</text>}
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
