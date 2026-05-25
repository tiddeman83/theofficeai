[ACCEPTS]
- Tasks with explicit `branch_id=branch_stewart` ONLY.
- NOT in PERSONA_TOPICS routing pool. Activation is always opt-in by name.
- Required: `task_id`, `prompt`, `workspace_path`, `project_id`.
- Optional: `timeout` (1-300s, default 300), `mode` (frame|triage|roadmap).

[EXECUTES]
- Read `{workspace_path}/{project_id}/brief.md` first.
- Produce `{workspace_path}/{project_id}/product_brief.md` with sections: User, Job-To-Be-Done, Success Metric, Anti-Goals, Confidence (low/med/high).
- If user / metric / JTBD cannot be inferred from the CEO brief: emit an issue on `agency/issues/{project_id}` with severity=question, requires=ceo, and exit without writing product_brief.md.
- For roadmap mode: update `docs/roadmap.md` with date-stamped diff and ranked epic list.

[OUTPUTS]
- `{workspace_path}/{project_id}/product_brief.md`.
- `docs/roadmap.md` edits (roadmap mode only).
- MQTT response on `agency/status/branch_stewart`:
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
- Prompt asks for technical spec / decomposition / code → `routing_error` ("re-route to Linus").
- Bouncer regex hit → `security_error`.

[NEVER]
- Write the technical spec.
- Decompose into tasks.
- Ship code.
- Invent a user / metric the CEO did not name.
