# Python Test Scripts Audit

## Scope & Inputs
- Analyzed: `example_script.py` (single test harness script; ~1694 lines).
- Dependencies referenced: `utilities` (aliased `u`, proprietary) and `test_initialization` (proprietary). Both are mocked at import time via `sys.modules` in this file.
- Entrypoint: `run_script()` invoked under `if __name__ == "__main__":`.
- Constraints assumed: static review only; behavior preservation preferred; no new third-party deps.

## Inventory & Dependency Map
- Entrypoint flow (`run_script`, lines ~20-70): optional rig start, log open/header, `test_initialization.standard_init()`, requirement blocks, error count, re-init, cleanup, optional rig stop.
- Requirement blocks:
  - `reqt_2a_passenger_freighter` (lines ~90-700): deeply nested loops over aircraft type and UUTs; uses large `input_parameter_validity_table` to drive dozens of near-identical set/check sequences; heavy logging and sleeps; many manual post-process calls.
  - `reqt_2b_passenger_freighter` (lines ~720-1670): similar pattern for test data flag logic across channels; repeated set/check sequences per UUT and aircraft type.
- Proprietary utilities usage: logging (`OpenLogFile`, `WriteToLog`, `AssembleLogheader`, `GatherScriptInfo`), signal control (`SetSignal`, `CheckSignal`, `StartRecording`, `StopRecording`, `SetTestCase`, `PostProcess`, `ErrorCount`, `CloseLogFile`), rig start/stop (`init_module.start_rig`, `down_module.stop_rig`).
- Shared patterns: repeated signal-name construction with string concatenation, repeated sleeps (`sleep(1/2/4/6)`), repeated colorized log statements, repeated manual verification notes.

## Key Findings (evidence-based)
- **Imports masked by mocks**: Lines ~5-12 inject `Mock` objects into `sys.modules` for `utilities` and `test_initialization`, meaning missing/incorrect utility APIs would be silently hidden during import; runtime errors will surface much later (harder to diagnose). Prefer explicit imports that fail fast, or gate the mocking behind a test-only flag.
- **No defensive cleanup**: `run_script` (lines ~20-70) has no `try/finally`; if any step fails, recordings/logs/rig stop may be skipped, risking resource leaks and inconsistent rig state.
- **Global mutable switches**: Flags like `record_data`, `pwr_start_stop` set at module level (lines ~15-25) implicitly control side effects; no parameterization for callers/harness; harder to run subsets or dry-run.
- **Massive duplication & imperative sequences**: Both requirement functions replicate large blocks of nearly identical set/check/sleep patterns. Example: lines ~400-700 repeat ProcSteps a–i per parameter, and lines ~1240-1660 repeat for each controller/side permutation. This obscures intent and invites drift when updates are needed.
- **Magic numbers & waits**: Sleeps of 1/2/4/6 seconds and tolerance values (e.g., `k_css_no_info_time` set to 3/5 on lines ~560-630) are hard-coded without named constants or rationale; deterministic timing is unclear and likely flaky if environment timing shifts.
- **Weak pass/fail signaling**: Assertions rely on `u.CheckSignal` side-effects; manual verification steps logged via `u.PostProcess` (e.g., lines ~520, ~610) indicate human-in-the-loop checks with no automated result capture. No aggregation per test case besides `u.SetTestCase`; failures likely raise but not clearly summarized.
- **Tight coupling to stringly-typed signals**: Signal names built with string concatenation (e.g., `UUT + 'k_css_no_info_time'`, lines ~170-230) repeated in multiple places; no single source of truth or validation. Typos would only surface at runtime.
- **Inconsistent recording lifecycle**: `StartRecording` / `StopRecording` guarded by `record_data` but not wrapped in finally; if an exception occurs mid-requirement, recording may remain active.
- **Logging noise vs. structure**: Frequent `WriteToLog` calls with free-form text and colors; no structured context (e.g., test id, parameter, UUT) that could be parsed. Headers assembled once, but per-step logs are unstructured.
- **Behavioral ambiguity**: `u.PostProcess` calls note "manually verify" which means automated determinism is incomplete; the script claims to test requirements but defers critical checks to humans.

## Refactor Plan (behavior-preserving by default)
1. **Harden lifecycle & error handling (low risk, high ROI)**
   - Wrap `run_script` body in `try/finally` to guarantee `StopRecording`, `CloseLogFile`, and rig stop even on failure.
   - Add lightweight context managers for recording and rig power that call utility start/stop in `__enter__/__exit__`.
2. **Parameterize execution (low risk)**
   - Convert module-level switches (`record_data`, `pwr_start_stop`) into arguments to `run_script(...)` with defaults; allow callers to disable rig power or recording without editing globals.
3. **Extract data-driven helpers (medium effort, high ROI)**
   - Define small helpers for common patterns (e.g., `set_aircraft_type(u, UUT, kind)`, `verify_output(u, expected_V, expected_P)`, `exercise_case(u, spec)`). Keep the existing `input_parameter_validity_table` but process it through reusable functions to eliminate duplicated ProcStep code.
   - Centralize signal-name construction in factory helpers or a dataclass that holds all derived names for a UUT; prevents repeated string concatenation and reduces typo risk.
4. **Encapsulate requirement flows (medium effort)**
   - Wrap requirement blocks in classes (e.g., `Requirement2A`, `Requirement2B`) with methods like `run_for(uut, aircraft_type)` and shared utilities; this improves readability and makes it easier to add new requirements without touching global code.
5. **Make timing deterministic (medium effort)**
   - Replace raw `sleep` calls with a timing helper that documents intent (e.g., wait for propagation, debounce) and centralizes default durations; allow override via kwargs/env for faster dry-runs.
6. **Improve logging/observability (low risk)**
   - Standardize log format: `[req][case][uut][param] message` and emit a single summary per test case. Capture expected vs actual values in structured form (JSON line or CSV) if utilities allow.
   - Where manual verification is currently required, emit explicit "manual check needed" markers and consider exporting the relevant signals to a deterministic assertion if available.
7. **Clarify pass/fail contracts (medium effort)**
   - Ensure `u.CheckSignal` raises or records failures; add a final summary (`u.ErrorCount`) per requirement section. Consider returning a result object from each requirement to aid aggregation.
8. **Testability & dry-runs (optional)**
   - Allow dependency injection of the `utilities` module (or an adapter) so unit tests can run against fakes without global `sys.modules` mocks. Guard the current mocks behind `if __name__ == "__main__" and os.environ.get("ALLOW_MOCKS")` or similar.

## Suggested OOP Modularization (optional)
- Introduce a small domain model:
  - `class SignalBundle`: builds and stores all related signal names for a UUT (validity, parameters, defaults).
  - `class RequirementRunner`: holds the `utilities` adapter, provides helpers like `set_and_verify`, `log_step`, `wait_for`.
  - `class Requirement2A(RequirementRunner)` and `Requirement2B(...)`: implement `run_for(uut, aircraft_type)` using concise step methods (`case_a`, `case_b`, ...). Each returns a result dict (status, failures, manual_checks).
- Benefits: reduces repetition, clarifies intent, and localizes changes when specs evolve.

## Quick Wins to Implement First
- Add `try/finally` around `run_script` to ensure log/recording/rig cleanup.
- Extract a `with recording(u, name):` context manager to pair `StartRecording`/`StopRecording`.
- Create a helper to set/check aircraft type and disable flags once per UUT rather than inline repetition.
- Replace repeated `WriteToLog` banners with a single structured logging helper.
- Move sleep durations into named constants (`WAIT_SHORT = 1`, `WAIT_MED = 2`, etc.).

## Residual Risks / Unknowns
- Behavior of `utilities` APIs is inferred; some refactors may need adapter shims rather than direct calls.
- Manual verification steps (`PostProcess`) indicate incomplete automation; converting them to assertions may require additional data capture support in utilities.
- Timing assumptions (sleep durations) may encode hardware latency; validate before tightening.

## Next Steps
- Confirm desired Python version and whether new lightweight dependencies (e.g., attrs/dataclasses backports) are allowed.
- Decide on acceptable behavior changes: e.g., fail-fast on import vs. current mock masking; automated vs. manual verification.
- Implement lifecycle guards and helper extraction in a small PR, then iterate on deeper modularization.
