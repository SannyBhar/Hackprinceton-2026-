import type {
  Instruction, ProjectionSettings, ProjectorCalibration, Puzzle, ScanResult,
} from './types';

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = (data as { detail?: unknown }).detail;
    throw new Error(typeof d === 'string' ? d : JSON.stringify(d ?? res.statusText));
  }
  return data as T;
}

export const api = {
  puzzles: () => call<Puzzle[]>('GET', '/api/puzzles'),
  savePuzzle: (p: Puzzle) => call<Puzzle>('PUT', '/api/puzzle', p),
  saveCalibration: (c: ProjectorCalibration) => call('PUT', '/api/calibration/projector', c),
  setProjection: (p: ProjectionSettings) => call('PUT', '/api/projection', p),
  scan: () => call<ScanResult>('POST', '/api/scan'),
  validate: (instructions: Instruction[]) =>
    call<{ ok: boolean; errors: string[] }>('POST', '/api/program/validate', { instructions }),
  confirm: (instructions: Instruction[]) => call('POST', '/api/program/confirm', { instructions }),
  run: () => call('POST', '/api/run'),
  stop: () => call('POST', '/api/stop'),
  reset: () => call('POST', '/api/reset'),
  toggleRecording: (grade = false, source: 'ui' | 'joystick' = 'ui') =>
    call('POST', '/api/recording/toggle', { grade, source }),
  recordAction: (action: 'FORWARD' | 'BACKWARD' | 'LEFT' | 'RIGHT') =>
    call<{ accepted: boolean }>('POST', '/api/recording/action', { action }),
  simFault: (f: { lateralDrift?: number; trackingLossMs?: number; linkUp?: boolean }) =>
    call('POST', '/api/sim/fault', f),
};
