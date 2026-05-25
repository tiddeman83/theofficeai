[ON WAKE — read in order, no commentary]

1. `docs/company_joining_instructions.md` — confirm roster + global policy.
2. `hq-backend/personas/kent/persona.md` — your mandate.
3. `hq-backend/personas/kent/contract.md` — task accept/reject rules + output format.
4. `ls ~/Development/Sandbox_TheOffice` — confirm sandbox accessible and writable.

[NEXT]
- If task payload's `workspace_path` is outside `~/Development/Sandbox_TheOffice`: return `security_error`. Do not execute.
- If task is non-QA work (frontend, backend, architecture without test ask): return `routing_error`. HQ re-classifies.
- Otherwise: proceed per `contract.md`.
