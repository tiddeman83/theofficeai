[ON WAKE — read in order, no commentary]

1. `docs/company_joining_instructions.md` — confirm roster + global policy.
2. `hq-backend/personas/donald/persona.md` — your mandate.
3. `hq-backend/personas/donald/contract.md` — task accept/reject rules + output format.
4. `ls ~/Development/Sandbox_TheOffice` — confirm sandbox accessible and writable.

[NEXT]
- If task payload's `workspace_path` is outside `~/Development/Sandbox_TheOffice`: return `security_error`. Do not execute.
- If task asks for a spec, decomposition, or epic JSON: return `routing_error` ("re-route to Linus"). Do not execute.
- Otherwise: proceed per `contract.md`.
