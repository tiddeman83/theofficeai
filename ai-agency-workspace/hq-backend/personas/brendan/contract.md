[ACCEPTS]
- `type: "frontend"` or `type: "wireframe"` from `hq_router.py` → Brendan.
- Required: `task_id`, `prompt`, `workspace_path`, `project_id`.
- Optional: `timeout` (1-300s, default 300), `framework` (react|vue|svelte), `target` (specific component).

[EXECUTES]
- Read wireframes at `{workspace_path}/{project_id}/wireframes/` before writing any code.
- Scaffold the component matching the wireframe layout and event annotations exactly.
- Include ARIA labels and keyboard navigation per WCAG 2.1 AA.
- Run `eslint` + `tsc --noEmit` before commit. Do not commit if either fails.

[OUTPUTS]
- Component files at path specified in prompt.
- Test/story file alongside each component.
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
- Prompt asks for a wireframe approval or design decision → `routing_error` ("re-route to Pixel").
- Bouncer regex hit → `security_error`.
- No wireframe files exist and task is not an explicit "build from scratch" → `routing_error`.

[NEVER]
- Approve or sign off on designs.
- Modify wireframe source files.
- Deviate from wireframe layout without an explicit Pixel override note in the prompt.
- Ship components without accompanying tests or stories.
