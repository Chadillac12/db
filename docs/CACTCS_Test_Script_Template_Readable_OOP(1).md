# CACTCS Script Readability Ideas + Annotated Template (draft)
_A few practical patterns I tossed together — feel free to tweak/ignore._

This isn’t meant to be a strict standard. It’s just a collection of ideas that tend to make CACTCS scripts easier to review (especially in logs) and easier to change later.

This doc includes a short list of patterns and an annotated template you can copy/paste as a starting point.

---

## 1) Make Logs Easier to Review

### Problem
Table-driven loops (parameter sweeps) are efficient for code, but the log often becomes a blur:
- “SetSignal / CheckSignal” spam
- No clear “Test Case Start/End”
- Hard to tell what parameter is being tested and which requirement/testpoint it belongs to

### Suggestion: Write a structured header + footer per test case
**Helpful to include at test case start:**
- Requirement / Testpoint ID (e.g., “Req 2a / TP=1”)
- Test Case number (and optionally a short name)
- Verification case label (a/b/c…)
- UUT (channel) and aircraft type
- Parameter under test (and any key values like resolution / tolerances)

**At test case end:**
- “PASS/FAIL” if available from harness, otherwise at least “Completed”
- Any key computed values (e.g., expected_output)

### One thing that helps: Use a single helper for case logging
If everyone logs the same way, review becomes easy.

### Also: Use a helper for testcase numbering
Call `next_case()` (shown in the template) so `SetTestCase` stays consistent and no one forgets to increment.

---

## 2) A Few Small Patterns That Help

These are intentionally small/boring — the goal is readability, not building a framework.

### Signal naming helper (avoid repeated string concatenation)
I’ve found an inline helper keeps the code less noisy than repeating `uut + '::' + name` everywhere.

```python
uut = f"{uut_base}::"

def s(name: str) -> str:
    return f"{uut}{name}"

k_disable_all_can_inputs = s("k_disable_all_can_inputs")
```

### Testcase numbering helper (`next_case`)
This keeps numbering consistent and prevents “forgetting” a `SetTestCase` when loops get complex.

```python
case_no = testcase

def next_case(case_type: str = "normal") -> int:
    nonlocal case_no
    case_no += 1
    u.SetTestCase(testpoint, case_no, type=case_type)
    return case_no

next_case("normal")
```

### Consistent log boundaries
If every case starts/ends with the same structure, it’s much easier to scan a log and understand what happened.

```python
u.WriteToLog(f"=== TEST CASE START: Req 2a / TP={tp} / TC={tc} / VC={vc} ===", color="green")
u.WriteToLog(f"UUT={uut} Aircraft={aircraft_type} Param={param}")
...
u.WriteToLog("=== TEST CASE END: COMPLETED ===", color="green")
```

### Keep setup/teardown hard to forget
If we have common lifecycle calls (rig start/stop, Open/CloseLogFile, recording start/stop), wrapping them in a context manager tends to reduce “oops, forgot cleanup” failures.

---

## 3) Annotated Template (Copy/Paste Starter)

This is a full-ish starting point that shows how the pieces fit together. It’s intentionally annotated to explain what each part is doing and why it helps log review / maintainability.

```python
"""
CACTCS Test Script Template (Readability + Review-Friendly Logging)

Intent:
- Keep the script lifecycle (rig/log/recording/init) consistent and hard to forget.
- Make testcase numbering and logging consistent so log review is quick.
- Reduce repetitive "plumbing" (signal string building, set/check blocks) so test intent is obvious.

Notes:
- The harness/utilities functions are assumed to exist (u.SetSignal, u.CheckSignal, u.SetTestCase, etc.).
- Adjust naming to match your team's conventions.
"""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from typing import Any, Dict, Optional

import utilities as u
import test_initialization


@dataclass(frozen=True)
class RunConfig:
    """Configuration bag.

    Why this helps:
    - Keeps metadata + toggles in one place.
    - Avoids scattered globals.
    - Makes scripts easier to diff/review.
    """

    program: str = "CACTCS"
    author: str = "Your Name"
    current_rcn: str = "RCN-XXXX"

    record_data: bool = True
    pwr_start_stop: bool = True

    rec_id: str = "your_recording_id_here"
    rec_freq_hz: int = 32


class Harness:
    """Small wrapper around utilities.

    Why this helps:
    - Collapses noisy repetition into smaller intent-focused blocks.
    - Encourages grouped set/check patterns.
    """

    def set_many(self, pairs: Dict[str, Any]) -> None:
        for sig, val in pairs.items():
            u.SetSignal(sig, val)

    def check_many(self, pairs: Dict[str, Any]) -> None:
        for sig, val in pairs.items():
            u.CheckSignal(sig, val)

    def settle(self, seconds: float = 1.0) -> None:
        u.sleep(seconds)


class RunContext:
    """Script lifecycle wrapper."""

    def __init__(self, config: RunConfig, script_name: str):
        self.config = config
        self.script_name = script_name
        self.h = Harness()

    def initialize(self) -> None:
        test_initialization.standard_init()

    def report_errors(self) -> None:
        u.ErrorCount()

    @contextmanager
    def safe_run(self):
        started_rig = False
        log_open = False

        try:
            if self.config.pwr_start_stop:
                u.init_module.start_rig()
                started_rig = True

            u.OpenLogFile(self.script_name)
            log_open = True

            yield

        finally:
            if log_open:
                try:
                    u.CloseLogFile()
                except Exception:
                    pass

            if started_rig:
                try:
                    u.down_module.stop_rig()
                except Exception:
                    pass

    @contextmanager
    def recording_scope(self):
        """Optional recording wrapper."""

        if not self.config.record_data:
            yield
            return

        u.StartRecording(self.config.rec_id, screen_name=self.config.rec_id, rec_freq_hz=self.config.rec_freq_hz)
        try:
            yield
        finally:
            u.StopRecording()

    def log_case_start(
        self,
        requirement_id: str,
        testpoint: int,
        testcase: int,
        verification_case: str,
        uut: str,
        aircraft_type: str,
        parameter: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        u.WriteToLog(
            (
                "================================================================\n"
                "TEST CASE START\n"
                "Requirement: {req}   TestPoint: {tp}   TestCase: {tc}   VC: {vc}\n"
                "UUT: {uut}   Aircraft: {ac}\n"
                "Parameter: {param}\n"
                "================================================================"
            ).format(
                req=requirement_id,
                tp=testpoint,
                tc=testcase,
                vc=verification_case,
                uut=uut,
                ac=aircraft_type,
                param=parameter,
            ),
            color="green",
        )

        if extra:
            for k in sorted(extra.keys()):
                u.WriteToLog(f"  {k}: {extra[k]}", color="green")

    def log_case_end(self, status: str = "COMPLETED", extra: Optional[Dict[str, Any]] = None) -> None:
        u.WriteToLog(f"TEST CASE END: {status}", color="green")
        if extra:
            for k in sorted(extra.keys()):
                u.WriteToLog(f"  {k}: {extra[k]}", color="green")
        u.WriteToLog("================================================================\n")


class RequirementExample:
    """Example requirement runner."""

    REQUIREMENT_ID = "REQ-X"  # e.g. "2a"
    TESTPOINT = 1

    def __init__(self, ctx: RunContext):
        self.ctx = ctx
        self.h = ctx.h

    def run_all(self) -> None:
        testcase = 0

        for aircraft_type in ("passenger", "freighter"):
            for uut_base in ("lctc1",):
                testcase = self._run_for_uut_aircraft(uut_base, aircraft_type, testcase)

    def _run_for_uut_aircraft(self, uut_base: str, aircraft_type: str, testcase: int) -> int:
        # Signal-name helper: keeps the "uut::signal" format consistent.
        uut = f"{uut_base}::"

        def s(name: str) -> str:
            return f"{uut}{name}"

        # Testcase helper: keeps numbering + SetTestCase tied together.
        case_no = testcase

        def next_case(case_type: str = "normal") -> int:
            nonlocal case_no
            case_no += 1
            u.SetTestCase(self.TESTPOINT, case_no, type=case_type)
            return case_no

        aircraft_type_sig = s("aircraft_type")
        disable_label_inputs = s("k_disable_all_label_aquisition_inputs")
        disable_can_inputs = s("k_disable_all_can_inputs")

        self._set_aircraft_type(aircraft_type_sig, aircraft_type)
        self.h.set_many({disable_label_inputs: 1, disable_can_inputs: 1})
        self.h.settle(1.0)
        self.h.check_many({disable_label_inputs: 1, disable_can_inputs: 1})

        # Example: one table-driven loop, but each testcase still logs cleanly.
        params = [
            {"param": "flight_phase", "vc": "a"},
            {"param": "flight_phase", "vc": "b"},
        ]

        for p in params:
            tc = next_case("normal")
            self._case_example(uut_base, aircraft_type, tc, p["vc"], p["param"], s)

        self.h.set_many({disable_label_inputs: 0, disable_can_inputs: 0})
        self.h.settle(1.0)
        self.h.check_many({disable_label_inputs: 0, disable_can_inputs: 0})

        return case_no

    def _set_aircraft_type(self, signal: str, aircraft_type: str) -> None:
        value = 8 if aircraft_type == "freighter" else 7
        u.SetSignal(signal, value)
        u.sleep(1)
        u.CheckSignal(signal, value)

    def _case_example(self, uut_base: str, aircraft_type: str, testcase: int, vc: str, param: str, s) -> None:
        self.ctx.log_case_start(
            requirement_id=self.REQUIREMENT_ID,
            testpoint=self.TESTPOINT,
            testcase=testcase,
            verification_case=vc,
            uut=uut_base,
            aircraft_type=aircraft_type,
            parameter=param,
        )

        # Put your SetSignal/CheckSignal steps here.
        # Using `s("signal")` keeps the names readable.
        self.h.settle(1.0)

        self.ctx.log_case_end(status="COMPLETED")


def main() -> None:
    script_name = u.GetScriptName(__file__)
    ctx = RunContext(RunConfig(), script_name)

    with ctx.safe_run():
        ctx.initialize()

        with ctx.recording_scope():
            RequirementExample(ctx).run_all()

        ctx.report_errors()
        ctx.initialize()


if __name__ == "__main__":
    main()
```

---

## 4) Reviewer Checklist (Log-Focused)
A reviewer should be able to scan the log and see:
- A clear header before every test case
- Parameter and UUT clearly stated
- Test case boundaries (“START/END”)
- No missing context when loops iterate

If the reviewer has to guess what a log section corresponds to, add more structured log headers.

---

## 4) Notes (Practical, Not Academic)

- **DRY (Don't Repeat Yourself):** Use `Harness.set_many/check_many` and `SignalNamespace`.
- **Make Change Easy:** Put mappings (aircraft type codes, parameter labels) in one place.
- **Small Steps:** Refactor one script at a time; keep behavior identical.
- **Communicate Intent:** Names + log headers are more important than clever code.

---

If we like these patterns, we can standardize a couple things (like the log header shape) and keep the rest optional.
