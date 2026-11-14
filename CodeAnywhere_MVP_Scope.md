# CodeAnywhere — MVP Scope and Agent Implementation Brief

Status: agreed product scope plus explicitly labeled implementation defaults. No implementation or hardware purchases are assumed complete.

## 1. Purpose and audience

Build an instructor-operated educational robotics platform for students in grades 2–4. Students arrange physical coding cards to program a robot on a physical grid. An instructor webapp reads the cards, runs the robot, tracks its movement, and displays feedback through a conventional projector. A second mode records joystick demonstrations and generates corresponding coding blocks.

Teach sequencing, movement parameters, spatial reasoning, prediction, and debugging. No loops in this MVP.

Context: 72-hour hackathon; team includes two mechanical engineers; low-end 3D printer available. Education is the primary track. Physical AI and practical AI are potential additional fits, but do not add unnecessary AI dependencies to deterministic execution or grading.

## 2. Non-negotiable product behavior

- The app is primarily for instructors. It owns puzzle setup, calibration, scanning, execution controls, recording, and review.
- Students use physical cards with ArUco markers. FORWARD and BACKWARD cards have a box for handwritten integer step counts.
- Supported cards: START, FORWARD, BACKWARD, LEFT, RIGHT, STOP.
- The target solution is an ordered sequence of cells, not a set of allowed tiles.
- Grade each observed cell entry against the target entry at the same sequence index.
- A wrong entry does not stop execution and does not automatically make subsequent entries wrong.
- The robot executes its full program subject to board bounds, explicit stop, and operational safeguards.
- Revisits retain correctness history and can produce diagonally split tile colors.
- The projector has no control API. It displays the app's fullscreen projection view through ordinary video output/mirroring. All warping and coloring happen in the app.
- Four physical corner markers establish the board frame. The instructor manually aligns four projected corners in the app.
- Game logic uses grid coordinates, not centimeters. Low-level robot movement still requires calibration or camera feedback.

## 3. Instructor workflow

### Setup

1. Connect the camera(s), projector, robot, and joystick.
2. Set grid rows/columns and identify the four physical corners.
3. Calibrate camera-to-grid mapping and projector rendering separately.
4. Create or load a puzzle: start cell, start heading, ordered target path, goal, and optional visual maze features.
5. Open the fullscreen board view on the projector.

### Programming mode

1. Present the physical/projected maze and intended route to the child.
2. Child arranges cards in order and writes step counts.
3. Instructor scans a stable image and reviews recognized commands and numbers.
4. Require correction/confirmation for ambiguous input; never guess a motion parameter silently.
5. Freeze the confirmed program and puzzle version when Run begins.
6. Execute the program; observe actual cell entries; grade and project feedback live.
7. Continue through wrong entries. Finish on STOP/program completion, unless a boundary or operational stop occurs.
8. Review the attempt and reset for another try.

### Reverse engineering mode

1. Instructor selects recording mode.
2. First joystick-button click begins recording.
3. Child drives a route; record joystick actions, observed position, heading, and stable cell transitions.
4. Second click stops the robot and ends recording.
5. Generate a corresponding block program, including START/STOP and compressed consecutive translations.
6. Display/export generated blocks for comparison or reconstruction using physical cards.

Recording describes the demonstrated route. It is not necessarily the shortest or only solution. Do not invent an ordered grading target in free recording mode; optional grading is available when the instructor supplies a target.

## 4. Coordinates and command semantics

Recommended implementation defaults (configurable, not additional user-confirmed requirements):

- Cell coordinates: `{row, col}`, zero-indexed; row increases downward, col rightward in the instructor's canonical board view.
- Continuous tracking: `{x, y}` in cell units; cell centers are `(col + 0.5, row + 0.5)`.
- Headings: N, E, S, W, with a continuous heading estimate retained for tracking/control.
- FORWARD/BACKWARD n: translate n cells relative to current robot heading.
- LEFT/RIGHT: rotate 90 degrees in place. Turns do not increment the cell-entry grading index.
- START marks the beginning of a valid program; execution still requires instructor Run confirmation.
- STOP ends the program. Require exactly one START first and one STOP last for the initial parser.
- Initially accept step counts 1–5 through a configurable validation limit. No negative, fractional, blank, or unconfirmed values.
- No sideways mecanum commands, loops, conditions, functions, or arbitrary-angle turns in the MVP.

## 5. Ordered correctness algorithm

Store `startCell` separately. `targetEntries` contains every expected cell AFTER leaving the start, including repeated coordinates. `actualEntries` contains observed stable cell transitions after execution starts. Do not count the initial stationary start detection.

For each new stable cell entry at index i:

```text
correct = i < targetEntries.length AND actualEntries[i] == targetEntries[i]
append VisitEvent(index=i, actualCell, expectedCellOrNull, correct)
update that physical cell's rendering history
increment i regardless of correctness
```

Example (letters are symbolic cells for grading illustration):

| Index | Target | Actual | Result |
| --- | --- | --- | --- |
| 0 | A | A | Green |
| 1 | B | C | Red |
| 2 | C | B | Red |
| 3 | D | D | Green |

- Never hold the target pointer until the robot recovers.
- Never latch all remaining entries red after the first error.
- Extra entries after the target ends are red.
- Missing target entries remain incomplete; do not fabricate observed visits.
- A multi-cell FORWARD command generates one visit per entered cell, not one per card.
- Repeated camera frames in one cell are not revisits. Leaving and re-entering is a revisit.
- If tracking skips cells or becomes uncertain, mark tracking uncertainty and pause operationally if needed. Do not fabricate camera-confirmed entries.
- Recommended completion default: success requires exact ordered entry match, complete target traversal, expected final cell, and normal program completion.

## 6. Tile appearance and revisit history

Base appearance shows maze/path/start/goal. Attempt feedback overlays it.

| Visit history for a physical cell | Display |
| --- | --- |
| Unvisited | Base appearance |
| Correct only, including repeated correct visits | Solid green |
| Incorrect only | Solid red |
| First incorrect, subsequent correct | Diagonal split: red left region, green right region |
| First correct, subsequent incorrect | Diagonal split: green left region, red right region |

Use two triangular regions separated diagonally. Recommended visual default: dividing line runs bottom-left to top-right; left triangle touches the top-left corner, right triangle touches the bottom-right corner. Add symbols/legend so color is not the sole explanation.

Three or more mixed visits were not explicitly settled. Scaffold a configurable reducer. Proposed default: preserve FIRST result on the left and LATEST result on the right; equal results render solid. Preserve the full event history regardless. Clearly document this assumption rather than treating it as confirmed.

New attempts clear feedback and the grading index, while prior attempt records may remain available for review.

## 7. Camera and projector calibration

### Camera

- Use four uniquely identified physical markers with fixed corner identities: TL, TR, BR, BL.
- Compute a camera-to-grid perspective mapping from known board points.
- Track a distinct marker on the robot for position and heading.
- Account for robot-marker elevation: a floor homography alone can introduce position error for a raised marker. Keep this a documented calibration concern; use a calibrated pose/height correction or validated approximation.
- Stabilize cell transitions using configurable filtering/hysteresis; avoid duplicate entries at boundaries.
- Mark pose stale when tracking is lost. Never display guessed position as observed truth.

### Projector

- Dedicated fullscreen `/projection` view contains only board graphics, no instructor panels.
- Instructor adjusts four output corners with drag handles and fine adjustment controls.
- Warp the ENTIRE board, including maze, feedback, and labels, to the selected quadrilateral. Cropping alone is not perspective correction.
- Save calibration relative to output viewport size and invalidate/warn on incompatible changes.
- Projector is a passive display. No SDK, network calls, or device programming.
- Use an extended display for laptop controls plus a clean projected view when available. Literal whole-desktop duplication would also show controls; support a fullscreen single-display fallback.
- A flat surface, fixed mounting, and sufficient projected footprint are assumed. Geometry correction cannot fix optical blur or an obstructed beam.

Camera and projector mappings share canonical grid coordinates but are independent. Do not use projector pixels as game coordinates. Keep physical markers readable despite projected graphics.

## 8. Card recognition

- Initial layout default: a single ordered horizontal row on a marked scan mat; no free-form branching or multi-row programs.
- Assign distinct physical marker IDs to repeated cards, mapping them to the same opcode.
- Use marker corners to rectify each card and crop a fixed numeric field.
- OCR only the step-count region for FORWARD/BACKWARD; evaluate handwriting recognition on actual sample cards.
- Return command, integer candidate, confidence/uncertainty, source card ID, order, and crop for review.
- Reject missing markers, duplicate detections, invalid syntax, unreadable numbers, and unsupported commands visibly.
- Offer instructor number correction before confirming the scan; retain raw recognition separately from confirmed values.
- Use printed-number cards as an explicit fallback if handwriting is unreliable; handwritten input remains the intended experience.
- Recognize cards only on Scan/confirmation, not continuously changing an active program.
- Support separate card and sandbox cameras through adapters. A single camera is acceptable only if both regions have adequate resolution/visibility. Do not assume the overhead tracking camera can also read distant handwriting.

## 9. Robot execution and recording

- Firmware controls motors and enforces bounded command duration, explicit stop, and a connection/heartbeat watchdog.
- Laptop owns puzzle grading; never send target correctness as permission to move.
- Bounds are operational constraints: stop before leaving the board. Validate planned movement before run and monitor actual pose during execution.
- If a plan exceeds bounds, flag it and require correction; if physical drift approaches the edge during a run, stop operationally. Never silently wrap, teleport, or clip the program into a different route.
- Keep programming mistakes distinct from actuator/tracking failures in review.
- Define one active control owner: program execution OR joystick recording, never both.
- Recommended joystick MVP: discrete one-cell forward/backward and 90-degree turns, debounced button toggles, input dead zone, and serialized actions.
- If continuous joystick driving is required, segment observed motion and heading into supported primitives. Flag diagonal/partial-cell/ambiguous segments; do not claim an exact replay when the block language cannot represent it.
- Generated programs must use observed movement plus heading/actions; position alone cannot identify backward travel or turns in place.

## 10. Suggested scaffold architecture

These are implementation recommendations, not a requirement to use a particular framework version.

| Component | Suggested implementation | Responsibility |
| --- | --- | --- |
| Instructor UI | React + TypeScript | Setup, map editor, scan review, modes, attempts |
| Projection view | Shared React board renderer + perspective transform | Passive display output |
| Backend | Python + FastAPI | Authoritative session state, compilation, grading, transport |
| Vision adapters | OpenCV ArUco + replaceable OCR adapter | Cards, calibration, robot pose |
| Robot firmware | ESP32 Arduino framework | Motor control, command acknowledgments, stop/watchdog |
| Joystick adapter | Browser Gamepad or hardware input adapter | Normalized actions/button events |
| Persistence | Local JSON initially | Puzzles, calibration, attempt records |

Use WebSocket events for UI/projection state updates. Select one robot transport (HTTP or WebSocket) behind a replaceable adapter. Freeze versions and dependencies during implementation. No cloud account or AI service is required to run the core MVP.

Suggested repository layout:

```text
frontend/src/{instructor,projection,board,calibration,api}
backend/app/{models,session,grading,compiler,vision,robot,recording,storage}
firmware/esp32/
fixtures/{puzzles,scans,pose_streams}
tests/
docs/
```

## 11. Shared data contracts

```typescript
type Cell = { row: number; col: number };
type Heading = 'N' | 'E' | 'S' | 'W';
type Instruction =
  | { op: 'START' | 'STOP' | 'LEFT' | 'RIGHT'; cardId?: number }
  | { op: 'FORWARD' | 'BACKWARD'; steps: number; cardId?: number };

type Puzzle = {
  id: string; version: number; name: string;
  rows: number; cols: number;
  startCell: Cell; startHeading: Heading; goalCell: Cell;
  targetEntries: Cell[];
};

type RobotPose = {
  timestampMs: number; x: number; y: number;
  headingDeg: number; trackingValid: boolean;
};

type VisitEvent = {
  attemptId: string; index: number; timestampMs: number;
  actual: Cell; expected: Cell | null; correct: boolean;
};
```

Validate these server-side. Define heading-degree convention explicitly (suggest 0=N, 90=E). Include run ID, instruction index, unique message ID, status, and errors in robot transport messages. Duplicate/retried messages must not execute a movement twice. Pose updates and command acknowledgments are distinct sources of evidence.

Suggested API surface:

- Puzzle create/load/update and calibration save/load.
- Scan request, recognition result, and confirmed program submission.
- Run, operational Stop, reset attempt.
- Recording start/stop and generated-program retrieval.
- WebSocket snapshot plus ordered events: pose, cell entry, visit graded, execution status, recording status, tracking warning, and fault.

Authoritative state lives in the backend; projection and instructor clients consume the same state. On reconnect, send a snapshot with event sequence number to prevent duplicated visits.

## 12. MVP screens and state

Screens: Setup/Calibration; Puzzle Editor; Programming/Scan Review; Live Attempt; Joystick Recording/Generated Code; Projection.

Suggested exclusive session states: IDLE, SCANNING, PROGRAM_READY, RUNNING, RECORDING, COMPLETED, STOPPED, FAULT. Calibration is allowed only while motors are stopped. Reject conflicting actions server-side. New puzzle/run requires confirmed start pose and heading.

Puzzle upload MVP means a structured JSON puzzle with an ordered path. A visual editor can draw/export that path. Arbitrary image-to-solution inference is out of scope; an image alone does not specify visit order reliably.

## 13. Hardware status and responsibilities

Proposed, not verified/purchased: Hiwonder 4WD mecanum chassis, ESP32, two Adafruit DRV8833 dual drivers, USB webcam(s), joystick, conventional projector, suitable batteries/regulation, wiring, markers, scan cards, flat board, and mounts.

Before wiring: confirm exact motor voltage/stall current against driver limits, independent four-motor control, power regulation/common grounding, and connector needs. Keep motor power off ESP32 output pins. Do not invent missing motor specifications or GPIO assignments.

Mechanical work: robot assembly/mounting, stable camera/projector supports, flat sandbox and corner-marker placement, card/scan-mat design, joystick housing as useful. A simulator must allow app work before hardware arrives.

## 14. Implementation milestones

1. Shared models, example puzzle, pure grading reducer, board renderer, and simulated robot/pose stream.
2. Instructor puzzle editor and calibration UI; fullscreen warped projection synchronized with instructor state.
3. Card detection plus numeric-field OCR adapter and confirmation workflow.
4. Firmware motor tests, movement calibration, communications and stop/watchdog; integrate before the final day.
5. Camera mapping/tracking, stable cell-entry events, bounds monitoring, live scoring and revisit rendering.
6. Joystick recording and block-code generation using the same command semantics.
7. AI theme generation, preview/caching, and projection readability checks.
8. End-to-end rehearsal, error recovery, and setup documentation.

Build independent modules against shared fixtures; integrate early. Do not spend the first two days polishing disconnected UI.

## 15. Acceptance criteria

- Instructor creates/loads a grid puzzle with an ordered route and initial heading.
- Four-corner calibration makes the projected grid align with the physical board; calibration survives refresh.
- Valid physical cards with confirmed numeric fields produce the expected program; ambiguous scans cannot run silently.
- A confirmed program executes once and remains frozen if cards move afterward.
- Wrong target entries do not stop the robot. A later entry matching its same-index target is green.
- Pure grader test: target [A,B,C,D], actual [A,C,B,D] yields [green,red,red,green].
- Extra entries are red; missing entries are incomplete; turns/repeated frames do not advance grading.
- Cell revisits render solid or split colors according to the agreed two-visit table.
- Boundary approach, explicit stop, stale tracking, or connection failure results in an operational stop with a distinct reason.
- Joystick button toggles recording without bounce; ending recording stops motion and produces supported blocks.
- Generated code preserves forward/backward and in-place turns; three consecutive forward cells compress to FORWARD 3.
- Instructor and projection views remain synchronized and recover from reconnect without duplicated events.
- Simulator demonstrates the full workflow without hardware; real integration is separately verified and labeled.

Prioritize meaningful tests for grading/indexing, revisit reduction, program validation/bounds, recording conversion, and duplicate-command handling. Include a manual hardware/calibration checklist; do not claim unperformed hardware tests passed.

## 16. Out of scope and unresolved choices

Out of scope: loops, conditions, functions, unrestricted handwritten code, automatic projector control, automatic image-maze solving, cloud classroom accounts, guaranteed learning gains, and unrestricted free-driving-to-perfect-code conversion.

Resolve or expose configuration for: three-plus-visit rendering; exact joystick hardware and discrete versus continuous operation; camera count; OCR engine/step range; robot transport; controller GPIO/power specifics; height correction; boundary margins and tracking thresholds. Use the labeled defaults above to scaffold without blocking, but do not present them as user-confirmed choices.

AI direction: theme generation is the selected generative feature. Do not implement a teaching assistant, automated pedagogical decisions, or an agentic workflow. The instructor defines the lesson and remains the authority on the target solution. Keep theme generation separate from deterministic grading and motor execution.

## 17. Initial instruction to a coding agent

Scaffold this MVP beginning with shared contracts, simulator, instructor UI, projection calibration, and the deterministic grading tests. Preserve all non-negotiable behavior. Use adapters for cameras, OCR, joystick, and robot so hardware can be integrated incrementally. Document assumptions and startup commands. Do not add loops, stop a run merely for a wrong tile, replace same-index grading with recovery-based grading, or implement a projector device API. Deliver a runnable local vertical slice before expanding features.


## 18. AI-generated grid themes

### Purpose and boundaries

Let students choose a theme that makes the instructor-defined puzzle visually engaging. Use a single image-generation model request per generation attempt, with an application-built prompt encapsulating fixed board parameters and an app-generated layout reference image. No agent, tool-planning loop, or teaching assistant is required.

The instructor defines and approves the puzzle. Theme generation changes presentation only: it must not change grid dimensions, start, heading, goal, targetEntries, command semantics, grading, or robot behavior. Changing themes must preserve the exact puzzle and its version/hash.

Example: a firefighter theme depicts a fire station at the start, connected streets along the route, buildings/parks in scenery cells, and a cartoon fire/emergency at the goal. Other possible themes include space, underwater exploration, and dinosaurs. Aim for age-appropriate, legible illustrations for grades 2–4.

### Hard parameters supplied by the app

| Parameter | Requirement |
| --- | --- |
| Grid | Exact rows and columns; zero-indexed coordinate convention |
| Output | Requested supported image dimensions and board aspect ratio; use deterministic fit/crop handling if the provider cannot return the exact size |
| Viewpoint | Flat top-down orthographic artwork; no perspective, tilt, or isometric view |
| Start | Exact cell and initial heading |
| Goal | Exact goal cell and theme-relevant destination |
| Route | Full ordered targetEntries, including revisits; derive visual route connectivity without losing the ordered source data |
| Cell roles | Explicit route/start/goal/scenery assignments and allowed artwork regions |
| Connections | Explicit entry/exit edges for route cells, calculated by the app |
| Reserved regions | Physical corner markers and robot tracking marker visibility must remain protected |
| Visual constraints | No generated text, extra grids, misleading traversable routes, or decorations that resemble live grading feedback |
| Theme | Student-selected subject plus a consistent style/palette |

An image model cannot enforce exact layout merely because the prompt calls these parameters hard. The app guarantees gameplay geometry through deterministic overlays and instructor preview. Treat the generated background as decorative and potentially imperfect; never derive navigation or grading from it.

### Prompt construction and layout reference

1. Serialize the confirmed puzzle into an immutable theme request.
2. Compute cell bounds and route connections, including turns and intersections for revisited cells.
3. Render a reference image at the board aspect ratio with exact cell regions, route, start, goal, and reserved areas. Use an image-capable generation endpoint that accepts a reference image.
4. Build a constrained prompt from those parameters and the theme. Use one coherent board composition, rather than independent generation calls for every tile.
5. Request artwork; show loading state while the existing board remains usable.
6. Fit the response into the canonical board canvas; check image decoding, dimensions, aspect handling, and request/puzzle association.
7. Present instructor preview with overlays enabled. Instructor accepts, regenerates, or uses a prepared fallback.
8. Persist accepted artwork plus its request metadata. Apply only when not RUNNING/RECORDING.

Example prompt template:

```text
Create a coherent, child-friendly {theme} illustration for a physical coding maze.
Use the supplied layout reference as the composition guide.
Board: {rows} rows by {cols} columns, requested output {width} by {height} pixels.
Coordinates: zero-indexed, row 0 at top, column 0 at left.
Start: {startCell}, facing {startHeading}. Goal: {goalCell}.
Ordered route: {targetEntries}.
Cell roles and route-edge connections: {cellLayout}.
Reserved blank regions: {reservedRegions}.
Use a flat top-down view with consistent scale and matching connections across cell edges.
Place a theme-relevant starting location at the start and destination at the goal.
Keep scenery in assigned regions and avoid misleading routes.
Do not add text, a separate grid, perspective distortion, or green/red grading indicators.
Keep important navigation and reserved regions visually clear.
```

This is a prompt template, not a guarantee of geometric compliance or a required model/provider choice. Do not send API credentials or student identifying information in prompts.

### Rendering layers

Render in canonical board coordinates, back to front:

1. Accepted AI-generated artwork (decorative background).
2. App-rendered exact route cues and grid lines.
3. App-rendered start/goal indicators and necessary labels.
4. Live correctness feedback, including solid and diagonally split revisit colors.

Apply the existing four-corner projection warp to the entire composition. No projector device programming. Keep feedback readable over every theme; use opaque or sufficiently strong overlays and symbols as needed. Theme colors must not masquerade as green/red correctness signals. Marker exclusion regions remain clear in final compositing, not merely in the image prompt.

### App/backend integration

Suggested module: backend theme service with a replaceable image-provider adapter, and frontend Theme panel/preview in puzzle setup. Keep API keys server-side. Suggested operations: generate, fetch job status, preview, accept, regenerate, select cached theme, and select fallback.

Recommended ThemeRequest fields: requestId, puzzleId, puzzleVersion, puzzleHash, themeText, rows, cols, startCell, startHeading, goalCell, targetEntries, output dimensions, cell layout, reserved regions, style settings, and prompt-template version.

Recommended ThemeAsset fields: assetId, requestId, puzzleHash, status, image location, actual image dimensions, provider/model identifier when available, creation time, and acceptance state.

Generation lifecycle is separate from robot session state: IDLE / GENERATING / READY / FAILED. A slow job must not block Stop, tracking, instructor controls, or rendering. Ignore stale generation results after puzzle edits; require a matching puzzle hash before acceptance.

Cache by puzzle geometry/path, theme/style, output settings, and prompt-template version. Keep accepted files locally available rather than relying on expiring provider URLs. Do not regenerate on every run, frame, or cell entry. Provide a timeout/error message, deliberate retry/regenerate action, and immediately usable prepared/default artwork.

### Timing estimates and build priority

Planning estimates, not measured service guarantees:

- Generation: roughly 30 seconds to 2 minutes per image as an initial allowance. Actual latency depends on selected provider/model, resolution, load, and retries; benchmark the actual integration.
- Generate before the activity, cache once, and reuse across attempts.
- Live grid rendering, tracking, and feedback have no dependency on generation latency.

Assuming the board renderer already exists:

| Integration task | Estimated focused developer time |
| --- | --- |
| Parameterized prompt and layout reference | 1–2 hours |
| Image API adapter and output display | 1–2 hours |
| Preview, regenerate, loading, caching | 1–2 hours |
| Alignment/readability/failure testing | 2–4 hours |
| Total | Approximately 5–10 hours |

These estimates cover a basic integration, not guaranteed artwork precision, model training, new projector calibration work, or production hardening. Reliable alignment/visual coherence is the main uncertainty. Core robot/card workflows remain the first integration priority.

### Theme acceptance criteria

- Instructor chooses a fixed puzzle and requests a student-selected theme.
- Request contains the board parameters and an exact layout reference.
- Generation cannot mutate puzzle geometry, ordered grading, or commands.
- Preview permits accept/regenerate/fallback before projection use.
- Changing themes leaves camera/projector calibration and grid coordinates unchanged.
- Exact grid and navigation overlays align even if artwork is imperfect.
- Live green/red and split-tile overlays remain legible; marker regions stay clear.
- Repeated runs reuse cached accepted artwork without a fresh API call.
- Provider failure/timeout leaves the activity runnable with a prepared theme.
- Stale responses from a prior puzzle cannot overwrite the current theme.
- No agentic workflow or teaching-assistant feature is introduced.
