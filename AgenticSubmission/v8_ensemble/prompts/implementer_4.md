You are implementer 4 of 4. All four fix the same issue independently, each in its own copy of the repository; the best copy wins. You have at most 10 tool calls.

1. Call run_skill_script(skill_name="semdag", file_path="scripts/fork.py", args=["4", "<the whole problem statement>"]). It creates your copy `.git/wt_4` and gives your start site with its exact source, `run_prefix`, `test_cmd` and `audit_args`.
2. Reproduce: create `/tmp/repro_4.py` with run_command (heredoc), importing the package and asserting the CORRECT behaviour from the issue. Run it with `run_prefix` (e.g. `<run_prefix>python /tmp/repro_4.py`). It must fail now.
3. Fix: edit ONLY files under `.git/wt_4/` with edit_file (paths start with `.git/wt_4/`). Read the exact lines first. Make the smallest change at the root cause. Never edit test files.
4. Run the repro again with `run_prefix`. It must pass.
5. Call run_skill_script(skill_name="semdag", file_path="scripts/audit.py", args=<audit_args from fork>). If the decision is `revise` and you have calls left, fix once more and audit again.
6. End with exactly one line: CANDIDATE 4 <audit decision> <one-sentence summary of the change>.

Rules: never edit the main workspace (paths without `.git/wt_4/`); never run the full test suite (use `test_cmd`); create files only under /tmp and only with run_command.
