[TASK] spec_review

[PROCESS]
1. Read the CEO brief at {project_dir}/brief.md.
2. Scan portfolio (query_portfolio skill) for matching patterns, tags, and existing solutions.
3. If anything in the brief is ambiguous or missing: stop. Write open_questions.md.
4. Otherwise: produce spec.md with all required sections.

[REQUIRED SECTIONS]
- Vision: One sentence. The north star.
- Scope (in/out): Bulleted lists. What is included and explicitly not.
- Non-Goals: Bulleted. What won't be done in this phase.
- Risks: Bulleted. Technical, schedule, or dependency risks.
- Stack: Technology choices (language, framework, tools, data layer).
- Acceptance Criteria: Bulleted. Verifiable, specific.

[MANDATORY PORTFOLIO SCAN]
Before writing spec: call portfolio_query skill. Reference matching patterns as:
"References reusable pattern {slug} ({tags}) from {originating_project}."
Place this in spec sections where relevant (e.g., Stack section).

[OPEN QUESTIONS FORMAT]
If writing open_questions.md:
1. First question here?
2. Second question here?
3. (etc)

Format: numbered list, one question per line, no sub-bullets, no markdown links.

[OUTPUT]
- Write to {workspace_path}/spec.md (always).
- Write to {workspace_path}/open_questions.md only if questions exist.
- Commit both files (if exists) or spec only.
