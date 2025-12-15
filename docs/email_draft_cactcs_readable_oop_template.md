# Email draft: Readable CACTCS Script Template

**Subject:** Proposal: a readable template style for new CACTCS test scripts

Hi team,

I wanted to share a lightweight template/style suggestion for **new** CACTCS Python test scripts. Nothing here is meant to be “the one true way” — it’s just a pattern that’s been helping make scripts easier to follow during log review and easier to maintain when requirements change.

I’ve attached a template you can copy/paste and adapt:
- `CACTCS_Test_Script_Template_Readable_OOP(1).md`

A few things this style tries to improve (in a practical, review-friendly way):
- **Logs that read like a test report**: clearer boundaries for each test case (start/end), plus the key context (Req/TP, testcase number, VC label, UUT, aircraft type, parameter under test).
- **Less repetitive “plumbing”**: small helpers for `set_many/check_many` and signal naming so the test intent is easier to spot.
- **Safer lifecycle handling**: a simple run context pattern to help ensure rig/log/recording cleanup happens consistently.
- **More reliable testcase tracking**: a `next_case()` helper so we increment/register testcases consistently and don’t have `testcase += 1` scattered around loops.

My thought is: for any **new scripts** (or when we touch an existing one for a larger change), we try to follow something like this structure so the team’s scripts look/feel consistent and log review stays fast.

If you have preferences on the logging header format, helper names, or what you want standardized vs optional, I’m happy to tweak the template. Totally open to feedback.

Thanks,

<Your Name>
