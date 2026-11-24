# v13 experimental delivery

Publish reviewed source, tests, native diagnostic utilities and evidence summaries to main by fast-forward; no Kaggle deployment or candidate promotion. Exclude reports/, raw request/model/task artifacts, datasets, credentials and unrelated untracked work. Root E4B config and four-minute/default-token budgets are unchanged. Package official validation, full tests, role engine equality and undefined-name lint pass.

Rollback is commit-based; preserve v6 and historical candidates. Sync canonical role assets using Tools/local/sync_v13_role_assets.py before validation. The final E4B run uses the official parity wrapper under Seatbelt/subprocess; stop only owned model/proxy listeners after observing completion and save a cleanup receipt. Never run Docker in this workstream.
