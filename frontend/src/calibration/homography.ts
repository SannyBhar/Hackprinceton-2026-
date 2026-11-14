/** 4-point perspective mapping for projector keystone correction.
 *
 * The whole board (artwork, route, feedback, labels) is rendered once in canonical
 * board pixels, then this homography warps the entire layer onto the quadrilateral
 * the instructor dragged on the projector output. Projector pixels are never game
 * coordinates; they only exist here.
 */
export type Pt = [number, number];

/** Solve H (row-major 3x3, h[8] = 1) with H * src[i] ~ dst[i] for 4 point pairs. */
export function solveHomography(src: Pt[], dst: Pt[]): number[] {
  if (src.length !== 4 || dst.length !== 4) throw new Error('need 4 point pairs');
  const A: number[][] = [];
  const b: number[] = [];
  for (let i = 0; i < 4; i++) {
    const [x, y] = src[i];
    const [u, v] = dst[i];
    A.push([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.push(u);
    A.push([0, 0, 0, x, y, 1, -v * x, -v * y]); b.push(v);
  }
  const h = gaussSolve(A, b);
  return [...h, 1];
}

function gaussSolve(A: number[][], b: number[]): number[] {
  const n = b.length;
  const M = A.map((row, i) => [...row, b[i]]);
  for (let c = 0; c < n; c++) {
    let p = c;
    for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r;
    if (Math.abs(M[p][c]) < 1e-12) throw new Error('degenerate corner layout');
    [M[c], M[p]] = [M[p], M[c]];
    for (let r = 0; r < n; r++) {
      if (r === c) continue;
      const f = M[r][c] / M[c][c];
      for (let k = c; k <= n; k++) M[r][k] -= f * M[c][k];
    }
  }
  return M.map((row, i) => row[n] / row[i]);
}

export function applyH(h: number[], [x, y]: Pt): Pt {
  const w = h[6] * x + h[7] * y + h[8];
  return [(h[0] * x + h[1] * y + h[2]) / w, (h[3] * x + h[4] * y + h[5]) / w];
}

/** Homography from the rectangle (0,0)-(w,h) [TL,TR,BR,BL] onto dst. */
export function rectToQuad(w: number, h: number, dst: Pt[]): number[] {
  return solveHomography([[0, 0], [w, 0], [w, h], [0, h]], dst);
}

/** CSS matrix3d (column-major 4x4) for an element with transform-origin: 0 0. */
export function toMatrix3d(h: number[]): string {
  const m = [h[0], h[3], 0, h[6], h[1], h[4], 0, h[7], 0, 0, 1, 0, h[2], h[5], 0, h[8]];
  return `matrix3d(${m.map((v) => +v.toFixed(10)).join(',')})`;
}

/** Corners must form a convex quad in TL,TR,BR,BL (clockwise on screen) order. */
export function isConvexClockwise(q: Pt[]): boolean {
  let sign = 0;
  for (let i = 0; i < 4; i++) {
    const [ax, ay] = q[i];
    const [bx, by] = q[(i + 1) % 4];
    const [cx, cy] = q[(i + 2) % 4];
    const cross = (bx - ax) * (cy - by) - (by - ay) * (cx - bx);
    if (Math.abs(cross) < 1e-9) return false;
    const s = Math.sign(cross);
    if (sign === 0) sign = s;
    else if (s !== sign) return false;
  }
  return sign > 0; // screen coords (y down): clockwise => positive cross
}
