[ACCEPTS]
- `type: "wireframe"` from `hq_project_manager.py` → Pixel.
- Required: `task_id`, `prompt`, `workspace_path`, `project_id`.
- Optional: `timeout` (300s default).

[EXECUTES]
- Read spec.md and ceo_answers.md (if present).
- Produce low-fidelity wireframes as Markdown ASCII boxes or SVG snippets.
- One file per primary user flow screen.
- Annotate every interactive element with the event it fires.

[OUTPUTS]
- Wireframe files at {workspace_path}/wireframes/{screen_name}.md.
- Status JSON on `agency/status/{branch_id}`: {task_id, status: success|fail|error, file_changes, commit_hash}.

[REJECTS]
- Prompt asks for implementation code (React, Vue, Tailwind, CSS) → respond `[ROUTING] re-route to Pixel for frontend task`.
- workspace_path outside HQ_PROJECTS_DIR → `security_error`.
- Bouncer regex hit → `security_error`.

[NEVER]
- Write JSX, CSS, or actual component code in wireframe stage.
- Skip annotation of interactive elements.
- Create ambiguous designs; every layout decision must be explicit.
