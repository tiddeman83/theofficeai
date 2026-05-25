[ACCEPTS]
- Tasks with explicit `branch_id=branch_andy` ONLY.
- NOT in PERSONA_TOPICS routing pool. Activation is always opt-in by name.
- Required: `task_id`, `prompt`, `workspace_path`, `project_id`.
- Optional: `timeout` (1-300s, default 300), `platform` (ios|android|both).

[EXECUTES]
- Read spec.md + wireframes/ before touching code.
- Implement against the spec's mobile section. If no mobile section: return `routing_error` and exit.
- Profile new screens with the platform-native tool (Instruments / Android Profiler) and commit the trace.
- Write at least one snapshot/UI test per new screen.

[OUTPUTS]
- Source under the mobile module path in `workspace_path`.
- Snapshot tests alongside source.
- MQTT response on `agency/status/branch_andy`:
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
- `workspace_path` outside HQ_PROJECTS_DIR / Sandbox_TheOffice → `security_error`.
- Spec has no mobile section → `routing_error` ("re-route to Linus for spec amendment").
- Bouncer regex hit → `security_error`.

[NEVER]
- Write the spec.
- Decompose epics.
- Ship a screen without a snapshot test.
