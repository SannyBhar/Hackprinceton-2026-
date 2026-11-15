import type { Cell, Heading, Instruction } from '../api/types';

const HEADINGS: Heading[] = ['N', 'E', 'S', 'W'];
const VEC: Record<Heading, [number, number]> = { N: [-1, 0], E: [0, 1], S: [1, 0], W: [0, -1] };

export const turnRight = (h: Heading): Heading => HEADINGS[(HEADINGS.indexOf(h) + 1) % 4];

function dirBetween(a: Cell, b: Cell): Heading | null {
  const d: [number, number] = [b.row - a.row, b.col - a.col];
  return (HEADINGS.find((h) => VEC[h][0] === d[0] && VEC[h][1] === d[1]) ?? null);
}

/** One reference card program that drives the ordered route exactly.
 * Uses BACKWARD when the next cell is directly behind (no turn needed), otherwise
 * turns in place and drives FORWARD. Consecutive moves merge up to maxSteps.
 * This is a helper for the instructor, never the grading target. */
export function referenceSolution(start: Cell, heading: Heading, entries: Cell[], maxSteps = 5): Instruction[] {
  const out: Instruction[] = [{ op: 'START' }];
  let h = heading;
  let prev = start;
  const move = (op: 'FORWARD' | 'BACKWARD') => {
    const last = out[out.length - 1];
    if (last.op === op && (last.steps ?? 0) < maxSteps) last.steps = (last.steps ?? 0) + 1;
    else out.push({ op, steps: 1 });
  };
  for (const c of entries) {
    const d = dirBetween(prev, c);
    if (!d) break; // non-adjacent: editor prevents this
    const i = HEADINGS.indexOf(h), j = HEADINGS.indexOf(d);
    const delta = (j - i + 4) % 4;
    if (delta === 0) move('FORWARD');
    else if (delta === 2) move('BACKWARD');
    else {
      out.push({ op: delta === 1 ? 'RIGHT' : 'LEFT' });
      h = d;
      move('FORWARD');
    }
    prev = c;
  }
  out.push({ op: 'STOP' });
  return out;
}
