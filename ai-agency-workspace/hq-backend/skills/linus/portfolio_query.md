[TASK] portfolio_query

[PROCESS]
1. Read {HQ_PORTFOLIO_DIR}/_index.json (fast lookup).
2. For each entry in the index: read {HQ_PORTFOLIO_DIR}/{slug}/manifest.yaml.
3. Match against spec keywords, stack, domain tags.
4. Return ranked list of matches with reasons.

[INDEX FORMAT]
Portfolio root contains _index.json:
{
  "entries": [
    {"slug": "mqtt_trinity_template", "tags": ["pattern:pub_sub", "domain:agent_orchestration"]},
    ...
  ]
}

[MANIFEST FORMAT]
{HQ_PORTFOLIO_DIR}/{slug}/manifest.yaml:
slug: mqtt_trinity_template
summary: MQTT pub/sub pattern for multi-agent orchestration.
tags: [pattern:pub_sub, domain:agent_orchestration, stack:python, stack:mqtt]
language: python
originating_project: theoffice-bootstrap
files:
  - hq_router.py
  - hq_project_manager.py
added_at: "2026-05-25T00:00:00Z"

[OUTPUT]
Stdout (plain text):
- Matching entries {slug}: {summary} ({tags})
  Why relevant: {reason}
  From: {originating_project}
- (next match)

Example:
- mqtt_trinity_template: MQTT pub/sub pattern for multi-agent orchestration. (pattern:pub_sub, domain:agent_orchestration, stack:python)
  Why relevant: Spec mentions MQTT broker for task routing.
  From: theoffice-bootstrap
