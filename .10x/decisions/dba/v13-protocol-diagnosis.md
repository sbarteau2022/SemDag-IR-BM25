# v13 native state and telemetry

No database migration. SQLite telemetry schema is unchanged. Optional exact request bodies live in owner-only local files; HTTP headers are not captured, and bodies/task material are neither ingested nor published. Transaction metadata remains task/slot-specific with current handles, assignment marker and candidate-hash verification failure. New ownership/continuation fields are computed response data. The Git baseline/file cache is operation-local memory, never persisted or shared across tasks.
