[TASK] portfolio_contribute

[MANIFEST SCHEMA]
manifest.yaml in {HQ_PORTFOLIO_DIR}/{slug}/:
slug: <unique identifier, kebab-case>
summary: <one-line description of the artifact>
tags: [<tag1>, <tag2>, ...]
language: <primary language: python, typescript, rust, etc>
originating_project: <project_id this came from>
files: [<list of relative paths copied to assets/>]
added_at: <ISO 8601 timestamp>

[TAGGING CONVENTION]
Structured tags for fast portfolio querying:
- pattern:<name>: Architectural pattern (pub_sub, repository, factory, state_machine).
- domain:<area>: Problem domain (agent_orchestration, auth, data_processing, ui).
- stack:<tech>: Technology (python, typescript, react, mqtt, postgres, etc).
- feature:<capability>: Cross-cutting feature (caching, retry, rate_limiting, etc).

Example tags: [pattern:pub_sub, domain:agent_orchestration, stack:python, stack:mqtt]

[INDEX UPDATE]
docs/portfolio/_index.json (root):
{
  "entries": [
    {"slug": "mqtt_trinity_template", "tags": ["pattern:pub_sub", "domain:agent_orchestration"]},
    ...
  ]
}

Add new entry to "entries" array. Keep entries sorted by slug.
Write atomically: temp file → replace.

[PROCESS]
1. Review {project_id} for reusable code, architectures, data models, query patterns.
2. For each artifact: create docs/portfolio/{slug}/ directory.
3. Write manifest.yaml with correct schema.
4. Copy relevant code files to {slug}/assets/. Preserve directory structure relative to project root.
5. Update _index.json by adding entry to "entries" array.
6. Verify YAML and JSON are valid.
7. Commit as: "portfolio: add {slug} from {project_id}".

[FILES LIST]
files field is a list of relative paths within assets/, e.g.:
files:
  - hq_router.py
  - hq_project_manager.py
  - mqtt_client_wrapper.py

[VALIDATION]
- slug must be kebab-case, unique, and not already in portfolio.
- tags must follow the convention (pattern:*, domain:*, stack:*, feature:*).
- language must be a single, recognizable value.
- added_at must be ISO 8601 UTC timestamp.
- files list must exist in assets/ directory.
