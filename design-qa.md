# Glimpse frontend design QA

## Comparison target

- Original selected visual direction (all 1487 x 1058):
  - `C:\Users\RXiaoen\.codex\generated_images\019fb1f1-c793-71f2-b053-d90e66b86a2d\call_Q7CEv6K7PlbJhKtKyrZeE9xJ.png` — memory wall/search
  - `C:\Users\RXiaoen\.codex\generated_images\019fb1f1-c793-71f2-b053-d90e66b86a2d\call_XPobfRrGTa2Z99BX2LHrtlWa.png` — summary editing
  - `C:\Users\RXiaoen\.codex\generated_images\019fb1f1-c793-71f2-b053-d90e66b86a2d\call_FHZzkFH84uxqVBcZ6gNTUvjv.png` — memory detail
  - `C:\Users\RXiaoen\.codex\generated_images\019fb1f1-c793-71f2-b053-d90e66b86a2d\call_IbMcmVfBP2YlpbgQYSMbGECr.png` — AI settings
  - `C:\Users\RXiaoen\.codex\generated_images\019fb1f1-c793-71f2-b053-d90e66b86a2d\call_qiBJmBaWPE54VISTDznC5Ho2.png` — image preview
- User-reported inspector evidence:
  - `C:\Users\RXiaoen\AppData\Local\Temp\codex-clipboard-e4f2afb8-230a-4262-8e9b-d5c81342313d.png` — gallery, 708 x 1182
  - `C:\Users\RXiaoen\AppData\Local\Temp\codex-clipboard-bc76c51b-4d53-4d1b-9185-52542edb21f5.png` — default summary, 702 x 742
  - `C:\Users\RXiaoen\AppData\Local\Temp\codex-clipboard-311eb6cc-2034-413c-ae4e-c386eba20bd5.png` — editing summary, 716 x 698
  - `C:\Users\RXiaoen\AppData\Local\Temp\codex-clipboard-b7e8d083-fa93-4d2f-9737-aa96fa43a43d.png` — active thumbnail outline clipping, 620 x 172
  - `C:\Users\RXiaoen\AppData\Local\Temp\codex-clipboard-c4beaa12-3775-453f-bc3e-b7cbf846cbc4.png` — editing summary text movement, 702 x 318
  - `C:\Users\RXiaoen\AppData\Local\Temp\codex-clipboard-25358703-92fd-46f2-892f-26b233c1f053.png` — default summary reference, 716 x 300
- Current polish evidence:
  - `C:\Users\RXiaoen\AppData\Local\Temp\codex-clipboard-e361fc2f-67cc-49e2-87f3-724f106fbb4f.png` — uneven search-source inset, 564 x 124.
  - `C:\Users\RXiaoen\AppData\Local\Temp\codex-clipboard-7e50efba-a8db-4cdc-8d98-1e675da84a0f.png` — intrusive search focus treatment, 1668 x 190.
  - `C:\Users\RXiaoen\AppData\Local\Temp\codex-clipboard-d7083fbf-36f8-464a-aa95-bacd1863d0e5.png` — intrusive summary focus treatment and disproportionate actions, 758 x 326.
- Current implementation evidence:
  - `E:\project\Glimpse\Glimpse\.tmp\ui-qa\comparison.png` — combined before/after evidence, 1600 x 1200.
  - `E:\project\Glimpse\Glimpse\.tmp\ui-qa\home-improved-1440.png` and `home-long-summary-edit-1440.png` — full views, 1440 x 900 CSS/pixels at deviceScaleFactor 1.
  - `E:\project\Glimpse\Glimpse\.tmp\ui-qa\segment-improved.png` (276 x 60), `search-focus-improved.png` (814 x 64), and `summary-edit-improved.png` (351 x 334) — focused implementation regions.
  - `E:\project\Glimpse\Glimpse\.tmp\ui-qa\home-1024x720-long-summary-edit.png` and `home-820x560-long-summary-edit.png` — responsive edit-state evidence at deviceScaleFactor 1.
- Final implementation screenshots: `E:\project\Glimpse\Glimpse\.tmp\design-qa\iteration-5\*.png`.
- Full-view source/implementation composites: `E:\project\Glimpse\Glimpse\.tmp\design-qa\iteration-5\comparisons\*.png`.
- Focused before/after inspector composites: `E:\project\Glimpse\Glimpse\.tmp\design-qa\iteration-5\refinement-comparisons\*.png`.
- Full-view viewport and pixels: 1487 x 1058 CSS/pixels at deviceScaleFactor 1; no resampling.
- Focused comparisons: the implementation inspector was cropped from the unscaled browser render, then normalized to each supplied evidence image's pixel dimensions for side-by-side inspection. The unscaled implementation remains the measurement source.
- Responsive evidence: 1440 x 900, 1024 x 720, and 820 x 560 at deviceScaleFactor 1.
- Browser: the user's approved Google Chrome headless instance.

## Findings and comparison history

### Iteration 1

- [P1] The full-width DEV row displaced the wall and debug metrics were always visible.
- [P1] The wide wall used four columns rather than the selected three-column rhythm.
- [P2] Detail/settings duplicated return navigation and main landmarks.
- [P2] Detail preview was visually over-weighted.
- [P2] The 820 px toolbar fragmented into three rows.

### Iteration 2

- Replaced DEV with a compact collapsed popover, restored the three/two/one-column breakpoints, removed duplicate navigation/landmarks, and regrouped the 820 px toolbar.
- One [P2] remained: the detail image filled too much of its panel and lacked the quiet double-click hint.

### Iteration 3

- Limited the detail image to 86% width and 80% height, restored the centered double-click hint, tightened settings form rhythm, and removed redundant query text.
- The original five-state and responsive comparison passed.

### Iteration 4 — user-reported inspector refinement

- [P2] Inspector thumbnails were tall/cropped and the large-preview button consumed unnecessary vertical space.
  - Fix: changed thumbnails to 56 px-high bounded containers with `object-contain`, preserved intrinsic aspect ratios, and removed the button while retaining double-click, Enter/Space, and the application modal.
- [P1] Summary editing changed the component height and pushed the copy/detail and OCR areas downward.
  - Fix: made the compact summary body a stable 80 px region, kept sync status visible, and moved Cancel/Save into the original Edit control slot.
- [P2] Secondary buttons laid SVGs and text on the inline baseline, visibly misaligning Copy summary, View details, maintenance, and related controls.
  - Fix: standardized secondary/primary controls on inline-flex, centered items, consistent gaps and line height, and prevented icons from shrinking across inspector, detail, settings, toolbar, shell, OCR, and toast controls.
- Post-fix browser geometry proves the default and edit states share identical anchors:
  - summary: top 602 px, bottom 766 px, height 164 px in both states;
  - lower summary actions: top 786 px in both states;
  - OCR card: top 851.03125 px in both states;
  - Edit, Cancel, and Save: each 112 x 40 px.
- No P0, P1, or P2 findings remain.

### Iteration 5 — thumbnail clipping and summary transition polish

- [P2] The selected first thumbnail's outward ring was clipped at the horizontal scroller's left edge.
  - Fix: added 4 px horizontal scroll-container breathing room and changed the selected ring to an inset ring, preserving the full blue outline.
- [P2] Compact summary text visibly shifted when edit mode mounted a differently padded, differently spaced textarea.
  - Fix: default and edit states now reuse the same persistent textarea with identical bounds, padding, font size, and line height. Editability and the absolute background/border surface are the only toggled properties.
  - Focus setup preserves and restores the existing scroll position, including the next animation frame, so moving the caret to the end cannot flash-scroll long summaries.
- Post-fix 16 ms transition sampling proves every observed frame used the same connected DOM node and content with invariant geometry:
  - text origin: x 1128 px, y 654 px;
  - typography: 14 px font size, 28 px line height;
  - summary: top 602 px, bottom 766 px;
  - lower summary actions: top 786 px;
  - OCR card: top 851.03125 px.
- The active thumbnail begins at least 4 px inside the scroll clip and its computed ring is inset. No P0, P1, or P2 findings remain.

### Iteration 6 — spacing, focus containment, and long-summary reading

- [P2] The search-source frame used 4 px padding around nominally 36 px controls, but the global 40 px button minimum overrode those controls and reduced the vertical inset to 1 px.
  - Fix: the three options now use a 44 px frame, an exact 3 px inset, and three equal 36 x 84 px grid cells with a local `min-height: 0` override.
- [P1] Search and summary fields combined component rings, the global outline, and an 8 px negative summary decoration inset. The result extended into neighboring visual space.
  - Fix: form focus is now one border plus a two-pixel inset treatment. The summary frame owns its one-pixel inset focus treatment, has no negative inset, and preserves the same geometry in read and edit states.
- [P1] Compact summaries stayed at 80 px regardless of content length.
  - Fix: the persistent textarea now measures its real wrapped `scrollHeight`, grows from 80 px up to 256 px (or 36% of a short viewport), and only then becomes internally scrollable. Width changes are remeasured through `ResizeObserver`; the observer and viewport listener are removed on unmount.
- [P2] Cancel and Save used 13 px medium text inside 112 x 40 px controls, making the controls look under-filled.
  - Fix: Edit, Cancel, and Save retain the established 112 x 40 px geometry and now share 14 px / 600 / 20 px typography. A container-query fallback wraps the two edit actions only when the summary component is narrower than 320 px.
- Independent review found two accessibility follow-ups before acceptance:
  - Primary controls now receive a two-tone inset keyboard focus ring, so focus remains visible on both white and primary-colored surfaces without consuming outside space.
  - A capped, overflowing read-only summary receives `tabindex="0"`, enabling keyboard scrolling; non-overflowing read-only summaries remain outside the tab order.
- Chrome geometry after the final pass:
  - source switcher: 3 px inset, 44 px frame, three equal 36 x 84 px controls;
  - focused search: primary border and two-pixel inset shadow, no outside outline;
  - long summary: 232 px natural height at 1440 x 900, 204 px cap at 1024 x 720, and 201 px cap at 820 x 560;
  - Cancel and Save: each 112 x 40 px with 14 px / 600 / 20 px typography;
  - no horizontal overflow at 1024 x 720 or 820 x 560;
  - 24/24 Vitest checks, TypeScript/Vite production build, and `git diff --check` pass;
  - no console, runtime, or network errors were recorded in the accepted Chrome run.
- The combined evidence is `E:\project\Glimpse\Glimpse\.tmp\ui-qa\comparison.png`. No actionable P0, P1, or P2 findings remain.

## Required fidelity surfaces

- Fonts and typography: system sans-serif fallback, weights, line heights, card wrapping, summary hierarchy, form labels, and Chinese/English states remain readable without clipping. Button line boxes now share the icon centerline.
- Spacing and layout rhythm: the wide wall remains three columns beside the 380 px inspector. Gallery controls are shorter, the selected thumbnail has unclipped edge breathing room, summary text and surrounding anchors produce 0 px displacement across every sampled transition frame, and the 820 px fallback remains an intentional two-row toolbar.
- Colors and tokens: light surfaces, blue focus/selection, green service status, orange capture action, search-source badges, and dark/system themes remain coherent and accessible.
- Image quality and asset fidelity: real screenshot assets are used throughout. Primary images and inspector thumbnails preserve intrinsic aspect ratio through `object-contain`; no CSS art, handcrafted SVG substitute, or placeholder imagery was introduced.
- Copy and content: visible Chinese and English copy remains coherent. The fixed vector model, local OCR stack, exact/semantic badges, and removal of the redundant large-preview button follow current product decisions.
- Icons and surfaces: Heroicons remain one consistent outline family. Visible icon/text controls in the inspector passed the automated centerline check with zero mismatches.
- States and interactions: search, filters, compact DEV tuning, summary edit/save/cancel, double-click and keyboard preview, modal navigation, settings/maintenance, loading/error/empty states, and unsaved-change confirmation remain implemented.
- Accessibility and responsiveness: one main landmark per route, labels, alt text, visible focus, modal focus trap/restoration, Escape/arrow keys, reduced motion, practical targets, and no horizontal overflow at 1440/1024/820 were verified.

## Interaction and console evidence

- `E:\project\Glimpse\Glimpse\.tmp\design-qa\iteration-5\chrome-report.json` records 36/36 passing checks and no console, runtime, HTTP, or network errors.
- Refinement checks include: no large-preview button; three short, aspect-correct thumbnails; unclipped selected-thumbnail ring; one persistent readonly/editable summary textarea; 16 ms no-movement transition sampling; identical default/edit anchors; two replacement actions matching the original button size; zero inspector icon/text centerline mismatches; double-click and keyboard modal entry; ArrowRight; Escape; and focus restoration.
- Existing regression coverage also passed for result badges/order, three-column wall, fixed vector/OCR display, route landmarks, responsive overflow, light/dark/system themes, and Chinese/English localization.

## Accepted non-blocking differences

- [P3] The modal backdrop remains slightly blurrier than the flatter original mock; it does not affect layout, legibility, or interaction.
- Browser QA omits native Tauri window buttons; this is an expected browser-development difference.
- The fixed vector model, OCR stack card, and search-source badges intentionally supersede stale or omitted fields in the earlier visual mock.

final result: passed
