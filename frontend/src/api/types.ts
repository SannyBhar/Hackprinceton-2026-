// Mirror of backend/app/models.py. Keep in sync.
export type Cell = { row: number; col: number };
export type Heading = 'N' | 'E' | 'S' | 'W';
export type Op = 'START' | 'STOP' | 'LEFT' | 'RIGHT' | 'FORWARD' | 'BACKWARD';
export type Instruction = { op: Op; steps?: number | null; cardId?: number | null };

export type Puzzle = {
  id: string; version: number; name: string;
  rows: number; cols: number;
  startCell: Cell; startHeading: Heading; goalCell: Cell;
  targetEntries: Cell[];
  sceneryCells: Cell[];
};

export type PuzzleListItem = Puzzle & { builtin: boolean; edited: boolean };

export type RobotPose = {
  timestampMs: number; x: number; y: number; headingDeg: number; trackingValid: boolean;
};

export type VisitEvent = {
  attemptId: string; index: number; timestampMs: number;
  actual: Cell; expected: Cell | null; correct: boolean;
};

export type TileState = {
  kind: 'unvisited' | 'solid' | 'split';
  left: boolean | null; right: boolean | null; visits: number;
};

export type SessionState =
  | 'IDLE' | 'SCANNING' | 'PROGRAM_READY' | 'RUNNING' | 'RECORDING' | 'COMPLETED' | 'STOPPED' | 'FAULT';

export type ScannedCard = {
  order: number; cardId: number | null; op: Op | null;
  rawSteps: number | null; stepsConfidence: number | null; markerConfidence: number;
  cropDataUrl: string | null; issues: string[];
};
export type ScanResult = { scanId: string; source: string; cards: ScannedCard[]; errors: string[]; needsReview: boolean };

export type Corner = { x: number; y: number };
export type ProjectorCalibration = {
  corners: Corner[]; viewportWidth: number; viewportHeight: number; markerMask: number; showGrid: boolean;
};
export type ProjectionSettings = {
  calibrating: boolean; testPattern: boolean; activeCorner: number; theme: string; showRobot: boolean;
};

export type AttemptSummary = {
  entries: number; correct: number; incorrect: number; missing: number; extra: number;
  reachedGoal: boolean; success: boolean; details: string[];
};
export type Attempt = {
  id: string; startedAt: number; endedAt?: number; puzzleId: string; puzzleVersion: number;
  program: Instruction[]; instructionIndex: number; events: VisitEvent[]; warnings: string[];
  stopReason: string | null; summary: AttemptSummary | null;
};

export type Recording = {
  actions: { action: Op; observedEntries: Cell[] }[];
  generated: Instruction[] | null; warnings: string[]; path: Cell[];
  startCell?: Cell; graded?: boolean;
};

export type Snapshot = {
  seq: number;
  state: SessionState;
  puzzle: Puzzle;
  calibration: ProjectorCalibration;
  projection: ProjectionSettings;
  scan: ScanResult | null;
  program: Instruction[] | null;
  plannedEntries: Cell[];
  attempt: Attempt | null;
  attemptHistory: Pick<Attempt, 'id' | 'startedAt' | 'stopReason' | 'summary'>[];
  tiles: Record<string, TileState>;
  pose: RobotPose | null;
  robot: { adapter: string; connected: boolean };
  recording: Recording;
  feed: { t: number; level: 'info' | 'warn' | 'error'; msg: string }[];
  tilePolicy: string;
  maxSteps: number;
};

export type WsMessage =
  | { seq: number; type: 'snapshot'; payload: Snapshot }
  | { seq: number; type: 'pose'; payload: RobotPose };

export const cellKey = (c: Cell) => `${c.row},${c.col}`;
export const sameCell = (a: Cell, b: Cell) => a.row === b.row && a.col === b.col;
