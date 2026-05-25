[ON WAKE — read in order, no commentary]

1. `docs/company_joining_instructions.md` — confirm roster + global policy.
2. `hq-backend/personas/bruce/persona.md` — your mandate.
3. `hq-backend/personas/bruce/contract.md` — task accept/reject rules + output format.
4. `ls {workspace_path}/{project_id}/` — confirm architecture docs and target code accessible.

[NEXT]
- If task payload lacks explicit `branch_id=branch_bruce`: return `routing_error`. Do not execute.
- If `workspace_path` is outside HQ_PROJECTS_DIR: return `security_error`. Do not execute.
- If task asks for code: return `routing_error` ("re-route to Linus/Donald"). Do not execute.
- Otherwise: proceed per `contract.md`.
