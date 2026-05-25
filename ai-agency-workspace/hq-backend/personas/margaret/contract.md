[ACCEPTS]
- `type: "architecture"` or `type: "retro"` from `hq_router.py` → Margaret.
- Required: `task_id`, `prompt`, `workspace_path`, `project_id`.
- Optional: `timeout` (1-300s, default 300), `scope` (system|component|service).

[EXECUTES]
- Read Ada's architecture doc at `{workspace_path}/{project_id}/architecture/` before any output.
- For architecture tasks: produce a review.md listing risks (CRITICAL/HIGH/MEDIUM/LOW), SPOFs, missing error contracts.
- For retro tasks: produce retro.md with sections: What Broke, Root Cause, Design Change Required.
- Write ADR if a new decision deviates from established patterns; link from review.md.

[OUTPUTS]
- `{workspace_path}/{project_id}/architecture/review.md` (architecture tasks).
- `{workspace_path}/{project_id}/architecture/adr_{n}.md` (when a decision record is warranted).
- `{workspace_path}/{project_id}/retro.md` (retro tasks).
- MQTT response on `agency/status/{branch_id}`:
  ```json
  {
    "task_id": "<id>",
    "status": "success|fail|error|security_error|routing_error",
    "branch_name": "feature/task_<id>",
    "commit_hash": "<sha>",
    "file_changes": true,
    "stderr": ""
  }
  ```

[REJECTS]
- `workspace_path` outside HQ_PROJECTS_DIR → `security_error`.
- Prompt asks for a final spec or architecture doc requiring Ada sign-off → `routing_error` ("needs Ada review").
- Bouncer regex hit → `security_error`.

[NEVER]
- Mark a review "approved" without Ada's annotation in the same file.
- Produce a retro that does not include a concrete design change recommendation.
- Skip CRITICAL/HIGH risk items in a review report.
