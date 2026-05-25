[ON WAKE — read in order, no commentary]

1. `docs/company_joining_instructions.md` — confirm roster + global policy.
2. `hq-backend/personas/tim/persona.md` — your mandate.
3. `hq-backend/personas/tim/contract.md` — task accept/reject rules + output format.
4. `ls {workspace_path}/{project_id}/` — confirm project directory accessible.

[NEXT]
- If task payload's `workspace_path` is outside HQ_PROJECTS_DIR: return `security_error`. Do not execute.
- If task asks to provision live cloud resources via SDK calls: return `routing_error` ("scripts only"). Do not execute.
- Otherwise: proceed per `contract.md`.
