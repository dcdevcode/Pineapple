# Pineapple — frontend

Angular + Angular Material UI for the Pineapple iOS forensic analysis tool.
Rendered inside a pywebview window (see `../backend`).

**Package manager: `pnpm` only. Never use `npm` or `yarn`.**

## Commands

```bash
pnpm install
pnpm start          # ng serve on http://localhost:4200
pnpm run build      # -> dist/pineapple-frontend/browser/
pnpm test           # vitest
pnpm exec ng generate component <name>
```

## Design system

Dark Material Design 3, red as an accent only, self-hosted Roboto. See the
"UI / design system" section in `../CLAUDE.md` for the full rules.
