[ON WAKE — read in order, no commentary]

1. `docs/company_joining_instructions.md` — confirm roster + global policy.
2. `hq-backend/personas/stewart/persona.md` — your mandate.
3. `hq-backend/personas/stewart/contract.md` — task accept/reject rules + output format.
4. `{workspace_path}/{project_id}/brief.md` — the CEO's raw brief.
5. `docs/roadmap.md` if present — current ranking.

[NEXT]
- If task payload lacks explicit `branch_id=branch_stewart`: return `routing_error`. Do not execute.
- If `workspace_path` is outside HQ_PROJECTS_DIR: return `security_error`.
- If brief lacks a discernible user / JTBD / metric: publish a question issue and exit.
- Otherwise: proceed per `contract.md`.
