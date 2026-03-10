# Web UI Redesign Implementation Plan

## Objective

Replace the current Bootstrap-based presentation layer with a native Tailwind-based design system while keeping the application server-rendered in Django. The migration includes the public job-submission experience and the staff console, but the rollout will prioritize public-facing pages first.

This plan is intentionally not a React or `shadcn/ui` migration. The recommended implementation is:

- Tailwind CSS for layout, spacing, typography, and component styling
- Django templates and template partials for UI composition
- A small shared JavaScript layer for theme, dialogs, menus, and disclosures
- A staged migration that decouples the public shell from the console shell

## Why This Approach

The current codebase is template-driven, not component-driven. Bootstrap is embedded in:

- the base shell in `jobs/templates/jobs/base.html`
- the console shell in `console/templates/console/base.html`
- template markup across public and console pages
- Django form widget classes in `jobs/forms/*.py`
- Bootstrap JS interactions such as dropdowns and modals
- the override layer in `static/css/theme.css`

Attempting to keep Bootstrap and "skin it harder" will continue to produce a compromised result. The only reliable way to get the desired look and interaction model is to replace Bootstrap as the UI foundation.

## Scope

In scope:

- Public app shell, navigation, theme toggle, messages, cards, tables, forms, empty states
- Job selection, job list/detail, account, login, all submission forms
- Console shell, dashboard, jobs, users, settings, audit, stats, cleanup
- Tailwind asset pipeline and deployment integration
- Removal of Bootstrap CSS/JS and Bootstrap-specific widget classes

Out of scope:

- Rewriting the app as a SPA or introducing React
- Using the literal `shadcn/ui` React component library
- Redesigning Django admin
- Backend behavior changes unrelated to presentation or UI interaction
- New charting or analytics work beyond restyling current surfaces

## Current State Summary

Based on the current repository:

- 24 HTML templates are in the active UI surface
- the public app has 13 templates under `jobs/templates/jobs/`
- the console has 10 templates under `console/templates/console/`
- the login page is separate under `templates/registration/`
- roughly 900 Bootstrap-oriented class hits appear across templates
- roughly 80 Bootstrap widget class usages appear in Django form definitions
- `console/templates/console/base.html` currently extends `jobs/templates/jobs/base.html`, which blocks a safe incremental migration

## Guiding Decisions

### 1. Keep the app server-rendered

The redesign should preserve Django templates as the rendering model. The UI does not currently justify introducing a client-side application architecture, and doing so would expand scope dramatically.

### 2. Use Tailwind, not Tailwind plus Bootstrap

Bootstrap should not remain in the final stack. During migration, temporary coexistence is acceptable only if it is isolated by phase and removed at the end.

### 3. Use a small shared JS layer, not a frontend framework

Interactions currently handled by Bootstrap JS will move to a small shared script, for example `static/js/ui.js`. This script will cover:

- theme persistence and application
- mobile nav or disclosure toggles
- dropdown and menu behavior
- modal dialog open/close behavior
- submit-button busy states where shared behavior makes sense

### 4. Split the public and console shells immediately

The console cannot continue to inherit from the public base while the public shell is being redesigned. The first structural change must decouple those two shells.

### 5. Centralize form rendering patterns

The submission pages are manually rendered field-by-field, which is good for control but too repetitive for a clean migration. Introduce shared template partials and form widget helpers early so field styling stays consistent.

## Target Architecture

### Asset pipeline

Add a minimal Tailwind build pipeline:

- `package.json`
- `tailwind.config.js`
- `static_src/app.css`
- output built CSS to `static/css/app.css`

Recommended npm scripts:

```bash
npm run build:css
npm run watch:css
```

Recommended Tailwind content targets:

- `jobs/templates/**/*.html`
- `console/templates/**/*.html`
- `templates/**/*.html`
- any Python files that generate class strings if needed

Tailwind build integration:

- local development: run `npm run watch:css` alongside Django
- Docker build: install Node and run `npm run build:css` before `collectstatic`

### Template structure

Introduce a root template split so public and console UIs can evolve independently:

- `templates/base_public.html`
- `templates/base_console.html`

Then update:

- `jobs/templates/jobs/base.html` to extend `templates/base_public.html`
- `console/templates/console/base.html` to extend `templates/base_console.html`

### Shared UI partials

Add shared partials for repetitive markup:

- `templates/components/ui/alert.html`
- `templates/components/ui/badge.html`
- `templates/components/ui/card.html`
- `templates/components/ui/button_link.html`
- `templates/components/ui/empty_state.html`
- `templates/components/ui/table_wrapper.html`
- `templates/components/forms/field.html`
- `templates/components/forms/checkbox.html`
- `templates/components/forms/error_list.html`
- `templates/components/forms/help_text.html`

These do not need to be over-abstracted. The goal is consistency and speed, not a miniature frontend framework.

### Form styling helpers

Refactor Django form styling so Bootstrap classes are not embedded in every form definition:

- add shared widget attribute helpers in `jobs/forms/shared.py`
- update form modules to use Tailwind-compatible classes or shared helper functions
- ensure text inputs, textareas, file inputs, selects, checkboxes, and numeric fields share a single styling contract

## Design System Requirements

Define a consistent Tailwind design language before page migration starts. At minimum, establish:

- color tokens for background, surface, border, text, muted text, accent, success, warning, danger, info
- typography scale for page title, section title, label, helper text, badge text, table headers
- spacing scale for cards, form groups, page sections, table cells
- border radius and shadow rules
- button variants: primary, secondary, outline, danger, warning, ghost
- field states: default, hover, focus, error, disabled
- surface patterns for cards, tables, banners, dialogs, side navigation
- status badges for job state and admin state

The current `static/css/theme.css` may be used as a reference for intent, but it should not be treated as a dependency to preserve.

## Delivery Phases

## Phase 1: Foundation and Shell Decoupling ✅

Estimated effort: 1 to 2 days

Goals:

- [x] establish Tailwind build support
- [x] create independent public and console base templates
- [x] preserve the existing app behavior while enabling phased migration

Files added:

- [x] `package.json`
- [x] `tailwind.config.js`
- [x] `static_src/app.css`
- [x] `static/js/ui.js`
- [x] `templates/base_public.html`
- [x] `templates/base_console.html`

Files updated:

- [x] `Dockerfile` — multi-stage build: Node stage builds CSS, Python stage copies the result
- [x] `jobs/templates/jobs/base.html` — now extends `base_public.html`
- [x] `console/templates/console/base.html` — now extends `base_console.html`
- [x] `CLAUDE.md` — added `npm install`, `npm run build:css`, and `css` process
- [x] `Procfile` — added `css: npm run watch:css`
- [x] `.gitignore` — added `node_modules/`

Implementation notes:

- [x] Keep Bootstrap available only where still needed during transition
- [x] Move theme persistence logic out of Bootstrap assumptions
- [x] Ensure the console can temporarily keep Bootstrap styling while public pages migrate first

Exit criteria:

- [x] Tailwind CSS builds successfully locally
- [x] Docker build includes CSS generation before `collectstatic`
- [x] public pages and console pages no longer depend on each other for shell inheritance

Phase 1 deviations and notes for future phases:

- Tailwind `preflight` is disabled (`corePlugins.preflight: false` in `tailwind.config.js`) to avoid clashing with Bootstrap's base styles during the coexistence period. Re-enable in Phase 9 after Bootstrap is removed.
- Tailwind `darkMode` is configured as `['selector', '[data-bs-theme="dark"]']` so that `dark:` variants work with the existing Bootstrap theme attribute. After Bootstrap removal, switch this to `['selector', '[data-theme="dark"]']` or `'class'` and update the HTML attribute accordingly.
- The Dockerfile uses a multi-stage build (Node stage for CSS, then `COPY --from`) instead of installing Node in the final image. This keeps the production image lean but means template files are copied into the Node stage too — if new template directories are added, the Dockerfile CSS stage needs updating.
- Both `base_public.html` and `base_console.html` include Tailwind CSS. This allows incremental Tailwind adoption in console templates without a later pipeline change.
- A minimal FOUC-prevention inline script remains in both base templates; the full theme interaction logic lives in `static/js/ui.js`.

## Phase 2: Tailwind Design System and Shared Partials ✅

Estimated effort: 1 to 2 days

Goals:

- [x] define the base visual language
- [x] reduce one-off styling decisions before page migration begins

Files added:

- [x] `templates/components/ui/alert.html`
- [x] `templates/components/ui/badge.html`
- [x] `templates/components/ui/card.html`
- [x] `templates/components/ui/button_link.html`
- [x] `templates/components/ui/empty_state.html`
- [x] `templates/components/ui/table_wrapper.html`
- [x] `templates/components/forms/field.html`
- [x] `templates/components/forms/checkbox.html`
- [x] `templates/components/forms/error_list.html`
- [x] `templates/components/forms/help_text.html`

Files updated:

- [x] `tailwind.config.js` — added color tokens, border radius tokens, and safelist for dynamic component variants
- [x] `static_src/app.css` — added `@layer base` with CSS custom property design tokens and `@layer components` with all component classes

Implementation notes:

- [x] Use Tailwind `@layer components` for reusable class groups such as buttons, inputs, cards, alerts, badges, and table wrappers
- [x] Keep utility classes in page templates where layout is page-specific
- [x] Keep shared component class names short and obvious, for example `ui-btn-primary`, `ui-input`, `ui-card`, `ui-alert-warning`

Exit criteria:

- [x] all basic component primitives exist in one place
- [x] form fields and cards can be rendered without Bootstrap classes
- [x] theme tokens support both light and dark modes

Phase 2 deviations and notes for future phases:

- Design tokens use `--ui-*` CSS custom properties with space-separated HSL channels (e.g. `--ui-primary: 240 5.9% 10%`). This format is required for Tailwind's `<alpha-value>` opacity modifier support (e.g. `bg-primary/90`). The existing `--bs-*` variables in `theme.css` remain for Bootstrap coexistence.
- Tailwind v3 tree-shakes `@layer components` classes based on content scanning. Since template partials use dynamic class names like `ui-alert-{{ variant }}`, a `safelist` was added to `tailwind.config.js` to ensure all component variants are always included in the build. This safelist can be removed after Phase 9 if all classes are directly referenced in templates.
- Button component uses a two-class pattern: `class="ui-btn ui-btn-primary"` (base + variant), following the same convention as Bootstrap's `btn btn-primary`. The `ui-btn-sm` modifier is additive.
- The `ui-spinner` class provides a pure-CSS loading spinner for submit busy states, replacing Bootstrap's `spinner-border`. It uses Tailwind's `animate-spin` utility.
- Template partials for `card.html` and `table_wrapper.html` are limited in usefulness because Django `{% include %}` cannot wrap arbitrary block content. For complex cards and tables, use the `ui-card` / `ui-table` classes directly in templates. The partials serve as reference patterns.
- `static/js/ui.js` was not modified in this phase — no new interaction primitives were needed for the component definitions. Future phases (particularly Phase 8 for modal behavior) will extend `ui.js`.

## Phase 3: Form Styling Layer

Estimated effort: 1 day

Goals:

- remove Bootstrap widget classes from Django forms
- make all form fields render correctly under Tailwind

Files to update:

- `jobs/forms/shared.py`
- `jobs/forms/boltz.py`
- `jobs/forms/chai.py`
- `jobs/forms/bindcraft.py`
- `jobs/forms/mpnn.py`
- `jobs/forms/rfdiffusion.py`

Implementation notes:

- Add helper functions that attach the correct classes by field type
- Normalize file input styling early, since submission pages rely heavily on uploads
- Include checkbox/radio styling, not only text inputs and selects

Exit criteria:

- no `form-control` or `form-select` classes remain in `jobs/forms/`
- rendered forms look correct when placed in Tailwind templates

## Phase 4: Public Shell and Entry Points

Estimated effort: 1 to 2 days

Goals:

- replace the public shell fully
- migrate the highest-visibility low-risk pages first

Files to update:

- `jobs/templates/jobs/base.html`
- `templates/registration/login.html`
- `jobs/templates/jobs/select_model.html`

Implementation notes:

- Rebuild the top navigation, user menu, theme menu, flash messages, skip-link behavior, and main page container in Tailwind
- Preserve all current auth and navigation behavior
- Use this phase to lock the visual direction before applying it to the full app

Exit criteria:

- login looks and behaves correctly
- model selection looks production-ready
- the public shell no longer loads Bootstrap assets

## Phase 5: Public Data Pages

Estimated effort: 1 to 2 days

Goals:

- migrate the common table/card/status patterns on user-facing pages

Files to update:

- `jobs/templates/jobs/list.html`
- `jobs/templates/jobs/detail.html`
- `jobs/templates/jobs/account.html`

Implementation notes:

- Standardize tables and action buttons before the form-heavy phases
- Make status badges and empty states consistent with the new design system
- Ensure mobile behavior is intentional, especially for tables and action rows

Exit criteria:

- public list/detail/account pages are visually complete
- card, table, badge, and empty-state patterns are stable enough for console reuse

## Phase 6: Public Submission Flows

Estimated effort: 3 to 4 days

Goals:

- migrate the full submission experience
- consolidate repeated field markup where possible

Files to update first:

- `jobs/templates/jobs/submit_base.html`
- `jobs/templates/jobs/submit_boltz2.html`
- `jobs/templates/jobs/submit_chai1.html`
- `jobs/templates/jobs/submit_protein_mpnn.html`
- `jobs/templates/jobs/submit_ligand_mpnn.html`

Files to update next:

- `jobs/templates/jobs/submit_bindcraft.html`
- `jobs/templates/jobs/submit_boltzgen.html`
- `jobs/templates/jobs/submit_rfdiffusion3.html`

Implementation notes:

- Migrate simple forms first to validate field styling
- Convert the complex conditional forms only after the base field components are proven
- Replace Bootstrap submit spinners with Tailwind-compatible busy states
- Preserve all existing conditional logic and input validation behavior

Exit criteria:

- all public submission flows are functional and visually consistent
- no public page depends on Bootstrap CSS or Bootstrap JS

## Phase 7: Console Shell and Console Summary/List Pages

Estimated effort: 2 to 3 days

Goals:

- apply the established design system to the console shell
- migrate the mostly table- and card-based admin pages first

Files to update:

- `console/templates/console/base.html`
- `console/templates/console/dashboard.html`
- `console/templates/console/jobs/list.html`
- `console/templates/console/users/list.html`
- `console/templates/console/stats.html`
- `console/templates/console/audit.html`
- `console/templates/console/cleanup.html`

Implementation notes:

- Rebuild the console sidebar and page framing in Tailwind
- Reuse public card, badge, table, and filter patterns where appropriate
- Keep the console visually related to the public app, but denser and more operational

Exit criteria:

- the console shell is independent and fully Tailwind-based
- all console list and summary pages are migrated without Bootstrap

## Phase 8: Console Detail Pages and Modal Work

Estimated effort: 2 to 3 days

Goals:

- finish the modal-heavy and detail-heavy console screens
- replace all remaining Bootstrap-driven interactions

Files to update:

- `console/templates/console/settings.html`
- `console/templates/console/users/detail.html`
- `console/templates/console/jobs/detail.html`
- `static/js/ui.js`

Implementation notes:

- Centralize dialog behavior in the shared JS layer
- Avoid page-specific modal implementations unless the content truly differs
- Review keyboard behavior, focus management, and escape-to-close behavior carefully

Exit criteria:

- all `data-bs-*` attributes are gone from app templates
- console dialogs and menus are accessible and consistent

## Phase 9: Bootstrap Removal, Cleanup, and QA

Estimated effort: 1 to 2 days

Goals:

- remove transitional dependencies
- verify the full UI surface end to end

Files to update or remove:

- remove Bootstrap includes from `jobs/templates/jobs/base.html` and any remaining templates
- remove or archive `static/css/theme.css`
- remove Bootstrap-specific comments, helper code, and widget classes

Repository-wide checks:

```bash
rg -n "bootstrap|data-bs-|form-control|form-select|btn-|card|alert-|list-group" jobs/templates console/templates templates jobs/forms
```

Exit criteria:

- no Bootstrap assets or Bootstrap-specific classes remain in the application UI
- the new Tailwind UI is the only active presentation layer

## Page Migration Order

Public-first order:

1. `templates/registration/login.html`
2. `jobs/templates/jobs/select_model.html`
3. `jobs/templates/jobs/list.html`
4. `jobs/templates/jobs/detail.html`
5. `jobs/templates/jobs/account.html`
6. `jobs/templates/jobs/submit_base.html`
7. `jobs/templates/jobs/submit_boltz2.html`
8. `jobs/templates/jobs/submit_chai1.html`
9. `jobs/templates/jobs/submit_protein_mpnn.html`
10. `jobs/templates/jobs/submit_ligand_mpnn.html`
11. `jobs/templates/jobs/submit_bindcraft.html`
12. `jobs/templates/jobs/submit_boltzgen.html`
13. `jobs/templates/jobs/submit_rfdiffusion3.html`

Console order:

1. `console/templates/console/base.html`
2. `console/templates/console/dashboard.html`
3. `console/templates/console/jobs/list.html`
4. `console/templates/console/users/list.html`
5. `console/templates/console/stats.html`
6. `console/templates/console/audit.html`
7. `console/templates/console/cleanup.html`
8. `console/templates/console/settings.html`
9. `console/templates/console/users/detail.html`
10. `console/templates/console/jobs/detail.html`

## Verification Plan

## Automated checks

Run during every migration phase:

```bash
npm run build:css
python manage.py check
python manage.py test jobs console
```

If the full test suite is too noisy or incomplete, at minimum run:

```bash
python manage.py check
```

## Manual regression matrix

Public pages:

- login page renders and submits correctly
- theme toggle persists across reloads
- flash messages render and dismiss correctly
- new job model selection is responsive and readable
- job list loads, empty state renders, action buttons work
- job detail shows files and actions correctly
- account page renders API keys and actions correctly
- all submission forms render labels, help text, errors, file inputs, disabled states, and submit busy states correctly

Console pages:

- sidebar navigation works and highlights current page
- dashboard summary cards and links work
- jobs and users list filters work
- bulk action bar still works on jobs list
- tables remain readable on smaller screens
- settings dialogs open, close, and submit correctly
- user detail dialogs and action buttons behave correctly
- job detail shows attempts, logs, and actions correctly

Cross-cutting:

- dark and light theme both work
- keyboard tab order is sensible
- focus rings are visible
- dialogs trap focus and restore focus on close
- no page has a broken layout at mobile widths

## Risks and Mitigations

### Risk: public and console remain coupled

Mitigation:

- split the bases in Phase 1 before any page-level redesign begins

### Risk: Tailwind misses dynamic classes during build

Mitigation:

- avoid runtime-generated class names where possible
- use a safelist in `tailwind.config.js` for any truly dynamic variants

### Risk: form consistency drifts across submission pages

Mitigation:

- centralize widget styling in Python helpers
- use shared template partials for repeated field patterns

### Risk: modal accessibility regresses during Bootstrap removal

Mitigation:

- implement one shared dialog pattern in `static/js/ui.js`
- test keyboard behavior on every modal-heavy console page

### Risk: deployment breaks because CSS is no longer prebuilt

Mitigation:

- add Node install and CSS build to `Dockerfile`
- document local and deployment asset-build steps explicitly

### Risk: the public redesign keeps changing mid-implementation

Mitigation:

- lock the visual direction at the end of Phase 4 before migrating all submission forms and the console

## Acceptance Criteria

The redesign is complete when all of the following are true:

- the application UI uses Tailwind as its only styling framework
- the public shell and console shell are independent
- no app template depends on Bootstrap CSS or Bootstrap JS
- no Django form widgets use `form-control` or `form-select`
- dialogs, menus, and theme toggles work without Bootstrap JS
- public submission flows and console operations behave as before
- the UI is responsive, keyboard-accessible, and visually coherent in light and dark modes

## Estimated Effort

Expected implementation time for one engineer:

- minimum: 12 working days
- realistic: 12 to 17 working days
- likely with design iteration and polish: 3 weeks

Suggested cadence:

- Week 1: Phases 1 through 4
- Week 2: Phases 5 through 7
- Week 3: Phases 8 and 9, then polish and regression cleanup

## Recommended First Commit Sequence

To reduce risk, the first few commits should be:

1. Add Tailwind pipeline and deployment build steps
2. Split public and console base templates
3. Add shared UI and form partials
4. Refactor Django widget classes
5. Redesign login and model selection

That sequence creates a stable foundation before any of the larger template migrations begin.
