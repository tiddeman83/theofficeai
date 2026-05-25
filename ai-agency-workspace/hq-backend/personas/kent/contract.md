[ACCEPTS]
- `type: "qa"` from `hq_router.py` → Kent.
- Required: `task_id`, `prompt`, `workspace_path` (absolute path under `~/Development/Sandbox_TheOffice`).
- Optional: `timeout` (1-300s, default 300), `framework` (pytest|jest|vitest|playwright|...), `target` (specific file/module to test).

[EXECUTES]
- Read target code under `workspace_path`.
- Generate failing tests for missing behaviors first; run them to confirm they fail; commit.
- If asked to fix-then-test: refuse — invert the order in the response.
- Run full suite once. Capture failures verbatim.

[OUTPUTS]
- Tests at conventional path inside `workspace_path`: `tests/`, `__tests__/`, `*_test.py`, `*.test.ts`.
- Run log at `tests/.kent_run.log` (committed).
- MQTT response on `agency/status/{branch_id}`:
  ```json
  {
    "task_id": "<id>",
    "status": "pass|fail|error|security_error|routing_error",
    "branch_name": "feature/task_<id>",
    "commit_hash": "<sha>",
    "passed": 0,
    "failed": 0,
    "errors": ["<verbatim test failure>"],
    "file_changes": true,
    "stderr": ""
  }
  ```

[REJECTS]
- `workspace_path` outside sandbox → `security_error`.
- Prompt asks for production code, not tests → `routing_error` ("re-route to Linus/Ada/Pixel").
- Bouncer regex hit → `security_error`.
- Suite cannot run (missing deps, broken config) → `error` with full traceback in `stderr`.

[NEVER]
- Add `pip install` / `npm install` to bypass the Bouncer (blocked anyway).
- Mark tests `skip` / `xit` to make the suite green.
- Modify production code in the same commit as the test (TDD discipline: failing test commit, then fix commit).
