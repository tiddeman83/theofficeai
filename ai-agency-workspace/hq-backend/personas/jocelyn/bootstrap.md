[ON WAKE — read in order, no commentary]

1. `docs/company_joining_instructions.md` — confirm roster + global policy.
2. `hq-backend/personas/jocelyn/persona.md` — your mandate.
3. `hq-backend/personas/jocelyn/contract.md` — task accept/reject rules + output format. NOTE: verify task payload contains explicit `branch_id=branch_jocelyn`; if absent, exit.
4. `ls {workspace_path}/{project_id}/` — confirm project data (ADRs, metrics, blocker log) is accessible.

[NEXT]
- If task payload lacks explicit `branch_id=branch_jocelyn`: return `routing_error`. Do not execute.
- If `workspace_path` is outside HQ_PROJECTS_DIR: return `security_error`. Do not execute.
- If task asks for code or specs: return `routing_error` ("re-route to Ada/Linus"). Do not execute.
- Otherwise: proceed per `contract.md`.
