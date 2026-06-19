# Teacher Play sidebar density

Sidebar (`#play-save-panel` / `.t-play-save-panel`) in [lab/templates/play.html](../../../lab/templates/play.html) requires scroll on a normal laptop. Staff/keyboard rendering is untouched — CSS/HTML only, scoped to the save panel.

Files: [lab/templates/play.html](../../../lab/templates/play.html), [apps/teacher/static/teacher/teacher-play.css](../../../apps/teacher/static/teacher/teacher-play.css)

- [x] Widen sidebar column on desktop: `.t-play-stage` grid-template-columns second track `minmax(240px,300px)` → `minmax(280px,360px)` at `≥1280px` (new media query or adjust base + narrow at 1020px breakpoint as today)
- [x] `.t-play-save-panel .play-save-grid`: `grid-template-columns: minmax(0,1fr)` → `repeat(2, minmax(0,1fr))`; keep `.play-save-field-wide` spanning both columns (`grid-column: 1 / -1`)
- [x] Reorder/pair fields in play.html so 2-col grid reads naturally: Unit tags + Interaction Modes as a pair, Additional tags + Target playlist as a pair; Description stays `play-save-field-wide`
- [x] `.t-play-checkboxes-group` (Interaction Modes): `flex-direction: column` → `flex-direction: row; flex-wrap: wrap` (pill-style)
- [x] Wrap Key set, Create transpositions, Make public, Save as official rows in a `<details class="play-save-advanced">` / `<summary>Advanced options</summary>` block, collapsed by default (no `open` attr)
- [x] Tighten spacing: panel padding 18px→14px, `.play-save-grid` gap 12px→8px, `#play-save-unit` `size="5"`→`4`
- [x] `.play-save-actions` (Save button): add `position: sticky; bottom: 0; background: var(--surface-2); padding-top: 8px;` so it stays visible without scrolling
- [x] Verify `#play-save-musicxml-options` (already conditionally shown) still reads correctly as a wide row inside the 2-col grid
- [x] Re-check `@media (max-width: 1020px)` / `(max-width: 720px)` stacking still works — single-column phone/tablet view should probably keep 1-col grid (override `play-save-grid` back to 1 col in the 1020px query)
- [ ] Manual check in browser at common laptop heights (~800-900px) on `/teacher/play/`: confirm no scroll needed for Description, Unit tags, Interaction Modes, Save button with Advanced collapsed — **not run**, this worktree has no DATABASE_URL configured so `/teacher/play/` can't be loaded with auth here
- [x] Confirm JS that reads/toggles these fields (`play-save-*` ids, `play-save-mode-*-lbl` ids) is unaffected — only layout/CSS changes, no id/structure removal. Found and fixed a real bug: `#play-save-official-row` now lives inside collapsed `<details>`, so jQuery `:visible` checks on it (`music_controls.js:1139,1308,1438,1792`) would silently break superuser "save as official" gating. Replaced with the already-tracked `this._isSuperuser` flag.
