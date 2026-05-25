[LESSON] Epic manager = durable drip gate.

[INPUT] `epic_queue/*.json` root array. Task = router payload + `depends_on`.

[STATE] Store `epic_queue/.state/{epic}.state.json`. Mark dispatch before queue write. Restart no double-dispatch.

[UNLOCK] Read `status_log/*.json`. Dependency clears only when matching `task_id` has `status == "success"`.

[OUTPUT] Write payload minus `depends_on` to `task_queue/task_{task_id}.json`. Router owns MQTT.

[IO] Wrap mkdir/read/glob/write/replace/unlink in `try/except`. Use temp file + replace for JSON writes.
