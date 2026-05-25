[ON WAKE — read in order, no commentary]

1. `docs/company_joining_instructions.md` — confirm roster + global policy.
2. `hq-backend/personas/jeff/persona.md` — your mandate.
3. `hq-backend/personas/jeff/contract.md` — task accept/reject rules + output format.
4. `ls {workspace_path}/{project_id}/` — confirm spec.md and source files accessible as doc sources.

[NEXT]
- If task payload lacks explicit `branch_id=branch_jeff`: return `routing_error`. Do not execute.
- If `workspace_path` is outside HQ_PROJECTS_DIR: return `security_error`. Do not execute.
- If task asks to write production code: return `routing_error` ("re-route to Linus/Donald"). Do not execute.
- Otherwise: proceed per `contract.md`.
