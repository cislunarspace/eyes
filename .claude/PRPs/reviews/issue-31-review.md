# Local Code Review: issue #31 — Accumulator S4/S5 extraction

**Reviewed**: 2026-05-13
**Scope**: uncommitted changes (`git diff HEAD`) plus untracked accumulator split files
**Decision**: APPROVE

## Summary

The issue #31 refactor successfully extracts `FacingTimeAccumulator` and `PresenceTimeAccumulator` into separate pure state machines, wires them through `SenseLoop`, and removes the S4/S5 accumulation paths from `AccumulatorEngine`. The Windows-only linux-packaging failure has been fixed by skipping the Linux-specific platformdirs assertion off Linux while preserving a direct `platformdirs.user_config_dir("eyes")` assertion on Linux; the full test suite is now green on this working tree.

## Findings

### CRITICAL
None.

### HIGH
None.

### MEDIUM

**M1. Worktree scope includes issue #28 changes alongside issue #31**
- Files: `src/eyes/classifier.py`, `src/eyes/detector.py`, `src/eyes/controller.py`, `src/eyes/main_window.py`, `tests/test_classifier.py`, `tests/test_controller.py`, `tests/test_detector.py`, `tests/test_sense_loop.py`
- The issue #31 accumulator split is present and coherent, but the working tree also includes the HeadPose value-type refactor and warning-banner/event-flow changes from issue #28.
- Suggested fix: keep these bundled only if the project workflow intentionally accepts a combined change; otherwise split issue #31 into a focused commit/PR after the issue #28 work lands.

### LOW

**L1. Generated session log is untracked**
- File: `.claude/session-files.log`
- This appears to be Claude/session bookkeeping rather than project source.
- Suggested fix: do not include it in the eventual commit unless the project intentionally tracks these session files.

**L2. CRLF/LF warnings on Windows**
- Files: several modified `.py` files reported by git.
- Git reported that LF will be replaced by CRLF when it next touches these files.
- Suggested fix: no code change required unless the repository expects stricter line-ending normalization; otherwise treat as cosmetic.

## Validation Results

| Check | Result | Notes |
|---|---|---|
| Type check | Skipped | No mypy/pyright command configured in `pyproject.toml`. |
| Lint | Skipped | No ruff/black lint command configured in `pyproject.toml`. |
| Focused tests | Pass | `.venv/Scripts/python.exe -m pytest tests/test_accumulator.py tests/test_facing_time_accumulator.py tests/test_presence_time_accumulator.py tests/test_sense_loop.py tests/test_controller.py` → `64 passed`. |
| Full tests | Pass | `.venv/Scripts/python.exe -m pytest tests/` → `259 passed, 1 skipped`. |
| Build | N/A | Pure Python app; no separate build command configured. |

## Files Reviewed

- `src/eyes/accumulator.py` — Modified
- `src/eyes/facing_time_accumulator.py` — Added/untracked
- `src/eyes/presence_time_accumulator.py` — Added/untracked
- `src/eyes/sense_loop.py` — Modified
- `tests/test_accumulator.py` — Modified
- `tests/test_facing_time_accumulator.py` — Added/untracked
- `tests/test_presence_time_accumulator.py` — Added/untracked
- `src/eyes/classifier.py` — Modified
- `src/eyes/detector.py` — Modified
- `src/eyes/controller.py` — Modified
- `src/eyes/main_window.py` — Modified
- `tests/test_classifier.py` — Modified
- `tests/test_controller.py` — Modified
- `tests/test_detector.py` — Modified
- `tests/test_sense_loop.py` — Modified
- `.claude/PRPs/reviews/issue-28-review.md` — Modified review artifact
- `.claude/session-files.log` — Added/untracked session log

## Next Steps

1. Decide whether issue #31 should ship bundled with the broader issue #28 work or be split into a focused change.
2. Exclude `.claude/session-files.log` from the eventual commit unless intentionally tracked.
