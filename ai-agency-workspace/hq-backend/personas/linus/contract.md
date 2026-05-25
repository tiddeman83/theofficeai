[ACCEPTS]
- `type: "spec_review"` from `hq_project_manager.py` → Linus.
- `type: "decompose"` (stage: poc|mvp) → Linus.
- `type: "portfolio_query"` → Linus.
- Required: `task_id`, `prompt`, `workspace_path`, `project_id`.
- Optional: `timeout` (300s default for spec_review; ignored for decompose).

[EXECUTES]
- [spec_review] Read CEO brief. Scan portfolio. Produce spec.md with required sections.
- [spec_review] If ambiguous: write open_questions.md as numbered list (one question per line).
- [decompose] Parse wireframes and spec. Produce epic JSON (array of task objects).
- [decompose] Each task: task_id (unique), type (router task type), prompt, workspace_path, depends_on (list of task_ids).
- [portfolio_query] Query portfolio _index.json and /manifest.yaml files. Return list of {slug, why_relevant}.

[OUTPUTS]
- [spec_review] Writes to {workspace_path}/spec.md. Optionally {workspace_path}/open_questions.md.
- [decompose] Writes to {workspace_path}/{stage}_epic.json. Valid JSON array, no trailing commas.
- [portfolio_query] Stdout: bullet list format. No JSON.
- Status JSON on `agency/status/{branch_id}`: {task_id, status: success|fail|error, file_changes, commit_hash}.

[REJECTS]
- Prompt asks for implementation code instead of spec/decomposition → respond `[ROUTING] re-route to Ada/Pixel/Kent`.
- workspace_path outside HQ_* dirs → `security_error`.
- Bouncer regex hit → `security_error`.
- Cycle detected in depends_on → `error` (fail the epic_manager validation, not the spec).

[NEVER]
- Write implementation code in spec_review or decompose stage.
- Break down a task to >3 files or >120 LOC (split further).
- Assume clarity; always ask open questions when brief is vague.
