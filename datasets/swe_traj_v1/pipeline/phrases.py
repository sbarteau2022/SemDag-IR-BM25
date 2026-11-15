"""Phrase banks for templated, observation-grounded reasoning.

Every slot is filled only with facts taken from real tool output or from the
injected-bug record, so the reasoning never states something the trajectory
did not observe. Several paraphrases per slot reduce stylistic overfitting.
"""
import random

R = random.Random()


def pick(options, **kw):
    return R.choice(options).format(**kw)


PLAN_SNIPPET = [
    "Plan: reproduce the report with a script in /tmp, localize from the traceback or the API it calls, make the smallest fix, re-run the repro plus the module's tests, then submit.",
    "First I'll reproduce the problem exactly as reported, using a throwaway script in /tmp so nothing leaks into the patch.",
    "Start by turning the snippet from the issue into /tmp/repro.py and running it. A concrete failure is better evidence than guessing.",
    "Reproduce first. I'll write the reported snippet to /tmp/repro.py (outside /workspace, so it can't end up in the diff) and run it.",
]
PLAN_CI = [
    "Plan: run only the failing test to see the exact failure, read what it expects, localize, apply a minimal fix, re-run that test and its file, then submit.",
    "I'll start by running just `{test}` to get the real failure output. No full-suite runs.",
    "Reproduce with the single failing test first, `{test}`, so every later step is grounded in the actual error.",
]
SAW_ASSERT = [
    "Reproduced: {err}. The result is wrong but nothing crashes, so the traceback won't point at the bug. I need to follow the API the snippet calls, `{api}`.",
    "The repro fails with {err}. That's a wrong value, not an exception from the library, so I'll locate `{api}`, which the snippet calls, and read it.",
    "Confirmed the bug: {err}. Since the failure is an assertion in the caller, the next step is the definition of `{api}`.",
]
SAW_TB = [
    "Reproduced: {err}. The traceback's innermost library frame is `{frame_func}` at {frame_file}:{frame_line}, so I'll read there first.",
    "The failure is {err}. It's raised inside the library, in `{frame_func}` ({frame_file}:{frame_line}). Reading that function.",
    "Got {err}. The traceback points into {frame_file} at line {frame_line} (`{frame_func}`), which is the best lead.",
]
READ_TEST = [
    "The test fails with {err}. Let me read the test body to see exactly which call and value it expects.",
    "Failure confirmed: {err}. Before touching the library I'll read the test to pin down the expected behaviour.",
]
AFTER_TEST_READ = [
    "The test calls `{api}` and checks its result. I'll find that definition.",
    "So the behaviour under test comes from `{api}`. Locating its definition next.",
]
GREP_PICK = [
    "`{name}` is defined in {file} at line {line}. Reading the function.",
    "Found it: {file}:{line}. I'll read just that function rather than the whole file.",
    "The definition I want is {file}:{line}{others}. Reading around it.",
]
CHAIN = [
    "`{api}` itself looks fine; it delegates the work to `{callee}`, which decides the result for this input. Following the call.",
    "Nothing wrong in `{api}` for this case. It hands off to `{callee}`, so that's where the faulty logic must be.",
    "`{api}` just forwards to `{callee}`. The bug has to be downstream, so I'll look up `{callee}`.",
]
WALK_UP = [
    "The exception surfaces here, but this function is only acting on the value it was given. The bad value comes from its caller in the traceback, `{caller}` ({file}:{line}). Moving up one frame.",
    "This frame just reacts to its input. One frame up, `{caller}` at {file}:{line} produces that input, so I'll check it.",
]
EDIT_RETRY = [
    "That line occurs more than once in the file, so the match isn't unique. I'll include the neighbouring line to anchor the edit.",
    "Not unique. Adding one line of context so the edit lands on the right occurrence.",
]
VERIFY_REPRO = [
    "Edit applied. Re-running the repro to confirm the fix.",
    "Now the same repro script again. It should pass.",
]
VERIFY_TEST = [
    "Edit applied. Re-running the failing test.",
    "Re-running `{test}` to confirm.",
]
REGRESS = [
    "The reported case passes now. Next, the module's test file, `{tfile}`, to check nothing nearby regressed. Only that file, not the full suite.",
    "Fixed for the reported input. A targeted regression check comes next: `{tfile}` only.",
    "Good. Running `{tfile}` as a scoped regression check.",
]
REGRESS_PREEXIST = [
    " The {n} remaining failure(s) are pre-existing: they also fail on the untouched base commit and are unrelated to `{func}`, so I'll leave them alone.",
]
DIFF = [
    "All green. A quick look at the diff to make sure it's minimal and touches no test files.",
    "Checking the final diff before submitting: it should be a single small hunk in source.",
]
SUBMIT = [
    "The fix is verified and minimal, and {calls} tool calls are used. Submitting.",
    "Repro and regression tests pass, and the diff is one focused change. Submitting now ({calls} calls used).",
    "Done. {calls} tool calls, the targeted tests pass, and the patch has no stray files. Submitting.",
]
FINAL = [
    "Fixed {where}: {what} The reported case now behaves as expected, and `{tfile}` passes.",
    "Root cause was in {where}. {what} Verified with the repro and `{tfile}`.",
    "Patched {where}. {what} Targeted tests pass.",
]

# family -> diagnosis text; {bad} {good} {func} {err} {cond}
DIAG = {
    "comparison": [
        "Line {line} decides this case with `{bad}`. For the reported input that comparison picks the wrong branch, which matches {err}. It should be `{good}`.",
        "The condition `{bad}` on line {line} is the suspect: it is what separates the reported input from the normal path, and it gets it wrong. `{good}` gives the expected result.",
        "Hypothesis: the comparison on line {line} is wrong. `{bad}` sends the reported input down the other branch. Changing it to `{good}` fixes the decision without touching anything else.",
    ],
    "logic": [
        "Line {line}'s condition `{bad}` has the wrong logic for this case. With the reported input it evaluates the opposite way from what the rest of `{func}` assumes. It should read `{good}`.",
        "The boolean logic on line {line} is the bug: `{bad}` should be `{good}`. As written, it takes the wrong branch for the input in the issue.",
    ],
    "arithmetic": [
        "Line {line} computes `{bad}`, which is off by one or has the wrong sign for this case. That explains {err}. It should be `{good}`.",
        "The arithmetic on line {line} is wrong: `{bad}` versus the intended `{good}`. That's consistent with {err}.",
    ],
    "constant": [
        "Line {line} returns `{bad}` on this path, but this branch should report `{good}`. That flip explains {err}.",
        "This branch hard-codes `{bad}`; the expected behaviour needs `{good}` here.",
    ],
    "indexing": [
        "Line {line} uses `{bad}`, which takes the wrong element/range of the sequence. The issue's output fits that. It should be `{good}`.",
        "Indexing bug on line {line}: `{bad}` should be `{good}`.",
    ],
    "api_misuse": [
        "Line {line} calls `{bad}`, the wrong function or method for what `{func}` is doing. The intended call is `{good}`.",
        "`{bad}` on line {line} is the mirror image of what's needed here. It should be `{good}`, which is what the surrounding code and the expected output imply.",
    ],
    "call_args": [
        "Line {line} passes its arguments in the wrong order: `{bad}`. Swapping them back to `{good}` matches the callee's signature and the expected output.",
        "The call on line {line}, `{bad}`, has its two arguments transposed. It should be `{good}`.",
    ],
    "wrong_return": [
        "Line {line} returns None even though `{func}` has already computed the result. The value is dropped, which explains {err}. It should be `{good}`.",
        "`{func}` builds the right value but then returns None on line {line}. It should return the computed value: `{good}`.",
    ],
    "missing_check": [
        "`{func}` never checks `{cond}`. The reported input hits exactly that case, and execution falls through to code that assumes it can't happen, hence {err}. I'll restore the guard: `{good}`.",
        "There's no handling for `{cond}` in `{func}`, and the issue's input is that edge case. Adding the missing guard (`{good}`) before the main logic fixes it.",
    ],
}
