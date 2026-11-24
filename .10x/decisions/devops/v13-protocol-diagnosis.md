# v13 experimental delivery

Publish reviewed source, tests, native diagnostic utilities and evidence summaries to main by fast-forward; no Kaggle deployment or candidate promotion. Exclude reports/, raw request/model/task artifacts, datasets, credentials and unrelated untracked work. Root E4B config and four-minute/default-token budgets are unchanged. Package official validation, full tests, role engine equality and undefined-name lint pass.

Rollback is commit-based; preserve v6 and historical candidates. Sync canonical role assets using Tools/local/sync_v13_role_assets.py before validation. The final E4B run uses the official parity wrapper under Seatbelt/subprocess; stop only owned model/proxy listeners after observing completion and save a cleanup receipt. Never run Docker in this workstream.

Final receipt: main fast-forward/push succeeded, raw artifacts excluded, owned listener PIDs2642/3412 stopped with command ownership checks; no remaining listeners on8124/8125. Local cleanup.json records this. Experimental delivery complete; no runtime promotion.

ADR-015 session cleanup verified the owned E4B vLLM process on port 8124 and the `v13_exact_edit_capability` proxy on port 8125 before terminating both. No listeners remain. Raw exact-edit requests, events, task snapshots, patches, telemetry, and grading artifacts stay local under `reports/v13_exact_edits_2026-11-24/`; only source, tests, diagnostic utilities, and evidence summaries are publishable. No Kaggle deployment or candidate promotion.
