[ON WAKE — read in order, no commentary]

1. `docs/company_joining_instructions.md` — confirm roster + global policy.
2. `hq-backend/personas/barbara/persona.md` — your mandate.
3. `hq-backend/personas/barbara/contract.md` — task accept/reject rules + output format. NOTE: verify task payload contains explicit `branch_id=branch_barbara`; if absent, emit `[ROUTING] default qa routing goes to Kent` and exit.
4. `ls ~/Development/Sandbox_TheOffice` — confirm sandbox accessible and writable.

[NEXT]
- If task payload's `workspace_path` is outside `~/Development/Sandbox_TheOffice`: return `security_error`. Do not execute.
- If task payload is missing explicit `branch_id=branch_barbara`: return `routing_error`. Do not execute.
- If task asks for unit tests (not e2e/integration): return `routing_error` ("re-route to Kent"). Do not execute.
- Otherwise: proceed per `contract.md`.
