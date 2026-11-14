import type { ReactNode } from 'react';
import type { Cell } from '../api/types';

/** Prepared, offline fallback themes. AI-generated artwork (milestone 7) replaces only the
 * background layer; these stay available as the instant fallback. Palettes deliberately
 * avoid saturated green/red so artwork never resembles grading feedback. */
export type Theme = {
  name: string;
  ground: string; tile: string; routeTile: string; road: string; roadLine: string;
  grid: string; start: string; goal: string; label: string; // label = index text colour
  scenery: (c: Cell) => ReactNode;
};

const building = (c: Cell) => {
  const h = 40 + ((c.row * 7 + c.col * 13) % 3) * 12;
  return (
    <g>
      <rect x={24} y={86 - h} width={52} height={h} rx={4} fill="#64748b" />
      {[0, 1, 2].map((i) => (
        <rect key={i} x={32 + i * 14} y={92 - h} width={8} height={8} fill="#fde68a" />
      ))}
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
  city: {
    name: 'City streets', ground: '#cbd5e1', tile: '#e2e8f0', routeTile: '#f1f5f9',
    road: '#475569', roadLine: '#facc15', grid: '#94a3b8', start: '#2563eb', goal: '#f97316',
    label: '#0f172a', scenery: building,
  },
  space: {
    name: 'Outer space', ground: '#0b1026', tile: '#141a3a', routeTile: '#1e2752',
    road: '#6366f1', roadLine: '#e0e7ff', grid: '#334155', start: '#0ea5e9', goal: '#f59e0b',
    label: '#e0e7ff', scenery: planet,
  },
  plain: {
    name: 'High contrast', ground: '#ffffff', tile: '#ffffff', routeTile: '#f5f5f4',
    road: '#a8a29e', roadLine: '#ffffff', grid: '#57534e', start: '#2563eb', goal: '#f97316',
    label: '#000000', scenery: () => <rect x={20} y={20} width={60} height={60} fill="#d6d3d1" />,
  },
};
