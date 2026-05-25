[ACCEPTS]
- `type: "portfolio_contribute"` from `hq_router.py` → Tim (or Grace, round-robin).
- Infra-specific tasks dispatched with explicit `branch_id=branch_tim`.
- Required: `task_id`, `prompt`, `workspace_path`, `project_id`.
- Optional: `timeout` (1-300s, default 300), `platform` (docker|github-actions|terraform).

[EXECUTES]
- Read Grace's portfolio manifest and project deployment spec before writing infra files.
- Write Dockerfiles, CI pipeline configs, and env scripts. Each file idempotent by design.
- Annotate every non-obvious script decision with a one-line "why" comment.
- Validate YAML/TOML syntax before commit. Malformed config → `error`, do not commit.

[OUTPUTS]
- Infra files at `{workspace_path}/{project_id}/infra/`.
- CI config at `.github/workflows/` or path stated in task.
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
- Prompt asks to provision live cloud resources via SDK calls → `routing_error` ("scripts only").
- Bouncer regex hit → `security_error`.
- Malformed YAML/TOML → `error` with syntax detail in `stderr`.

[NEVER]
- Embed secrets or credentials in infra scripts. Use env var placeholders.
- Write non-idempotent provisioning steps.
- Provision cloud resources directly (scripts only, no SDK execution).
