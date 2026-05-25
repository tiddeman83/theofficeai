[TASK] wireframe

[PROCESS]
1. Read spec.md and any CEO answers (ceo_answers.md).
2. Identify primary user flow screens (milestones, not every micro-state).
3. For each screen: create a low-fidelity wireframe (ASCII box or SVG).
4. Annotate every interactive element with the event it fires.

[WIREFRAME FORMAT]
ASCII box diagram (Markdown):
```
┌─────────────────────────────────────┐
│ Header                              │
├─────────────────────────────────────┤
│ Sidebar                │ Main Area  │
│ - Link (click→nav)    │ - Button   │
│                       │   (click→  │
│                       │    submit) │
│                       │ - Input    │
│                       │   (change→ │
│                       │    update) │
└─────────────────────────────────────┘
```

OR SVG markup in markdown code block.

[ANNOTATIONS]
Every interactive element gets a comment with the event:
- `(click→<action>)` — mouse click triggers action
- `(submit→<action>)` — form submission
- `(change→<action>)` — input/select change
- `(hover→<state>)` — hover effect
- `(focus→<state>)` — focus state

[SCREEN NAMING]
One file per primary screen. Naming: kebab-case, descriptive.
Examples: `login_form.md`, `dashboard_home.md`, `settings_modal.md`.

[OUTPUT]
- Write to {workspace_path}/wireframes/{screen_name}.md for each screen.
- No JSX, CSS, or component code. Zero implementation.
- Commit all wireframe files as a single commit: "wireframes: {screen_list}".
