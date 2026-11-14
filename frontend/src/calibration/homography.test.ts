import { describe, expect, it } from 'vitest';
import { applyH, isConvexClockwise, rectToQuad, toMatrix3d, type Pt } from './homography';

const close = (a: Pt, b: Pt) => {
  expect(a[0]).toBeCloseTo(b[0], 6);
  expect(a[1]).toBeCloseTo(b[1], 6);
};

describe('homography', () => {
  const dst: Pt[] = [[210, 95], [1650, 140], [1720, 1010], [160, 960]];
  const H = rectToQuad(600, 500, dst);

  it('maps board corners exactly onto the dragged quad', () => {
    close(applyH(H, [0, 0]), dst[0]);
    close(applyH(H, [600, 0]), dst[1]);
    close(applyH(H, [600, 500]), dst[2]);
    close(applyH(H, [0, 500]), dst[3]);
  });

  it('is a true perspective map, not bilinear (centre = diagonal intersection)', () => {
    const [p0, p1, p2, p3] = dst;
    // intersection of diagonals p0-p2 and p1-p3
    const d = (p0[0] - p2[0]) * (p1[1] - p3[1]) - (p0[1] - p2[1]) * (p1[0] - p3[0]);
    const a = p0[0] * p2[1] - p0[1] * p2[0];
    const b = p1[0] * p3[1] - p1[1] * p3[0];
    const X: Pt = [(a * (p1[0] - p3[0]) - (p0[0] - p2[0]) * b) / d, (a * (p1[1] - p3[1]) - (p0[1] - p2[1]) * b) / d];
    close(applyH(H, [300, 250]), X);
  });

  it('identity rectangle yields identity matrix3d', () => {
    const I = rectToQuad(100, 50, [[0, 0], [100, 0], [100, 50], [0, 50]]);
    expect(toMatrix3d(I)).toBe('matrix3d(1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1)');
  });

  it('detects crossed / mis-ordered handles', () => {
    expect(isConvexClockwise(dst)).toBe(true);
    expect(isConvexClockwise([dst[0], dst[2], dst[1], dst[3]])).toBe(false);
  });
});
