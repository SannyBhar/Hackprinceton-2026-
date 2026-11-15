# Two-inch movement blocks (2026-11-15)

This user-approved format replaces handwritten distances on physical FORWARD/BACKWARD cards.
The earlier architecture/OCR requirements describe the previous card format.

| Marker ID | Student block | Movement |
| --- | --- | --- |
| 0 | FORWARD | One grid cell forward (22 cm after measured hardware calibration) |
| 1 | BACKWARD | One grid cell backward |
| 2 | RIGHT | In-place clockwise 90° turn |
| 3 | LEFT | In-place counterclockwise 90° turn |

Dictionary: **DICT_4X4_1000**. Each block and marker square is **2 × 2 inches (50.8 × 50.8 mm)**.
The supplied SVG geometry was preserved exactly; only its original 100 mm size attributes
were changed to 2 inches. Source assets: `assets/markers/4x4_1000-{0,1,2,3}.svg`.
Automated tests rasterize those exact assets, compare all bits with OpenCV's dictionary,
and scan them at all four rotations.

## Printing and scanning

```bash
backend/.venv/bin/python tools/make_cards.py --out printables
```

Open `printables/unit-blocks.html` in a browser and print at **100% / actual size**, with
fit/shrink-to-page disabled. Measure a printed square: it must be 2 inches / 50.8 mm.
The sheet references the generated SVG files, so keep them together. The tool also creates
optional START (ID 10) and STOP (ID 80) markers. It does not generate old arena markers or
handwriting boxes. Old files in an existing output directory are not deleted; use the new
HTML sheet to select the current assets.

The marker fills the block: **there is no room for an internal white margin**. Keep clear
white background around every block, including white gaps between adjacent blocks. Start
with 1/2 inch of white separation and verify detection with the actual camera.
Do not crop the black border, overlay text on the pattern, laminate with strong glare, or
butt black marker edges together. Physical recognition/readability remains to be tested.

Place a single horizontal row, read left to right. Multiple copies of ID 0 are multiple
FORWARD blocks, not a duplicate-ID error. For example, `0, 0, 2, 0` means forward one cell,
forward one cell, turn right, forward one cell. Orientation does not change the ID's command.
Unknown IDs remain visibly unresolved until corrected or removed.

In Program, scan, check every block/order, then explicitly acknowledge the review and confirm.
The UI adds missing START/STOP bookends, so the four supplied movement markers are sufficient.
No distance field, numeric crop or OCR is used in this physical scan workflow. Run does not
start from scanning or review alone; the existing pose/readiness/safety gates still apply.

## Compatibility and boundaries

- Existing markerless `BoardCamera`, projector geometry, grading, Wi-Fi/USB firmware and hardware
  calibration were not changed. A 2-inch code block does not change the 22 cm physical grid cell.
- Old board-corner IDs 0–3 must stay outside the card scan view: those patterns now mean movement.
  Current main uses markerless arena tracking, so no new arena marker IDs are introduced.
- Numeric marker ranges 20–79 are no longer physical movement cards. Reprint movement cards
  with the supplied IDs. Optional START/STOP use 10/80.
- `ScanResult.unitBlocks` is additive. New physical/fixture scans set it true. Server confirmation
  enforces `steps=1` for every translation in a reviewed unit-block scan, including edited rows.
- The existing REST/compiler/firmware/history contracts retain `steps` internally to read older
  saved programs and recordings without changing their behavior. The student editor creates only
  one-cell movement instructions. Shared block displays expand compressed old/reference programs
  into repeated unit blocks and retain the active original command index.
- Optional OCR code and the old scan-finalization path remain for historical compatibility/tests;
  adapter composition no longer loads OCR for physical blocks, even if an old OCR setting exists.
- The two simulator fixture scans now use repeated movement IDs and require order review. Existing
  student commands, ordered grading/revisits and simulator execution remain compatible.

## Verification

Baseline: 92 backend tests passed, 4 skipped; 8 frontend tests and typecheck passed.
Final: **114 backend tests passed, 4 skipped; 11 frontend tests and 5 Playwright workflows passed; typecheck and production build passed.** The four existing skips need local `testpattern_cam0.jpg` / `robot_testpattern.jpg` captures. The existing Starlette/AnyIO warning remains. No firmware or dependency versions changed. Added regressions cover
all four supplied SVGs in four orientations, repeated IDs/order, empty/corrupt/unknown scans,
no OCR invocation, one-cell server validation, SVG print dimensions, display expansion, automatic
bookends, browser review and repeated-block simulator execution with correct same-index grading. Physical printing/camera/motor acceptance is not implied by these tests. Existing dependency findings remain documented separately.
