/** Top-down black rover, drawn centred on (0,0) and facing up (-y) at rotation 0. ~60x74 units. */
export function Rover({ stale = false }: { stale?: boolean }) {
  const body = stale ? '#6b7280' : '#121417';
  const wheel = stale ? '#9ca3af' : '#2a2e35';
  return (
    <g>
      <ellipse cx={0} cy={6} rx={34} ry={40} fill="#000" opacity={0.18} />
      {[-24, 0, 24].map((y) => (
        <g key={y}>
          <rect x={-33} y={y - 9} width={12} height={18} rx={4} fill={wheel} />
          <rect x={21} y={y - 9} width={12} height={18} rx={4} fill={wheel} />
          <line x1={-31} y1={y - 4} x2={-23} y2={y - 4} stroke="#4b5563" strokeWidth={2} />
          <line x1={23} y1={y - 4} x2={31} y2={y - 4} stroke="#4b5563" strokeWidth={2} />
        </g>
      ))}
      <rect x={-23} y={-32} width={46} height={64} rx={12} fill={body}
            stroke={stale ? '#9ca3af' : '#000'} strokeWidth={2} strokeDasharray={stale ? '5 4' : undefined} />
      {/* solar deck */}
      <rect x={-16} y={-6} width={32} height={30} rx={4} fill={stale ? '#9ca3af' : '#1f2937'} />
      {[-2, 6, 14].map((y) => <line key={y} x1={-16} y1={y} x2={16} y2={y} stroke="#374151" strokeWidth={1.5} />)}
      <line x1={0} y1={-6} x2={0} y2={24} stroke="#374151" strokeWidth={1.5} />
      {/* gloss */}
      <path d="M-19,-26 Q-19,-30 -14,-30 L10,-30" stroke="#fff" strokeOpacity={0.35} strokeWidth={3}
            strokeLinecap="round" fill="none" />
      {/* camera head at the front */}
      <rect x={-11} y={-30} width={22} height={16} rx={5} fill={stale ? '#9ca3af' : '#000'} />
      <circle cx={-5} cy={-22} r={3.6} fill={stale ? '#e5e7eb' : '#9cc3f0'} />
      <circle cx={5} cy={-22} r={3.6} fill={stale ? '#e5e7eb' : '#9cc3f0'} />
      <path d="M0,-44 L7,-35 L-7,-35 Z" fill={stale ? '#9ca3af' : '#121417'} />
      {stale && <text y={12} textAnchor="middle" fontSize={22} fontWeight={800} fill="#fff">?</text>}
    </g>
  );
}

/** Standalone SVG rover for UI chrome (logo, legends). */
export function RoverIcon({ size = 28, heading = 0 }: { size?: number; heading?: number }) {
  return (
    <svg width={size} height={size} viewBox="-46 -50 92 100" aria-hidden>
      <g transform={`rotate(${heading})`}><Rover /></g>
    </svg>
  );
}
