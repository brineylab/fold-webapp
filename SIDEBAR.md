# Sidebar Refactor Implementation Plan

Replace the current top-nav layout with a persistent, collapsible sidebar inspired by [shadcn/ui sidebar](https://ui.shadcn.com/docs/components/base/sidebar). Pure Django templates + Tailwind + vanilla JS — no React migration needed.

---

## Current State

- **Public app** (`base_public.html`): top navbar with "fold@Scripps" brand, "New Job" / "Console" buttons, user dropdown. Content renders in a centered `max-w-7xl` container.
- **Console app** (`console/base.html`): extends public base, adds a 13rem sticky sidebar card with icon+label nav links and active-state highlighting.
- **Model selection** (`select_model.html`): separate full-page grid of model cards grouped by category.
- **Interactions** (`ui.js`): vanilla JS handling themes, dropdowns, dialogs, alerts — all via `data-*` attributes.
- **Design tokens** (`app.css`): HSL-based CSS variables, `ui-*` component classes, already closely mirrors shadcn conventions.

## Target State

A persistent left sidebar that serves as the primary navigation surface for the entire app (public + console). The sidebar contains:

1. **Header** — app branding ("fold@Scripps")
2. **Primary nav** — Jobs, New Job (or model selector flyout)
3. **Models section** — collapsible category groups listing all registered models as direct submit links
4. **Footer** — user info, theme toggle, account link, logout
5. **Console section** (staff only) — collapsible group with all console nav items

The sidebar collapses to icon-only mode on desktop (persisted via `localStorage`) and becomes an overlay drawer on mobile. A slim top bar remains for the mobile hamburger trigger and optional breadcrumbs.

---

## Phase 1: Sidebar Layout Shell

**Goal:** Create the new base layout template with sidebar + top bar, wired up but without interaction logic. All existing pages continue to work.

### 1.1 New CSS variables and sidebar component styles

**File:** `static_src/app.css`

Add to `:root` / `[data-theme="dark"]`:
```css
--sidebar-width: 16rem;        /* 256px expanded */
--sidebar-width-icon: 3rem;    /* 48px collapsed */
```

Add new component classes in `@layer components`:
```css
/* Sidebar shell */
.ui-sidebar { /* fixed left column, full height, border-right, bg-card */ }
.ui-sidebar-header { /* sticky top section with branding */ }
.ui-sidebar-content { /* flex-1 overflow-y-auto, scrollable nav area */ }
.ui-sidebar-footer { /* sticky bottom section */ }

/* Sidebar nav items */
.ui-sidebar-item { /* flex items-center gap-2.5, rounded-md, px/py, hover states */ }
.ui-sidebar-item-active { /* bg-accent font-medium */ }

/* Sidebar group (collapsible section) */
.ui-sidebar-group { /* wrapper */ }
.ui-sidebar-group-label { /* uppercase text-xs, muted, px matching items */ }
.ui-sidebar-group-content { /* collapsible inner container */ }

/* Sidebar collapsed state */
.ui-sidebar-collapsed .ui-sidebar-item span { /* hidden */ }
.ui-sidebar-collapsed .ui-sidebar-group-label { /* hidden */ }
.ui-sidebar-collapsed .ui-sidebar-group-content { /* hidden for model sub-items */ }
```

### 1.2 New base layout template

**File:** `templates/base_sidebar.html`

Structure (extends nothing — new standalone base):
```
<html>
  <head>  (same as current base_public.html)  </head>
  <body class="bg-background text-foreground text-sm">

    <!-- Skip to content link -->

    <!-- Sidebar -->
    <aside class="ui-sidebar" id="app-sidebar" data-sidebar>
      <div class="ui-sidebar-header">
        <a href="{% url 'job_list' %}">fold@Scripps</a>
        <!-- Collapse toggle button (desktop) -->
      </div>

      <div class="ui-sidebar-content">
        {% block sidebar_nav %}
          {% include "components/sidebar/nav_main.html" %}
          {% include "components/sidebar/nav_models.html" %}
          {% if user.is_staff %}
            {% include "components/sidebar/nav_console.html" %}
          {% endif %}
        {% endblock %}
      </div>

      <div class="ui-sidebar-footer">
        {% include "components/sidebar/footer.html" %}
      </div>
    </aside>

    <!-- Mobile overlay backdrop -->
    <div class="hidden fixed inset-0 z-30 bg-black/50" id="sidebar-backdrop" data-sidebar-backdrop></div>

    <!-- Main area -->
    <div class="transition-all duration-200" id="main-wrapper"
         style="margin-left: var(--sidebar-width);">

      <!-- Top bar (mobile toggle + optional breadcrumb) -->
      <header class="sticky top-0 z-20 flex h-12 items-center gap-2 border-b border-border bg-background px-4 lg:hidden">
        <button data-sidebar-toggle aria-label="Toggle sidebar">
          <!-- hamburger icon -->
        </button>
        <span class="text-sm font-medium">{% block topbar_title %}{% endblock %}</span>
      </header>

      <!-- Flash messages -->
      <div class="px-4 py-4 sm:px-6 lg:px-8" aria-live="polite">
        {% for message in messages %} ... {% endfor %}
      </div>

      <!-- Page content -->
      <main class="px-4 pb-8 sm:px-6 lg:px-8" id="main-content">
        {% block content %}{% endblock %}
      </main>
    </div>

    <script src="{% static 'js/ui.js' %}"></script>
  </body>
</html>
```

Key points:
- Sidebar is `position: fixed`, `top: 0`, `bottom: 0`, `left: 0`, `width: var(--sidebar-width)`, `z-index: 40`.
- Main wrapper uses `margin-left: var(--sidebar-width)` to shift content.
- On mobile (`<lg`), sidebar starts translated off-screen (`-translate-x-full`) and becomes an overlay when toggled.
- The `max-w-7xl` constraint moves to `<main>` or is removed entirely to let content fill the available width (sidebar already constrains horizontal space).

### 1.3 Sidebar partial templates

Create `templates/components/sidebar/` directory with:

**`nav_main.html`** — Primary navigation:
```html
<div class="ui-sidebar-group">
  <div class="ui-sidebar-group-label">Navigation</div>
  <div class="ui-sidebar-group-content">
    <a href="{% url 'job_list' %}" class="ui-sidebar-item {% active %}">
      <!-- list icon --> <span>Jobs</span>
    </a>
    <a href="{% url 'job_submit' %}" class="ui-sidebar-item {% active %}">
      <!-- plus-circle icon --> <span>New Job</span>
    </a>
  </div>
</div>
```

**`nav_models.html`** — Model quick-launch links grouped by category:
```html
<div class="ui-sidebar-group" data-sidebar-collapsible>
  <button class="ui-sidebar-group-label" data-sidebar-collapsible-trigger>
    Models <svg class="chevron">...</svg>
  </button>
  <div class="ui-sidebar-group-content" data-sidebar-collapsible-content>
    {% for category, models in sidebar_model_categories %}
      <div class="px-2 py-1 text-xs text-muted-foreground">{{ category }}</div>
      {% for model in models %}
        <a href="{% url 'job_submit' %}?model={{ model.key }}"
           class="ui-sidebar-item pl-6">
          <span>{{ model.name }}</span>
        </a>
      {% endfor %}
    {% endfor %}
  </div>
</div>
```

**`nav_console.html`** — Staff-only console links (mirrors current `console/base.html` sidebar):
```html
<div class="ui-sidebar-group" data-sidebar-collapsible>
  <button class="ui-sidebar-group-label" data-sidebar-collapsible-trigger>
    Ops Console <svg class="chevron">...</svg>
  </button>
  <div class="ui-sidebar-group-content" data-sidebar-collapsible-content>
    <a href="{% url 'console:dashboard' %}" class="ui-sidebar-item">
      <!-- gauge icon --> <span>Dashboard</span>
    </a>
    <!-- ...remaining console nav items... -->
  </div>
</div>
```

**`footer.html`** — User info + theme + logout:
```html
<div class="flex flex-col gap-1 p-2">
  <a href="{% url 'account' %}" class="ui-sidebar-item">
    <!-- user icon --> <span>{{ user.username }}</span>
  </a>
  <div class="ui-sidebar-item" data-dropdown>
    <!-- palette icon --> <span>Theme</span>
    <!-- dropdown with light/dark/system buttons -->
  </div>
  <form action="{% url 'logout' %}" method="post">
    {% csrf_token %}
    <button class="ui-sidebar-item w-full">
      <!-- logout icon --> <span>Logout</span>
    </button>
  </form>
</div>
```

### 1.4 Context processor for sidebar data

**File:** `jobs/context_processors.py` (new)

```python
from model_types import get_model_types_by_category

def sidebar_context(request):
    if not request.user.is_authenticated:
        return {}
    return {
        "sidebar_model_categories": get_model_types_by_category(),
    }
```

Register in `bioportal/settings.py` → `TEMPLATES[0]['OPTIONS']['context_processors']`.

This makes `sidebar_model_categories` available on every authenticated page without repeating it in every view.

---

## Phase 2: Sidebar Interactions (JS)

**Goal:** Add collapse/expand, mobile drawer, collapsible groups, and keyboard shortcut.

### 2.1 Sidebar toggle and persistence

**File:** `static/js/ui.js` — add a new `// ---- Sidebar management ----` section.

State management:
- `localStorage` key: `fold-webapp-sidebar` → `"expanded"` | `"collapsed"`
- On load, read stored state and apply `.ui-sidebar-collapsed` to `#app-sidebar` + update `#main-wrapper` margin.
- `[data-sidebar-toggle]` buttons toggle the class and persist.

Desktop collapse behavior:
- `.ui-sidebar-collapsed`: sidebar width shrinks to `var(--sidebar-width-icon)`, labels hidden via CSS, tooltips on hover.
- `#main-wrapper` margin adjusts accordingly.
- Smooth `transition-all duration-200`.

Mobile drawer behavior:
- On `<lg` screens, sidebar is off-screen by default (`-translate-x-full`).
- `[data-sidebar-toggle]` adds/removes an `.open` class.
- `#sidebar-backdrop` shown/hidden in sync.
- Click on backdrop closes sidebar.
- `body` scroll locked when open.

### 2.2 Collapsible groups

For `[data-sidebar-collapsible]` containers:
- `[data-sidebar-collapsible-trigger]` toggles a `.collapsed` class on the group.
- `[data-sidebar-collapsible-content]` animates `max-height` from `0` to `scrollHeight` (or uses `grid-template-rows: 0fr → 1fr` trick for smooth animation).
- Chevron icon rotates via `.collapsed .chevron { rotate: -90deg }`.
- Group collapsed state optionally persisted in `localStorage` by group name.

### 2.3 Keyboard shortcut

- `Cmd+B` (Mac) / `Ctrl+B` (other) toggles sidebar collapsed state on desktop.
- Only active when no dialog is open and no input is focused.

### 2.4 Tooltip on collapsed items

When sidebar is collapsed (icon-only mode), hovering a `.ui-sidebar-item` shows a small tooltip with the label text. Implementation:
- CSS-only approach using `::after` pseudo-element with `content: attr(data-tooltip)`.
- Add `data-tooltip="{{ label }}"` to each sidebar item.
- Only visible when `.ui-sidebar-collapsed` is active.

---

## Phase 3: Migrate Public App Pages

**Goal:** Switch all public-facing pages from `base_public.html` to `base_sidebar.html`.

### 3.1 Update template inheritance

| Template | Change |
|---|---|
| `jobs/base.html` | `{% extends "base_sidebar.html" %}` (was `base_public.html`) |
| `jobs/list.html` | No change (inherits via `jobs/base.html`) |
| `jobs/detail.html` | No change |
| `jobs/select_model.html` | May become optional / simplified (see 3.3) |
| `jobs/submit_base.html` | No change |
| `jobs/submit_*.html` | No change |
| `jobs/account.html` | No change |
| `registration/login.html` | Keep on `base_public.html` (no sidebar for unauthenticated) |

### 3.2 Active state highlighting

Add a template tag or convention for marking the active sidebar item. Options:

**Option A — URL-name matching (recommended, matches current console pattern):**

Each sidebar link checks `request.resolver_match.url_name` or `request.resolver_match.namespace`:
```html
{% if request.resolver_match.url_name == 'job_list' %}ui-sidebar-item-active{% endif %}
```

This already works and is consistent with the existing console sidebar pattern.

**Option B — Template block:**

Each page sets `{% block active_nav %}jobs{% endblock %}` and the sidebar checks it. More explicit but adds boilerplate.

Recommendation: Option A. It's already proven in the console sidebar.

### 3.3 Model selection page

With models listed in the sidebar, the standalone `select_model.html` grid page becomes less essential. Two options:

**Option A — Keep as-is:** Sidebar links go directly to `?model=<key>`, but the "New Job" sidebar link still goes to the model selection grid. The grid page remains useful for showing help text and maintenance status.

**Option B — Remove grid page:** "New Job" items in sidebar link directly to submit forms. The `select_model.html` page becomes a fallback for when no model is specified.

Recommendation: **Option A for initial implementation.** Keep `select_model.html` as the landing for "New Job" and as a fallback. Sidebar model links are a shortcut for users who already know which model they want.

### 3.4 Remove duplicate nav from top bar

The current top-bar buttons ("New Job", "Console", user dropdown) become redundant since they're in the sidebar. The top bar on desktop can be removed entirely or reduced to a minimal breadcrumb strip. On mobile it remains as a hamburger trigger.

### 3.5 Content width adjustment

Current pages use `max-w-7xl` centered content. With the sidebar consuming ~256px, the main content area should:
- Remove the `max-w-7xl` wrapper (sidebar already constrains width).
- Or keep a slightly narrower max-width (e.g., `max-w-6xl`) for readability on ultrawide monitors.

---

## Phase 4: Migrate Console Pages

**Goal:** Unify console navigation into the shared sidebar, eliminating the separate console sidebar.

### 4.1 Update console base template

**File:** `console/templates/console/base.html`

Change from:
```html
{% extends "base_console.html" %}
{% block content %}
  <div class="grid grid-cols-1 lg:grid-cols-[13rem_1fr] gap-6">
    <aside>...</aside>
    <div>{% block console_content %}{% endblock %}</div>
  </div>
{% endblock %}
```

To:
```html
{% extends "base_sidebar.html" %}
{% block content %}
  {% block console_content %}{% endblock %}
{% endblock %}
```

The console nav links are already in the sidebar's `nav_console.html` partial (Phase 1.3), so the separate sidebar `<aside>` is removed. Console pages now get the same sidebar as public pages, with the "Ops Console" group expanded/highlighted.

### 4.2 Remove `base_console.html`

Once `console/base.html` extends `base_sidebar.html` directly, the intermediate `base_console.html` template is no longer needed. Delete it.

### 4.3 Console active states

Console nav items use the existing `request.resolver_match.url_name` pattern, which transfers directly to the sidebar partials with no changes.

---

## Phase 5: Polish and Responsive Refinements

**Goal:** Final visual polish, accessibility, and edge cases.

### 5.1 Transitions and animations

- Sidebar expand/collapse: `transition: width 200ms ease, margin-left 200ms ease`.
- Collapsible groups: `transition: grid-template-rows 200ms ease` (CSS grid trick).
- Chevron rotation: `transition: rotate 200ms ease`.
- Mobile drawer: `transition: transform 200ms ease`.
- Respect `prefers-reduced-motion`: all transitions become instant.

### 5.2 Accessibility

- Sidebar landmark: `<aside role="complementary" aria-label="Main navigation">`.
- Toggle button: `aria-expanded`, `aria-controls="app-sidebar"`.
- Collapsible groups: `aria-expanded` on trigger, `aria-hidden` on content.
- Focus management: when mobile drawer opens, focus moves to first sidebar link. On close, focus returns to trigger.
- Keyboard: Tab through sidebar items naturally. Escape closes mobile drawer.
- Skip-to-content link remains and works.

### 5.3 Responsive breakpoints

| Breakpoint | Behavior |
|---|---|
| `< 768px` (mobile) | Sidebar hidden off-screen. Hamburger in top bar. Overlay drawer on toggle. |
| `768px–1023px` (tablet) | Same as mobile, or collapsed icon-only mode. |
| `>= 1024px` (desktop) | Sidebar visible. Expanded or collapsed per user preference. |

### 5.4 Print styles

Hide sidebar and top bar when printing. Content fills full page width.

```css
@media print {
  .ui-sidebar, #sidebar-backdrop, header { display: none !important; }
  #main-wrapper { margin-left: 0 !important; }
}
```

### 5.5 Tailwind config updates

**File:** `tailwind.config.js`

- Add `--sidebar-width` and `--sidebar-width-icon` to the theme if needed for utility usage.
- Ensure content paths cover the new `templates/components/sidebar/*.html` partials (already covered by `./templates/**/*.html` glob).

---

## File Change Summary

### New files
| File | Purpose |
|---|---|
| `templates/base_sidebar.html` | New base layout with sidebar + top bar |
| `templates/components/sidebar/nav_main.html` | Primary nav links (Jobs, New Job) |
| `templates/components/sidebar/nav_models.html` | Model quick-launch by category |
| `templates/components/sidebar/nav_console.html` | Staff-only console nav |
| `templates/components/sidebar/footer.html` | User info, theme, logout |
| `jobs/context_processors.py` | Provides `sidebar_model_categories` to all templates |

### Modified files
| File | Changes |
|---|---|
| `static_src/app.css` | Add sidebar CSS variables and component classes |
| `static/js/ui.js` | Add sidebar toggle, collapse, mobile drawer, keyboard shortcut, collapsible groups |
| `tailwind.config.js` | Minor updates if needed |
| `bioportal/settings.py` | Register context processor |
| `jobs/templates/jobs/base.html` | Change extends to `base_sidebar.html` |
| `console/templates/console/base.html` | Change extends to `base_sidebar.html`, remove inline sidebar grid |
| `templates/base_public.html` | Keep for unauthenticated pages (login). Optionally simplified. |

### Deleted files
| File | Reason |
|---|---|
| `templates/base_console.html` | Superseded by `base_sidebar.html` |

---

## Implementation Order

```
Phase 1  [Layout Shell]
  1.1  CSS variables + sidebar component classes
  1.2  base_sidebar.html template
  1.3  Sidebar partial templates
  1.4  Context processor + settings registration

Phase 2  [Interactions]
  2.1  Sidebar toggle + localStorage persistence
  2.2  Collapsible groups
  2.3  Keyboard shortcut (Cmd/Ctrl+B)
  2.4  Collapsed-mode tooltips

Phase 3  [Public App Migration]
  3.1  Switch jobs/base.html to extend base_sidebar.html
  3.2  Active state highlighting
  3.3  Model selection page adjustments
  3.4  Remove redundant top-bar nav
  3.5  Content width tuning

Phase 4  [Console Migration]
  4.1  Switch console/base.html to extend base_sidebar.html
  4.2  Delete base_console.html
  4.3  Console active states

Phase 5  [Polish]
  5.1  Transitions and animations
  5.2  Accessibility audit
  5.3  Responsive breakpoint tuning
  5.4  Print styles
  5.5  Tailwind config cleanup
```

Each phase is independently deployable. Phase 1+2 can be developed and tested before any existing pages are migrated. Phases 3 and 4 are the "switchover" — they change what users see. Phase 5 is refinement.

---

## What This Does NOT Require

- **No React/Vue/Svelte** — everything is Django templates + Tailwind + vanilla JS.
- **No new npm dependencies** — all interactions are hand-written (< 100 lines of JS).
- **No database changes** — model categories come from the existing in-memory registry.
- **No URL changes** — all existing routes remain identical.
- **No breaking changes to submit forms** — template inheritance chain (`submit_*.html` → `submit_base.html` → `jobs/base.html`) is preserved.
