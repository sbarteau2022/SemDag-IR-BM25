# Lane report: run_14_v7_requests

**Resolved 0/5** (reference run_10_v6: 1/5 on the same tasks)

Broke at: {'planner': 3, 'verify': 2}

| task | resolved | ref | broke at | rounds | plan ok | repro runs | edits ok/tried | audit decisions | submitted | s plan/exec/audit | tok plan/exec/audit | peak ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| requests_6644 | no | wrong_file | planner | 0 | 0 | 0 | 0/0 | - | 0 | 0/0/0 | 0/0/0 | 0.00 |
| requests_7427 | no | YES | planner | 0 | 0 | 0 | 0/0 | - | 0 | 0/0/0 | 0/0/0 | 0.00 |
| requests_7433 | no | destructive_write | planner | 0 | 0 | 0 | 0/0 | - | 0 | 0/0/0 | 0/0/0 | 0.00 |
| requests_7502 | no | right_function_wrong_fix | verify | 2 | 1 | 2 | 1/2 | revise,submit_best,submit_best | 1 | 80/50/24 | 4009/2579/1165 | 0.16 |
| requests_7505 | no | right_file_wrong_function | verify | 3 | 1 | 2 | 1/2 | revise | 1 | 118/75/27 | 5967/3887/1393 | 0.17 |

Time share by role: planner 53%, executor 34%, auditor 14%
