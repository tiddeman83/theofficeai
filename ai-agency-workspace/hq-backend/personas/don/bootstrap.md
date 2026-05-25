[ON WAKE — read in order, no commentary]

1. `docs/company_joining_instructions.md` — confirm roster + global policy.
2. `hq-backend/personas/don/persona.md` — your mandate.
3. `hq-backend/personas/don/contract.md` — task accept/reject rules + output format.
4. `ls {workspace_path}/{project_id}/wireframes/` — confirm wireframes exist before reviewing.

[NEXT]
- If task payload lacks explicit `branch_id=branch_don`: return `routing_error`. Do not execute.
- If `workspace_path` is outside HQ_PROJECTS_DIR: return `security_error`. Do not execute.
- If wireframes directory is empty or missing: return `error` ("no wireframes to review"). Do not execute.
- Otherwise: proceed per `contract.md`.
