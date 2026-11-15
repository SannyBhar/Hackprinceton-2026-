import { expect, it } from 'vitest';
import { referenceSolution } from './solve';
import { keystone } from '../calibration/CalibrationPad';
it('reference cards retain reverse motion, heading, and card distance limits', () => {
  const p = referenceSolution({row:2,col:0}, 'N', [{row:1,col:0},{row:2,col:0},{row:2,col:1}]);
  expect(p.map(i => [i.op,i.steps])).toEqual([['START',undefined],['FORWARD',1],['BACKWARD',1],['RIGHT',undefined],['FORWARD',1],['STOP',undefined]]);
});
it('calibration keystone preserves the near edge and corner order', () => {
  const p = [{x:0,y:0},{x:1,y:0},{x:1,y:1},{x:0,y:1}];
  expect(keystone(p,.2)).toEqual([{x:.1,y:0},{x:.9,y:0},p[2],p[3]]);
});
