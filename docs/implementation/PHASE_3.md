> Historical phase record. Current hardware/build instructions and verification status:
> [stabilization](STABILIZATION.md) and [Mac runbook](../MAC_HARDWARE_SETUP.md).

# Phase 3 — themes, learning and acceptance

Nano Banana adapter uses Gemini Interactions REST with model configuration, backend-only
GEMINI_API_KEY, a deterministic PNG layout reference, and a bounded generation task. Requests
contain puzzle geometry/theme, never student identifiers. Provider jobs support READY/FAILED/
CANCELLED, persistent cache, preview, acceptance and stale-puzzle rejection. Rendering puts
accepted artwork beneath exact route/grade/marker layers. Static/cached output works offline.
Install requirements-ai.txt before use. Model default gemini-nano-banana-2.1 is configurable;
account availability and a real paid generation are unverified without backend credentials.
Official protocol reference: https://ai.google.dev/gemini-api/docs/image-generation .

Progress uses explicit BKT defaults (prior .2, learning .1, guess .2, slip .1). These are
illustrative, not fitted/validated on children. Normal attempts count only if observed entries
match the commanded plan; faults or unattributed deviations are excluded. Sequencing/spatial
use task-level evidence; direction/distance require instructor annotation in History. Reports
include evidence counts, uncertainty and accuracy trends. Recommendations choose validated,
bounded deterministic candidate paths for a weaker skill, with explanations and instructor
approval. No AI or learning module imports a robot adapter or issues movement.

Seed distinctly labeled synthetic histories (optional):
`PYTHONPATH=backend backend/.venv/bin/python tools/seed_learning_demo.py --data-dir data`.
These are separate local aliases; never label them as classroom evidence. Actual learners use
local aliases, not cloud accounts. No educational efficacy/diagnosis claim is supported.

## Verification / limits

Backend tests cover theme request contract with a mock HTTP provider, cached image validation,
acceptance/stale guards, cancellation/failure/static fallback, deterministic BKT, exclusion of
faults, and candidate solvability. Mock images are NOT a live Gemini acceptance result.

Real local TrOCR inference was exercised on a synthetic printed digit crop; raw output `2 0`
was rejected as ambiguous and returned no candidate. Model loaded successfully. This validates
inference/fallback only, not handwritten-card accuracy. Run real-card benchmarks with:
`PYTHONPATH=backend backend/.venv/bin/python tools/benchmark_ocr.py path/to/manifest.json`.
Manifest: list of {"path":"crop.png","expected":2}; paths relative to manifest. Results include
raw text/candidate/latency/errors. No actual card dataset was supplied.

Playwright tests cover scan review/global STOP, projection updates/reconnect, library JSON
import, local student creation/selection, laptop calibration-pad keyboard updates, saved attempt
history, and theme-failure UI. Theme browser fixture is explicitly mocked. Chromium initially
could not start under macOS sandbox Mach-port restrictions; browser tests run outside that
sandbox. Hardware, optical alignment, real serial wiring and live provider acceptance remain
PENDING. Neither firmware image was flashed. See ACCEPTANCE_MATRIX.md for source coverage.


Final hardening: snapshot payload/envelope sequences now agree; slow consumers are closed with
1013 and resnapshot on reconnect. Older poses cannot overwrite newer ones. Robot connections
have one client owner, integer primitives and bounded payloads. The firmware ID ledger retains
128 accepted discrete IDs without eviction; once full, it rejects motion until a stopped power
cycle. STOP is still accepted. Disconnected transport STOP does not prevent session cleanup;
the independent firmware watchdog/drive expiry remains the fallback. Unified GRASSROOT_CAMERA
selects one webcam, with explicit legacy camera variable fallbacks.
