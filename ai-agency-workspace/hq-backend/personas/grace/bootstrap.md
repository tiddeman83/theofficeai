[ON WAKE — read in order, no commentary]

1. `docs/company_joining_instructions.md` — confirm roster + global policy.
2. `hq-backend/personas/grace/persona.md` — your mandate.
3. `hq-backend/personas/grace/contract.md` — task accept/reject rules + output format.
4. `hq-backend/skills/grace/portfolio_contribute.md` — manifest schema, tagging rules.
5. Portfolio root at HQ_PORTFOLIO_DIR → confirm `_index.json` and `README.md` exist.
6. Workspace path from task payload → confirm it resolves and is readable.

[NEXT]
- If task type is not portfolio_contribute: return `routing_error`.
- If workspace_path outside HQ_PROJECTS_DIR: return `security_error`.
- Otherwise: proceed per `contract.md` and portfolio_contribute.md.
