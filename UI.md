# UI design system

The rules the Pineapple frontend is built to. `CLAUDE.md` carries the short
version; this is the full one, with tokens and the component patterns.

## Intent

**Material Design 3, restrained and functional.** Every screen must look
deliberately designed for *this* tool — a forensic instrument. Explicitly
**not** the "generic AI assistant" aesthetic.

**Forbidden**, always:

- centered hero text, marketing-style layouts, decorative hero art
- gradients, glassmorphism / blur panels, neon glow, custom drop shadows
- emoji, purple
- any illustration that isn't clean monochrome line-art of the real object

Depth comes from **Material elevation**, never from custom shadows or glow.

## Colour

A single fixed **light** colour scheme. **No theme switch** — no dark mode, no
system mode, no settings UI for it. This is a deliberate product choice, not a
missing feature.

The theme is configured once in `styles.scss` via `mat.theme(...)`:

- `theme-type: light`
- `primary` and `tertiary`: `mat.$yellow-palette`, but the low-contrast
  light-scheme olive is overridden to a **goldenrod amber** (`--mat-sys-primary:
  #b8860b`, `--mat-sys-primary-container: #ffe1a8`) — a nod to the pineapple,
  used as an **accent only**: the active tab underline, focus rings, the
  primary/filled button. **Never** large amber fills, amber backgrounds, or
  amber gradients. The accent is only ~3:1 on white, so anything using it as
  *text* (e.g. the About links) also carries a non-colour cue such as an
  underline.
- `density: 0`

### Surface tokens

Defined on `html` in `styles.scss`; use these, not raw hex:

| Token | Value | Use |
| --- | --- | --- |
| `--app-bg` | `#ffffff` | window background, inset blocks |
| `--app-surface` | `#f4f4f3` | raised surfaces, table bodies, the tab container |
| `--app-border` | `rgba(0,0,0,0.12)` | hairline dividers and outlines |
| `--app-text` | `rgba(0,0,0,0.87)` | primary text |
| `--app-text-muted` | `rgba(0,0,0,0.6)` | secondary text, metadata, counts |

The background is **pure white**; raised surfaces are a hair of grey plus the
hairline border and Material elevation. For anything the tokens don't cover, use
the Material system tokens (`--mat-sys-*`) — e.g. `--mat-sys-error`,
`--mat-sys-surface-container-high`, `--mat-sys-on-surface-variant`.

## Typography

**Roboto**, self-hosted via `@fontsource/roboto` (weights 400 and 500, latin
subset, loaded in `angular.json`). **No Google Fonts or any CDN link — the app
must work fully offline.**

Body text uses `var(--mat-sys-body-medium)`; headings and labels use the
matching `--mat-sys-*` scale steps (`title-medium`, `title-small`,
`label-small`, …). Don't hard-code `font-size` / `font-weight` except where a
fixed monospace size is unavoidable (the syslog viewport). Monospace stack,
everywhere it's needed:

```
ui-monospace, SFMono-Regular, Menlo, Consolas, monospace
```

(There is no bundled monospace font, so this is a system stack by necessity.)

## Spacing & layout

Material **8 dp grid** (4 dp for tight inline gaps). Panels fill the window;
the active tab panel takes the remaining height (`flex: 1`, `min-height: 0`
down the chain so inner scroll areas work).

## SCSS conventions

- One `.scss` per component, BEM-ish class names scoped by the component
  block (`.analysis__header`, `.table__toolbar`).
- Reach into Angular Material's MDC DOM classes (`.mat-mdc-tab-*`) **only**
  when there is no theme token for what you need, and leave a comment saying
  so. Re-check these on every Material upgrade — they are the fragile part.
- `prettier` formats SCSS; there is no separate SCSS linter.

## Component patterns

These are the reusable shapes already in the app. Match them.

### Brand lockup (`Brand`)

`brand/` — the full product logo (`public/logo.png`: the pineapple mark plus the
"Pineapple" wordmark, a single image) rendered as one `<img>` sized by height.
`size` is `compact` (34 px — the default, in the left column of the app header)
or `large` (52 px — the About tab). Reuse it anywhere the app names itself;
never re-typeset the wordmark. The logo is the product mark, so it keeps its own
colour — it is not subject to the monochrome line-art rule below.

### App header + tabs

`app.html` is a `mat-tab-group` (Device / Analysis / About) whose header row
_is_ the app header: a subtle grey strip (`--app-surface`) with a full-width
hairline underneath, no shadow. The `Brand` lockup sits absolutely in its left
column (width `--app-brand-col`, which the tab-header clears with a matching
`padding-left`); height is `--app-header-height` (both tokens live on `html` in
`styles.scss`).

Traditional tabs, not a segmented control: each tab is a **Material Symbols
Outlined** icon (`phone_iphone` / `manage_search` / `info`) stacked over its
label via an `<ng-template mat-tab-label>`, an amber underline
(`--mat-sys-primary`) marks the active one, and icon + label stay text-coloured
(`--app-text-muted` idle, `--app-text` active) — never amber. Most of it is
`mat.tabs-overrides(...)` tokens; the header background/border and the
label-stacking reach into MDC classes because there's no token for them.

Icons: Material Symbols Outlined is self-hosted (`@fontsource-variable`, wired
in `angular.json`); `MAT_ICON_DEFAULT_OPTIONS` in `app.config.ts` makes every
`<mat-icon>` a Symbols ligature, and `styles.scss` points the fontSet class at
the variable font. Decorative icons carry `aria-hidden="true"` and lean on the
visible text label.

### Nav-rail (Analysis case browser)

A fixed-width (`200px`) left rail of `mat-nav-list` **buttons** (not anchors —
they switch state, not navigate), each showing a section label and, when
known, a right-aligned muted count. `[activated]` marks the current section.

### `ArtifactTable`

The generic table for every artifact list (`analysis/artifact-table.ts`).

- `mat-table` + `mat-paginator` inside an `overflow: auto` scroll box with a
  `--app-border` outline; the table body is `--app-surface`.
- Owns its fetch loop: give it `columns`, a `fetchPage` function, and
  optionally `scope` (bump to refetch), `searchable`, `detailFields` /
  `detailTitle`, and (Files only) `resolvePreview` / `onExtract`.
- Toolbar row (searchable tables only): a projected `[tableFilter]` control
  sits left of a 260 px Search field; both wrap together on a narrow window.
- Cells truncate with an ellipsis (`max-width`); numeric columns right-align.
- A row with `detailFields` is a button (`role`, `tabindex`, Enter / click)
  that opens `RecordDetailDialog`.

### `RecordDetailDialog`

The full record behind one row: every field as a label / value pair (long
values in a scrollable monospace block), each with a **quiet** copy affordance
— a 28 px transparent icon button, not a full Material button, that shows a
check + "Copied" tooltip for 1.5 s. Files rows also get a classified content
preview (image / plist-as-JSON / text / "binary — no preview" / unavailable)
and an "Extract file…" action with inline status.

### Wizard dialogs (`BackupDialog`, `AnalysisDialog`)

A `@switch (step())` state machine: confirm/pick → options/configure → native
path picker → progress → result. `disableClose` while the run is in a
`RUNNING_PHASE` — only the explicit Cancel button stops it. A `phaseLabel()`
pure function maps each backend phase to a human string.

### Illustrations

Clean monochrome **line-art of the real object**. The reference is the iPhone
SVG in `device/phone-outline/phone-outline.html`: `currentColor` strokes, no
fill, no photo, no 3D, no glow. Any new illustration follows that.

**Icons** are the exception: UI affordances use Material Symbols Outlined (see
"App header + tabs"), sized in `px`, coloured by `currentColor`. Icons label
controls; they are not decoration.

## Accessibility

`angular-eslint`'s template-accessibility rules are on in CI. Interactive
elements must be real buttons/links or carry `role` + `tabindex` +
keyboard handlers. Icon-only controls need an `aria-label`.
