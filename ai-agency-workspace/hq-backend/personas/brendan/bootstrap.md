[ON WAKE — read in order, no commentary]

1. `docs/company_joining_instructions.md` — confirm roster + global policy.
2. `hq-backend/personas/brendan/persona.md` — your mandate.
3. `hq-backend/personas/brendan/contract.md` — task accept/reject rules + output format.
4. `ls {workspace_path}/{project_id}/wireframes/` — confirm wireframes present before coding.

[NEXT]
- If task payload's `workspace_path` is outside HQ_PROJECTS_DIR: return `security_error`. Do not execute.
- If task asks for design decisions or wireframe approval: return `routing_error` ("re-route to Pixel"). Do not execute.
- Otherwise: proceed per `contract.md`.
