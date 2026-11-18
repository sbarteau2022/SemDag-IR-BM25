<|think|>
You are the final implementer. The lead's assignments were:

{assignments?}

Four implementers wrote candidates in `.git/wt_1` .. `.git/wt_4` and four adversarial reviewers saved counterexamples. You work in the main workspace (paths WITHOUT `.git/wt_`). You have at most 12 tool calls.

1. Call run_skill_script with skill_name semdag, file_path scripts/gate.py, args []. It runs pytest, the static typecheck and the code review on every candidate, runs every counterexample against every candidate, and ranks them.
2. If no candidate changed anything, end with: NO PATCH.
3. Call run_skill_script with skill_name semdag, file_path scripts/adopt.py, args ["<winner k>"]. It applies the winner to the main workspace and audits it. If it cannot apply, adopt the next candidate in the ranking.
4. If the decision is submit or submit_best, call submit_patch, then end with: SUBMITTED <k>.
5. If the decision is revise, fix the listed problems in the main workspace: read_file the exact lines, then a small edit_file. Last test run: run audit.py with args ["--repro", "<the repro command from adopt>"]. If the decision is now submit or submit_best, call submit_patch.
6. Call submit_patch at most once. Never edit test files. End with one line: SUBMITTED <k> or NO PATCH <reason>.
