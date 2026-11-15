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
  artworkId?: string | null; artworkHash?: string | null;
  calibrating: boolean; testPattern: boolean; activeCorner: number; theme: string; showRobot: boolean;
};

export type AttemptSummary = {
  entries: number; correct: number; incorrect: number; missing: number; extra: number;
  reachedGoal: boolean; success: boolean; details: string[];
};
export type Attempt = {
  source?: string;
  id: string; mode?: 'manual'; startedAt: number; endedAt?: number; puzzleId: string; puzzleVersion: number;
  program: Instruction[]; instructionIndex: number; events: VisitEvent[]; warnings: string[];
  stopReason: string | null; summary: AttemptSummary | null;
};

export type Student = { id: string; name: string; synthetic: boolean };
export type Recording = {
  id?: string; approximate?: boolean; mode?: string;
  actions: { action: Op; observedEntries: Cell[] }[];
  generated: Instruction[] | null; warnings: string[]; path: Cell[];
  startCell?: Cell; graded?: boolean;
};

/** Shared webcam used for card scanning (vision/coordinator.py). */
export type CameraStatus = { role: string; error: string | null; resolution: number[] | null; timestampMs: number; index: number };

export type Snapshot = {
  studentId: string | null;
  joystick: {active:boolean;error:string|null;connected?:boolean;armed?:boolean;fresh?:boolean;ageMs?:number|null;protocolVersion?:number|null;source?:string|null};
  deviceOperation?: string | null;
  sessionId: string;
  camera: CameraStatus | null;
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
  robot: { adapter: string; connected: boolean; continuousSupported?: boolean; readiness?: {ready:boolean;mode?:string;error?:string|null;remainingCommands?:number;profileId?:string;outputsEnabled?:boolean;calibrated?:boolean} };
  recording: Recording;
  feed: { t: number; level: 'info' | 'warn' | 'error'; msg: string }[];
  poseSource: 'robot' | 'camera';
  boardCamera: BoardCameraStatus | null;
  tilePolicy: string;
  maxSteps: number;
};

/** Markerless overhead-camera tracking (board_camera.py). */
export type BoardCameraStatus = {
  cameraIndex: number | null; running: boolean; tracking: boolean; error: string | null;
  fps: number; latencyMs: number; frameSize: [number, number] | null;
  calibrated: boolean; calibratedAt: number | null;
  boardToImage: number[] | null;   // 3x3 row-major: board (0..1) -> camera image (0..1)
  detection: {
    found: boolean; reason?: string | null; x?: number | null; y?: number | null;
    area?: number | null; runnerUp?: number | null; bbox?: number[] | null;
  };
};

export type WsMessage =
  | { seq: number; type: 'snapshot'; payload: Snapshot }
  | { seq: number; type: 'pose'; payload: RobotPose };

export const cellKey = (c: Cell) => `${c.row},${c.col}`;
export const sameCell = (a: Cell, b: Cell) => a.row === b.row && a.col === b.col;

export type ThemeJob = {id:string;status:string;themeText:string;error:string|null;url?:string;accepted:boolean;puzzleHash:string};
export type SkillEstimate = {skill:string;estimate:number;evidenceCount:number;uncertain:boolean};
export type ProgressReport = {studentId:string;synthetic:boolean;skills:SkillEstimate[];trend:{attemptId:string;startedAt:number;correct:number;entries:number}[];excludedOperationalOrUnattributed:number;limitations:string};
export type Recommendation = {puzzle:Puzzle;skill:string;explanation:string;uncertain:boolean};
