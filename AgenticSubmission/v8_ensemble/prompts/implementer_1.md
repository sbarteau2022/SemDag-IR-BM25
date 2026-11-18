<|think|>
You are implementer 1 of 4. The lead has reviewed the code and assigned the work:

{assignments?}

Do the line that starts with ASSIGN 1. Your own copy of the repository already exists at `.git/wt_1`. You have at most 10 tool calls.

1. Read the code you were assigned in your copy: read_file(".git/wt_1/<file>").
2. Reproduce: create `/tmp/repro_1.py` with run_command (heredoc) that imports the package and asserts the CORRECT behaviour from the issue. Run it with: cd /workspace/.git/wt_1 && PYTHONPATH=src:. python /tmp/repro_1.py  (it must fail now).
3. Fix: run_skill_script with skill_name semdag, file_path scripts/edit.py, args ["1", "<file path as in the repo>", "<exact old text>", "<new text>"]. It always writes into your copy. If it answers with a block reference such as "@1", call it again with "@1" as the old text. Smallest change at the root cause. Never edit test files.
4. Run the repro again (same command). It must pass.
5. Audit: run_skill_script with skill_name semdag, file_path scripts/audit.py, args ["--wt", "1", "--repro", "cd /workspace/.git/wt_1 && PYTHONPATH=src:. python /tmp/repro_1.py"]. If the decision is revise and you have calls left, fix once more and audit again.
6. End with exactly one line: CANDIDATE 1 <audit decision> <one-sentence summary of the change>.

Write argument values plainly: no extra quotes inside them. Change code only with edit.py. Never run the full test suite.
