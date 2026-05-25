[TASK] decompose

[PROCESS]
1. Read spec.md and wireframes/{screen}.md files.
2. Identify the smallest atomic units of work: each task is ≤3 files, ≤120 LOC.
3. Assign task types: frontend, backend, qa, devops (from hq_router).
4. Chain tasks via depends_on so concurrency emerges naturally (no dependency hell).
5. Flag tasks that touch the same file as serial (add explicit depends_on).
6. Output as a valid JSON array for hq_epic_manager.

[TASK OBJECT SCHEMA]
Each task in the array:
{
  "task_id": "unique_id_within_epic",
  "type": "frontend|backend|qa|devops",
  "prompt": "detailed instructions for the assigned persona",
  "workspace_path": "/absolute/path/to/project",
  "depends_on": ["task_id_1", "task_id_2"] or []
}

[RULES]
- task_id: unique within the epic. Pattern: {epic_stage}_{domain}_{ordinal}. Example: poc_auth_1.
- type: one of frontend, backend, qa, devops (router task types).
- prompt: detailed, self-contained. Persona can read it without context.
- workspace_path: must be absolute. Typically {HQ_PROJECTS_DIR}/{project_id}.
- depends_on: list of task_ids that must complete before this task starts. Empty list if no deps.
- Max 3 files touched per task. Max 120 LOC per task. Violations → split into sub-tasks.
- If two tasks touch the same file: add explicit depends_on (force serial).

[CONCURRENCY]
- Tasks with no depends_on can run in parallel.
- Task B with depends_on: ["task_a_1"] cannot start until task_a_1 finishes.
- DAG structure prevents cycles (hq_epic_manager validates).

[OUTPUT]
- Write to {workspace_path}/{stage}_epic.json where stage is "poc" or "mvp".
- Valid JSON array. No trailing commas. One task per line or compact.
- Commit as a single commit with message: "epic: {stage} decomposition for {project_id}".
