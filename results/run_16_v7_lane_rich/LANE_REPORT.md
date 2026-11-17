# Lane report: run_16_v7_rich

**Resolved 1/5** (reference run_10_v6: 1/5 on the same tasks)

Broke at: {'executor': 1, 'auditor': 2, 'verify': 1, 'none': 1}

| task | resolved | ref | broke at | rounds | plan ok | repro runs | edits ok/tried | audit decisions | submitted | s plan/exec/audit | tok plan/exec/audit | peak ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rich_3043 | no | destructive_write | executor | 1 | 1 | 0 | 0/0 | - | 0 | 125/74/20 | 6863/4096/1024 | 0.29 |
| rich_3052 | no | right_function_wrong_fix | auditor | 2 | 1 | 0 | 3/3 | revise | 0 | 88/189/11 | 4744/10302/529 | 0.33 |
| rich_3180 | no | right_function_wrong_fix | auditor | 2 | 1 | 0 | 2/2 | revise | 0 | 78/214/2 | 4288/11920/101 | 0.19 |
| rich_3296 | no | right_file_wrong_function | verify | 3 | 1 | 0 | 2/2 | revise | 1 | 146/91/22 | 8028/5091/1193 | 0.15 |
| rich_3468 | YES | YES | none | 1 | 1 | 0 | 1/1 | - | 0 | 13/281/0 | 653/13764/0 | 0.61 |

Time share by role: planner 33%, executor 63%, auditor 4%
