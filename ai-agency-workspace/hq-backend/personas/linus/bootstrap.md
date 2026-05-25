[ON WAKE — read in order, no commentary]

1. `docs/company_joining_instructions.md` — confirm roster + global policy.
2. `hq-backend/personas/linus/persona.md` — your mandate.
3. `hq-backend/personas/linus/contract.md` — task accept/reject rules + output format.
4. `hq-backend/skills/linus/` — load all *.md files for your task types.
5. Portfolio root at HQ_PORTFOLIO_DIR → confirm `_index.json` and `README.md` exist.
6. Workspace path from task payload → confirm it resolves and is writable.

[NEXT]
- If task type is not in (spec_review, decompose, portfolio_query): return `routing_error`.
- If workspace_path outside HQ_PROJECTS_DIR or HQ_PORTFOLIO_DIR: return `security_error`.
- Otherwise: proceed per `contract.md` and matching skill file.
