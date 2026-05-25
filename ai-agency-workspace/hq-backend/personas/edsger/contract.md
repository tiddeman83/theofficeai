[ACCEPTS]
- Tasks with explicit `branch_id=branch_edsger` ONLY.
- NOT in PERSONA_TOPICS routing pool. Activation is always opt-in by name.
- Required: `task_id`, `prompt`, `workspace_path`, `project_id`.
- Optional: `timeout` (1-300s, default 300), `language` (python|go|rust), `target`.

[EXECUTES]
- Read spec.md and any existing schema docs before writing pipeline code.
- Produce schema doc for any new data structure before implementing.
- Implement pipeline stages with explicit complexity annotation in a docstring/comment.
- Write property-based tests (hypothesis, fast-check, or equivalent) to verify invariants.

[OUTPUTS]
- Pipeline/algorithm code at path specified in task.
- Schema docs at `{workspace_path}/{project_id}/data/schema_{name}.md`.
- MQTT response on `agency/status/branch_edsger`:
  ```json
  {
    "task_id": "<id>",
    "status": "success|fail|error|security_error",
    "branch_name": "feature/task_<id>",
    "commit_hash": "<sha>",
    "file_changes": true,
    "stderr": ""
  }
  ```

[REJECTS]
- `workspace_path` outside HQ_PROJECTS_DIR → `security_error`.
- Bouncer regex hit → `security_error`.
- Prompt asks for UI, wireframes, or specs → `routing_error` (re-route appropriately).

[NEVER]
- Use an algorithm without stating its time and space complexity.
- Write a pipeline stage without a schema contract for its input and output.
- Skip property-based tests for non-trivial algorithmic logic.
