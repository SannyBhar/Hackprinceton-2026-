import type { ReactNode } from 'react';
import type { Cell } from '../api/types';

/** Prepared, offline board themes. AI-generated artwork (later milestone) replaces only the
 * background layer; these remain the instant fallback. Palettes avoid saturated green/red so
 * the board never resembles grading feedback. */
export type Theme = {
  name: string;
  ground: string;                  // shows through the gaps between tiles = grid lines
  tileTop: string; tileBottom: string; tileStroke: string;
  routeTop: string; routeBottom: string;
  gloss: number;                   // 0..1 strength of the glossy highlight
  road: string; roadLine: string;
  start: string; goal: string;
  badgeBg: string; badgeFg: string;
  scenery: (c: Cell) => ReactNode; // drawn inside a 100x100 cell
};

const rock = (c: Cell) => {
  const v = (c.row * 7 + c.col * 13) % 3;
  return (
    <g opacity={0.9}>
      <ellipse cx={50} cy={64} rx={30} ry={8} fill="#000" opacity={0.08} />
      <path d={v === 0 ? 'M24,62 Q30,34 50,32 Q72,30 76,60 Q60,70 24,62Z'
        : v === 1 ? 'M28,64 Q26,42 44,38 Q54,26 68,40 Q80,52 72,64Z'
        : 'M30,62 Q34,40 52,40 Q70,42 70,62Z'} fill="#a9b8cc" />
      <path d={v === 0 ? 'M34,46 Q44,38 56,40' : 'M38,48 Q46,42 56,44'} stroke="#fff" strokeWidth={4}
            strokeLinecap="round" fill="none" opacity={0.7} />
    </g>
  );
};

const building = (c: Cell) => {
  const h = 40 + ((c.row * 7 + c.col * 13) % 3) * 12;
  return (
    <g>
      <rect x={24} y={86 - h} width={52} height={h} rx={4} fill="#64748b" />
      {[0, 1, 2].map((i) => <rect key={i} x={32 + i * 14} y={92 - h} width={8} height={8} fill="#fde68a" />)}
    </g>
  );
};

const planet = (c: Cell) => (
  <g>
    <circle cx={50} cy={50} r={22} fill={(c.row + c.col) % 2 ? '#a78bfa' : '#38bdf8'} />
    <ellipse cx={50} cy={50} rx={36} ry={9} fill="none" stroke="#e0e7ff" strokeWidth={4} />
  </g>
);

export const THEMES: Record<string, Theme> = {
  glossy: {
    // Deep slate-blue grid lines: strong contrast against white tiles, still visible when
    // washed out by a projector (black would project as "no light" and vanish).
    name: 'Glossy white', ground: '#25406a',
    tileTop: '#ffffff', tileBottom: '#e9eef5', tileStroke: '#34568a',
    routeTop: '#fffdf4', routeBottom: '#fbf1cf', gloss: 0.9,
    road: '#f5c400', roadLine: '#ffffff', start: '#5b8fd1', goal: '#111111',
    badgeBg: '#3f6fb5', badgeFg: '#ffffff', scenery: rock,
  },
  city: {
    name: 'City streets', ground: '#94a3b8',
    tileTop: '#eef2f7', tileBottom: '#dbe2ec', tileStroke: '#94a3b8',
    routeTop: '#f8fafc', routeBottom: '#e8edf4', gloss: 0.3,
    road: '#475569', roadLine: '#facc15', start: '#2563eb', goal: '#f97316',
    badgeBg: '#0f172a', badgeFg: '#ffffff', scenery: building,
  },
  space: {
    name: 'Outer space', ground: '#060a1c',
    tileTop: '#1a2147', tileBottom: '#11163a', tileStroke: '#334155',
    routeTop: '#27316a', routeBottom: '#1c2552', gloss: 0.15,
    road: '#6366f1', roadLine: '#e0e7ff', start: '#0ea5e9', goal: '#f59e0b',
    badgeBg: '#e0e7ff', badgeFg: '#0b1026', scenery: planet,
  },
  plain: {
    name: 'High contrast', ground: '#3f3f46',
    tileTop: '#ffffff', tileBottom: '#ffffff', tileStroke: '#3f3f46',
    routeTop: '#f4f4f5', routeBottom: '#f4f4f5', gloss: 0,
    road: '#a1a1aa', roadLine: '#ffffff', start: '#2563eb', goal: '#f97316',
    badgeBg: '#000000', badgeFg: '#ffffff',
    scenery: () => <rect x={22} y={22} width={56} height={56} rx={6} fill="#d4d4d8" />,
  },
};

export const DEFAULT_THEME = 'glossy';
