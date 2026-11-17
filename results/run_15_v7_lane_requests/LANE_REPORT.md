# Lane report: run_15_v7_requests

**Resolved 1/5** (reference run_10_v6: 1/5 on the same tasks)

Broke at: {'auditor': 2, 'none': 1, 'verify': 1, 'executor': 1}

| task | resolved | ref | broke at | rounds | plan ok | repro runs | edits ok/tried | audit decisions | submitted | s plan/exec/audit | tok plan/exec/audit | peak ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| requests_6644 | no | wrong_file | auditor | 1 | 1 | 0 | 1/1 | - | 0 | 61/224/0 | 3273/12642/0 | 0.28 |
| requests_7427 | YES | YES | none | 1 | 1 | 0 | 1/4 | - | 0 | 80/218/0 | 4414/11933/0 | 0.24 |
| requests_7433 | no | destructive_write | verify | 3 | 1 | 0 | 2/2 | revise,submit_best,submit_best,submit_best | 1 | 103/89/29 | 5684/4997/1468 | 0.24 |
| requests_7502 | no | right_function_wrong_fix | executor | 1 | 1 | 0 | 0/5 | - | 0 | 17/264/0 | 896/14884/0 | 0.21 |
| requests_7505 | no | right_file_wrong_function | auditor | 2 | 1 | 2 | 1/1 | - | 1 | 90/48/3 | 4968/2662/169 | 0.15 |

Time share by role: planner 29%, executor 69%, auditor 3%
