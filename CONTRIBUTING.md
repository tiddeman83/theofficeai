# Contributing to The Office AI

Thanks for taking a look. This is a small public project; contributions are welcome and easy to get wrong, so please skim this whole file before opening an issue or PR.

The Office AI is unusual in that a meaningful slice of its commits are written by AI agents acting as personas (Linus, Ada, Pixel, Kent, Grace, SteveJobs). Human and agent contributions follow the same rules below — the only thing that differs is the byline and whether you have to apologise for typos.

---

## Table of contents

- [Code of Conduct](#code-of-conduct)
- [Ways to contribute](#ways-to-contribute)
- [Filing an issue](#filing-an-issue)
- [Development setup](#development-setup)
- [Branch & commit conventions](#branch--commit-conventions)
- [Pull request checklist](#pull-request-checklist)
- [Style rules (the non-negotiable bits)](#style-rules-the-non-negotiable-bits)
- [Persona-authored changes](#persona-authored-changes)
- [Security disclosures](#security-disclosures)

---

## Code of Conduct

Be civil. Disagree with the idea, never the person. Bad-faith behaviour, harassment, or persistent unconstructive negativity is grounds for a permanent block.

Caveman applies to agent-to-agent traffic. It does **not** apply to human-to-human discussion in issues or PRs — be terse if you like, but be kind.

---

## Ways to contribute

- **Bug reports** with a clear reproducer (broker config, branch ID, payload JSON, observed log lines).
- **Pull requests** for bugs, missing safety checks, docs, or new personas.
- **New skills** — Caveman-compressed lesson markdown dropped into `ai-agency-workspace/hq-backend/skills/global/`. The Librarian is happy to grow.
- **New personas** — see [Adding a persona](#adding-a-persona) below.
- **Real-world reports** from running the daemon on something other than macOS / Ubuntu; cross-platform edge cases are gold.

If you want to propose a substantial change (a new component, a wire-format change, an architectural pivot), please open an issue first. A 30-minute discussion saves a lot of rebase.

---

## Filing an issue

Open an issue at https://github.com/tiddeman83/theofficeai/issues and include:

1. **What you did.** The exact command, the exact JSON payload (redact secrets), the persona/CLI involved.
2. **What you expected.**
3. **What actually happened.** Stdout, stderr, and the MQTT status JSON if you have it.
4. **Environment.** OS, Python version, Node version, paho-mqtt version, CLI versions (`claude --version`, `codex --version`, etc.).

If it is a security issue, **do not file a public issue** — see [Security disclosures](#security-disclosures).

---

## Development setup

The README's [Quick Start](README.md#quick-start) covers the runtime setup. For development on top of that:

```bash
git clone https://github.com/tiddeman83/theofficeai.git
cd theofficeai/ai-agency-workspace
python -m venv .venv && source .venv/bin/activate
pip install -r branch-daemon/requirements.txt -r hq-backend/requirements.txt
```

Frontend:

```bash
cd ai-agency-workspace/hq-frontend
npm install
npm run dev
```

You can develop without a real Linode broker by running Mosquitto locally:

```bash
brew install mosquitto && brew services start mosquitto      # macOS
# or
sudo apt install mosquitto && sudo systemctl start mosquitto # Linux
```

Point `MQTT_BROKER_IP=127.0.0.1` in your `.env` and you're good.

---

## Branch & commit conventions

- One branch per change. Name it `feature/<short-slug>`, `fix/<short-slug>`, or `docs/<short-slug>`. The Branch Daemon auto-uses `feature/task_{id}` for agent-driven work; please don't reuse that prefix manually.
- Conventional commit messages:

  ```
  <type>: <subject>

  <optional body explaining the why, not the what>
  ```

  Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`.

- Keep commits small and self-contained. A green test run per commit is the goal, not always reality.
- **Do not** add `Co-Authored-By` lines for tools (Claude, Codex, ChatGPT, etc.) unless the human contributor has explicitly chosen to. Attribution is the author's call.

---

## Pull request checklist

Before you mark a PR ready for review:

- [ ] The PR description states **what** changed and **why**. Link the issue if there is one.
- [ ] Secrets / `.env` files / personal absolute paths are not committed. Check `git diff` once more.
- [ ] New Python code has type hints where it isn't actively annoying.
- [ ] New JS/TS code passes `npm run lint` in `hq-frontend/`.
- [ ] Any new security check (bouncer pattern, path validator, sandbox root) is covered by a deliberate test or at minimum a documented manual repro.
- [ ] Docs are updated when behaviour changes — at minimum `docs/architecture.md` or `docs/development.md`.
- [ ] You have not broken the contract on `agency/tasks/*` or `agency/status/*` payload shapes. If you have, call it out explicitly; it's a wire-format change and needs sign-off.

---

## Style rules (the non-negotiable bits)

These are the only style rules I will be opinionated about. Everything else is taste.

- **Immutability over mutation.** Especially in Python utility helpers and React reducers. Return new objects.
- **Files stay focused.** ~400 lines is the comfortable target, 800 is the ceiling. If a file is sprawling, split it.
- **No silent failure.** Catch, log, and propagate or convert to a typed error. Never swallow.
- **No hardcoded secrets.** Ever. Even in test fixtures. Use `.env` and `.env.example`.
- **No `rm`, `mv`, `chmod`, `chown`, `kill`, `sudo`, `curl`, `wget`, `ssh`, `npm install`, `pip install`** in any prompt, task payload, or daemon code path. The Bouncer blocks them at runtime; don't try to route around it.

---

## Persona-authored changes

If your PR was largely written by a Branch Office persona (Linus, Ada, Pixel, Kent, Grace) running through the system itself:

1. The PR title should be human-readable and **not** Caveman. A human reviews PRs; speak to them.
2. The PR body should include the originating task ID and the persona, e.g.:

   ```
   Task: studiebuddy-arch-001
   Persona: Ada (Claude Code)
   ```
3. The first review pass is on **you**, the human who routed the task. Don't push agent output straight to `main` without reading it.

### Adding a persona

1. Create a folder under `ai-agency-workspace/hq-backend/personas/<name>/`.
2. Drop in `persona.md` (Caveman mandate), `contract.md` (input/output shape), `bootstrap.md` (first-run greeting), and optionally `codex_invocation.md` if the persona runs under Codex.
3. Register the persona in `hq-backend/hq_router.py` under the `PERSONAS` mapping (`task_type → persona name`).
4. If the persona maps to a CLI not already supported, extend `build_agent_command()` in `branch-daemon/worker_node.py`.
5. Document the persona in [README.md](README.md#the-roster).

---

## Security disclosures

If you find a vulnerability — particularly anything that could:

- bypass the Regex Bouncer,
- escape the per-persona sandbox roots,
- exfiltrate broker credentials or local files,
- execute arbitrary code via a crafted MQTT payload —

please **do not** open a public issue. Email **tijmenbaas83@gmail.com** with the subject line `theofficeai security: <one-line summary>`, a minimal reproducer, and a sensible disclosure timeline. I'll respond within a few working days.

Public credit for the report is on by default once a fix is shipped; tell me if you'd rather stay anonymous.

---

Thanks for being here. Now go ship something weird.
