import type {
  ThemeJob, ProgressReport, Recommendation, Attempt, Recording, Student, Cell, Instruction, ProjectionSettings, ProjectorCalibration, Puzzle, PuzzleListItem, ScanResult,
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
  hardwareCalibration: (body:{action:'wheel'|'translation'|'turn';wheel:number;duty:number;durationMs:number;confirmed:boolean}) => call<{status:string;error?:string}>('POST','/api/hardware/calibration',body),
  themes: () => call<ThemeJob[]>('GET','/api/themes'),
  generateTheme: (text:string) => call<ThemeJob>('POST','/api/themes',{text}),
  acceptTheme: (id:string) => call('POST',`/api/themes/${encodeURIComponent(id)}/accept`),
  cancelTheme: (id:string) => call('DELETE',`/api/themes/${encodeURIComponent(id)}`),
  progress: (id:string) => call<ProgressReport>('GET',`/api/students/${encodeURIComponent(id)}/progress`),
  recommendations: (id:string) => call<Recommendation[]>('GET',`/api/students/${encodeURIComponent(id)}/recommendations`),
  annotateSkill: (id:string,skill:string,correct:boolean) => call('POST',`/api/attempts/${encodeURIComponent(id)}/evidence`,{skill,correct}),
  students: () => call<Student[]>('GET','/api/students'),
  createStudent: (name:string) => call<Student>('POST','/api/students',{name}),
  selectStudent: (studentId:string|null) => call('PUT','/api/student',{studentId}),
  attempts: (studentId?:string) => call<Attempt[]>('GET','/api/attempts'+(studentId?'?studentId='+encodeURIComponent(studentId):'')),
  setRecordingGrade: (grade:boolean) => call('PUT','/api/recording/options',{grade}),
  recordings: () => call<Recording[]>('GET','/api/recordings'),
  importRecording: (record:unknown) => call('POST','/api/recordings/import',record),
  confirmRecording: (id:string,reviewed:boolean) => call('POST',`/api/recordings/${encodeURIComponent(id)}/confirm`,{reviewed}),
  joystickSample: (sample:{protocolVersion:number;seq:number;timestampMs:number;x:number;y:number;button:boolean}) => call('POST','/api/joystick/sample',sample),
  puzzles: () => call<PuzzleListItem[]>('GET', '/api/puzzles'),
  /** Save AND make it the active puzzle on the board. */
  savePuzzle: (p: Puzzle) => call<Puzzle>('PUT', '/api/puzzle', p),
  /** Save to the library only (not allowed for the active puzzle). */
  savePuzzleOnly: (p: Puzzle) => call<Puzzle>('POST', '/api/puzzles', p),
  deletePuzzle: (id: string) => call<{ result: 'deleted' | 'reverted' }>('DELETE', `/api/puzzles/${encodeURIComponent(id)}`),
  saveCalibration: (c: ProjectorCalibration) => call('PUT', '/api/calibration/projector', c),
  setProjection: (p: ProjectionSettings) => call('PUT', '/api/projection', p),
  cameraRole: (role: 'scan' | 'track' | 'closed') => call('POST', '/api/camera/role', { role }),
  calibrateCamera: (heightCorrection=0) => call('POST', '/api/calibration/camera',{heightCorrection}),
  clearScan: () => call('DELETE', '/api/scan'),
  scan: () => call<ScanResult>('POST', '/api/scan'),
  validate: (instructions: Instruction[]) =>
    call<{ ok: boolean; errors: string[]; plannedEntries: Cell[] }>('POST', '/api/program/validate', { instructions }),
  confirm: (instructions: Instruction[], scanId?: string, reviewed = false) => call('POST', '/api/program/confirm', { instructions, scanId, reviewed }),
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
