# Pineapple — frontend

Angular + Angular Material UI for the Pineapple iOS forensic analysis tool.
Rendered inside a pywebview window (see `../backend`). Zoneless, fully
signal-based; no `window.pywebview` means every service is an idle no-op, so it
also runs in a plain browser.

**Package manager: `pnpm` only. Never use `npm` or `yarn`.**

## Commands

```bash
pnpm install
pnpm start          # ng serve on http://localhost:4200
pnpm run build      # -> dist/pineapple-frontend/browser/
pnpm lint           # eslint (angular-eslint)
pnpm test           # vitest
pnpm exec prettier --check "src/**/*.{ts,html,scss}"
```

## Design system

Dark Material Design 3, a muted yellow as an accent only, self-hosted Roboto.
See [`../UI.md`](../UI.md) for the full rules and the component patterns.
