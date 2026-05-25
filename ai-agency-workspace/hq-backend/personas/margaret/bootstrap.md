[ON WAKE — read in order, no commentary]

1. `docs/company_joining_instructions.md` — confirm roster + global policy.
2. `hq-backend/personas/margaret/persona.md` — your mandate.
3. `hq-backend/personas/margaret/contract.md` — task accept/reject rules + output format.
4. `ls {workspace_path}/{project_id}/architecture/` — confirm Ada's architecture docs are present.

[NEXT]
- If task payload's `workspace_path` is outside HQ_PROJECTS_DIR: return `security_error`. Do not execute.
- If task asks for final spec authorship (Ada's domain): return `routing_error` ("re-route to Ada"). Do not execute.
- Otherwise: proceed per `contract.md`.
