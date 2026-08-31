# AGENTS.md

Orientation for AI coding agents working in this repository. Humans should read
[`README.md`](README.md) first; contributors should also read
[`CLAUDE.md`](CLAUDE.md).

## What this project is

`pineapple` is an **iOS forensic analysis tool** — a desktop application
(Python backend + Angular frontend in one pywebview window) that inspects an
Apple device over USB, captures a full logical image as a `.pineapple` archive,
and parses that image offline into a per-case SQLite database.

Two principles constrain almost every change:

1. **Read-only and non-destructive** toward the device. The only write is
   toggling backup encryption for an encrypted acquisition, always restored
   afterwards.
2. **Never guess.** With more than one device attached, the tool refuses to act.
   More broadly: never choose between real alternatives (a library, a data
   shape, an API surface, a UX behaviour) on your own — ask.

## Documentation map

| File | Read it for |
| --- | --- |
| [`README.md`](README.md) | The public overview: what the tool does, how the analysis works, requirements, setup, the command reference. |
| [`AGENTS.md`](AGENTS.md) | This file — agent orientation and where each doc lives. |
| [`CLAUDE.md`](CLAUDE.md) | The hard rules: English-only repo, incremental scope, ask before choosing alternatives, test every non-trivial function, the tooling and layout tables, per-module notes. |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | The deep "why of everything": process model, the sync bridge over async `pymobiledevice3`, `DeviceSession`, the long-lived-job pattern, backup creation, the analysis pipeline and parsers, the case-folder read model, the frontend architecture. |
| [`UI.md`](UI.md) | The UI design system: Material Design 3 (light-only, goldenrod-amber accent), the surface tokens, and every reusable component pattern. |

## Before you start

- **English only** in everything that lands in the repo — comments, identifiers,
  docstrings, commit messages, and every `.md` file. (Chat with the user happens
  in whatever language they use in the conversation; only what gets committed is
  required to be English.)
- **Backend**: Python `>=3.14`, [`uv`](https://docs.astral.sh/uv/) only.
  **Frontend**: [`pnpm`](https://pnpm.io/) only — never `npm` or `yarn`.
- Work on the **`development`** branch. `main` is the baseline. Commit every
  logical step; push and open PRs only when asked.
- Keep it simple and readable: clear names, small functions, no premature
  abstraction, no cleverness that needs a comment to survive.
- Every new function with non-trivial behaviour ships with its test in the same
  change (backend in `backend/tests/`, frontend in a `*.spec.ts`).
- Do not add scope, features, or "nice to haves" that were not requested.

## Quick commands

```bash
# Backend — must stay green (CI enforces)
cd backend  && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest

# Frontend — must stay green (CI enforces)
cd frontend && pnpm lint && pnpm exec prettier --check "src/**/*.{ts,html,scss}" && pnpm test && pnpm build

# Run the app
cd frontend && pnpm run build && cd ../backend && uv run pineapple-gui
cd backend  && uv run pineapple-gui --dev   # against `pnpm start` on :4200
```
