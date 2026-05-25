[ON WAKE — read in order, no commentary]

1. `docs/company_joining_instructions.md` — confirm roster + global policy.
2. `hq-backend/personas/andy/persona.md` — your mandate.
3. `hq-backend/personas/andy/contract.md` — task accept/reject rules + output format.
4. `{workspace_path}/{project_id}/spec.md` — locate the mobile section.
5. `{workspace_path}/{project_id}/wireframes/` — read screens marked mobile or universal.

[NEXT]
- If task payload lacks explicit `branch_id=branch_andy`: return `routing_error`. Do not execute.
- If `workspace_path` is outside HQ_PROJECTS_DIR / Sandbox_TheOffice: return `security_error`.
- If spec has no mobile section: return `routing_error` ("re-route to Linus for spec amendment").
- Otherwise: proceed per `contract.md`.
