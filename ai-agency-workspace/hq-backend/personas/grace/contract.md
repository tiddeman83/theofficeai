[ACCEPTS]
- `type: "portfolio_contribute"` from `hq_project_manager.py` → Grace.
- Required: `task_id`, `prompt`, `workspace_path`, `project_id`.
- Optional: `timeout` (300s default).

[EXECUTES]
- Scan the completed project for reusable components (patterns, utilities, schemas, architectures).
- For each artifact: create manifest.yaml with slug, summary, tags, language, originating_project, files list, added_at.
- Copy relevant code files to docs/portfolio/{slug}/assets/.
- Update docs/portfolio/_index.json to register new entries.

[OUTPUTS]
- New directories: docs/portfolio/{slug}/ with manifest.yaml + assets/ subdirectory.
- manifest.yaml in YAML format per the schema.
- _index.json updated atomically.
- Status JSON on `agency/status/{branch_id}`: {task_id, status: success|fail|error, file_changes, commit_hash}.

[REJECTS]
- workspace_path outside HQ_PROJECTS_DIR → `security_error`.
- Bouncer regex hit → `security_error`.
- Malformed manifest.yaml → `error`.

[NEVER]
- Create invalid YAML manifests (check structure).
- Overwrite existing portfolio entries without approval.
- Tag artifacts with vague or redundant tags.
