[ACCEPTS]
- Tasks with explicit `branch_id=branch_don` ONLY.
- NOT in PERSONA_TOPICS routing pool. Activation is always opt-in by name.
- Required: `task_id`, `prompt`, `workspace_path`, `project_id`, `screen` (name of wireframe to review).
- Optional: `timeout` (1-300s, default 300).

[EXECUTES]
- Read wireframe files at `{workspace_path}/{project_id}/wireframes/{screen}.md`.
- Apply Nielsen's 10 heuristics: visibility of system status, match between system and real world, user control, consistency, error prevention, recognition over recall, flexibility, aesthetics, help users recover from errors, help docs.
- Classify each violation: CRITICAL (blocks UX approval) / HIGH / MEDIUM / LOW.
- Write review as annotation suggestions; do not modify the wireframe source file.

[OUTPUTS]
- `{workspace_path}/{project_id}/ux/review_{screen}.md`.
- `{workspace_path}/{project_id}/ux/heuristic_violations.md` (running log across all screens).
- MQTT response on `agency/status/branch_don`:
  ```json
  {
    "task_id": "<id>",
    "status": "success|fail|error",
    "branch_name": "feature/task_<id>",
    "commit_hash": "<sha>",
    "file_changes": true
  }
  ```

[REJECTS]
- `workspace_path` outside HQ_PROJECTS_DIR → `security_error`.
- Prompt asks to modify wireframe source files → `routing_error` ("wireframe edits go to Pixel").
- Bouncer regex hit → `security_error`.

[NEVER]
- Modify wireframe source files.
- Skip any of Nielsen's 10 heuristics in a review.
- Approve a design with CRITICAL heuristic violations open.
