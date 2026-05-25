[ACCEPTS]
- Tasks with explicit `branch_id=branch_barbara` in the payload ONLY.
- NOT activated by default `qa` or `uat` routing — the pool for those types is branch_kent (size 1).
- Required: `task_id`, `prompt`, `workspace_path` (absolute path under `~/Development/Sandbox_TheOffice`).
- Optional: `timeout` (1-300s, default 300), `framework` (pytest|playwright|cypress), `target`.

[POOL NOTE]
- QA pool is intentionally size-1 (branch_kent). Kent and Barbara MUST NOT race on the same test fixtures.
- Barbara is only activated when an operator explicitly sets `branch_id=branch_barbara`.
- Typical use case: Barbara handles e2e / integration automation; Kent handles unit tests; never concurrent on the same workspace.

[EXECUTES]
- Read target code and Kent's existing unit tests before writing automation tests.
- Write failing e2e/integration tests first. Run them to confirm they fail. Commit.
- Fix and run again. Report final status with pass/fail counts.
- Automation tests must be isolated: no shared mutable state between test cases.

[OUTPUTS]
- Test files at `tests/e2e/` or `tests/integration/` inside `workspace_path`.
- Run log at `tests/.barbara_run.log` (committed).
- MQTT response on `agency/status/branch_barbara`:
  ```json
  {
    "task_id": "<id>",
    "status": "pass|fail|error|security_error",
    "branch_name": "feature/task_<id>",
    "commit_hash": "<sha>",
    "passed": 0,
    "failed": 0,
    "errors": ["<verbatim failure>"],
    "file_changes": true,
    "stderr": ""
  }
  ```

[REJECTS]
- `workspace_path` outside sandbox → `security_error`.
- Task routed without explicit `branch_id=branch_barbara` (fallback: defer to Kent).
- Prompt asks for unit tests (Kent's domain) → `routing_error` ("re-route to Kent").
- Bouncer regex hit → `security_error`.

[NEVER]
- Run concurrently with Kent on the same `workspace_path`.
- Mark tests `skip` / `xit` without an open ticket reference.
- Modify production code in the same commit as automation tests.
