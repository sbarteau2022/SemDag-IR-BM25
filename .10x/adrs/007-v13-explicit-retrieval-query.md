# ADR-007: Keep the original task, send a compact retrieval query

Status: Accepted within owner-authorized protocol/throughput repair; no new permissions, model or evaluation gate.

Evidence: SDK-aligned discovery succeeds (list -> load semdag -> get_status). The next call spends about 101 seconds generating a full environment transcript inside prepare and then omits required outer skill_name. The backend only consumes this text as a retrieval/anchor query; it does not need copied conda installation output to expose the repository source.

Decision: keep the complete, unmodified original issue in the model input and original external verification task. Ask root to construct an explicit concise retrieval query containing title, exact error text and relevant traceback/symbol names, excluding installation transcripts. Do not truncate or rewrite it in a host adapter. Keep native prepare action/arity and all role/slot/hash guards unchanged. The actual submitted query is captured verbatim. This changes tool-query generation, not the user task or grading tests. No hidden prompts or inferred missing fields.

Alternative: continue full-ticket copying through a small-model tool call. Rejected for observed budget/correctness cost. Capturing the ticket in a host-provided runtime file or repairing missing SDK fields would add unauthorized runtime context/alter intent and is rejected.

Gates unchanged: actual E4B prepare -> managed edit -> outside-verified apply; resolution separately against unaltered task/test patch. Preserve the full-copy failure, no success claim from shorter output or component tests. Same case, roles, model and fixed token/time budgets. A concise query may omit useful anchors or select a wrong locus; original issue remains available to judge correctness, and failed localization/verification must stay failures.
