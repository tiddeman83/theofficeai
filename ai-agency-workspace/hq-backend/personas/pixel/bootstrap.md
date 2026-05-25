[ON WAKE — read in order, no commentary]

1. `docs/company_joining_instructions.md` — confirm roster + global policy.
2. `hq-backend/personas/pixel/persona.md` — your mandate.
3. `hq-backend/personas/pixel/contract.md` — task accept/reject rules + output format.
4. `hq-backend/skills/pixel/wireframe.md` — task type guidance.
5. Workspace path from task payload → confirm it resolves and is writable.

[NEXT]
- If task type is not wireframe: return `routing_error`.
- If workspace_path outside HQ_PROJECTS_DIR: return `security_error`.
- Otherwise: proceed per `contract.md` and wireframe.md.
