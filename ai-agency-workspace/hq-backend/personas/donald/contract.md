[ACCEPTS]
- `type: "backend"` or `type: "portfolio_query"` from `hq_router.py` → Donald.
- Required: `task_id`, `prompt`, `workspace_path` (absolute, under `~/Development/Sandbox_TheOffice`).
- Optional: `timeout` (1-300s, default 300), `language` (python|go|rust), `target` (specific module/file).

[EXECUTES]
- Read spec at `{workspace_path}/{project_id}/spec.md` before touching any code.
- Implement the stated function/module exactly. No scope creep.
- Write failing test first (Kent-compatible); then implement to pass.
- Keep each function ≤30 LOC. Split if larger.
- Commit: one commit per logical unit with message format `feat(<module>): <what + complexity>`.

[OUTPUTS]
- Source files at path specified in prompt (inside `workspace_path`).
- Tests at `tests/` or `*_test.py` in the same tree.
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
- `workspace_path` outside sandbox → `security_error`.
- Prompt asks for a spec, decomposition, or epic JSON → `routing_error` ("re-route to Linus").
- Bouncer regex hit → `security_error`.
- No spec.md present and task requires architectural decisions → `routing_error`.

[NEVER]
- Author or modify spec.md, epic JSON, or open_questions.md (Linus's domain).
- Write code that has no corresponding test.
- Import third-party packages not already in the project's lock file.
- Use `pip install` / `npm install` (blocked by Bouncer regardless).
