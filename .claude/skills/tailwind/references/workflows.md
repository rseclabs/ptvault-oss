# CSS Workflows Reference

## Contents
- Dark Mode Implementation
- Adding a New UI Component
- Responsive Design
- Dynamic Class Manipulation
- Validation Checklist

## Dark Mode Implementation

PTVault uses `data-theme="dark"` on `<html>`, managed by `ThemeManager` in `static/js/utils.js`. Default is dark (pentesters prefer dark themes).

```javascript
// static/js/utils.js — ThemeManager
const ThemeManager = {
    getTheme() {
        return localStorage.getItem('theme') || 'dark';
    },
    setTheme(theme) {
        localStorage.setItem('theme', theme);
        document.documentElement.setAttribute('data-theme', theme);
    },
    toggleTheme() {
        const current = this.getTheme();
        this.setTheme(current === 'dark' ? 'light' : 'dark');
    }
};
```

**How it works:** The `[data-theme="dark"]` selector in `static/css/main.css` overrides all `--color-*` variables. Components using `var(--color-bg-primary)` automatically switch between `#ffffff` (light) and `#1a202c` (dark).

**NEVER** check dark mode in component CSS. If your component uses CSS variables correctly, dark mode is free.

```css
/* BAD - Manually handling dark mode per component */
.my-card { background: #fff; }
[data-theme="dark"] .my-card { background: #1a202c; }

/* GOOD - Automatic via variables */
.my-card { background: var(--color-bg-primary); }
```

## Adding a New UI Component

### Workflow Checklist

Copy this checklist and track progress:
- [ ] Step 1: Add HTML structure in `templates/dashboard.html`
- [ ] Step 2: Add CSS classes in `static/css/main.css` under a new section header
- [ ] Step 3: Use ONLY CSS variables for colors, spacing, radius, shadows
- [ ] Step 4: Add responsive `@media` rules if layout changes at 768px or 1024px
- [ ] Step 5: Test dark mode by toggling theme — no visual breakage
- [ ] Step 6: Test at 375px width for mobile

### Example: Adding a Stats Widget

**Step 1 — HTML in `dashboard.html`:**

```html
<div class="stats-widget">
    <div class="stats-widget-header">
        <h4>Findings by Severity</h4>
    </div>
    <div class="stats-widget-body">
        <div class="stats-widget-item">
            <span class="severity-badge critical">Critical</span>
            <span class="stats-widget-count">5</span>
        </div>
    </div>
</div>
```

**Step 2 — CSS in `static/css/main.css`:**

```css
/* ============================================
   STATS WIDGET
   ============================================ */
.stats-widget {
    background: var(--color-bg-primary);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    overflow: hidden;
}

.stats-widget-header {
    padding: var(--spacing-md) var(--spacing-lg);
    border-bottom: 1px solid var(--color-border);
}

.stats-widget-header h4 {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--color-text-primary);
}

.stats-widget-body {
    padding: var(--spacing-lg);
}

.stats-widget-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-sm) 0;
}

.stats-widget-count {
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--color-text-primary);
}
```

### Validation Loop

1. Add the component
2. Toggle dark mode in browser — verify no broken colors
3. If broken, find hardcoded values and replace with CSS variables
4. Repeat step 2 until clean in both themes

## Responsive Design

### Breakpoints Used

| Width | Target | Usage Count |
|-------|--------|-------------|
| 768px | Tablet / Mobile | Most common (11 occurrences) |
| 1024px | Desktop | Secondary (4 occurrences) |
| 1200px | Large desktop | Rare (1 occurrence) |

### Pattern: Collapsing Grid

```css
/* Desktop: sidebar + content. Mobile: stacked */
.evidence-container {
    display: grid;
    grid-template-columns: 280px 1fr;
    gap: var(--spacing-lg);
}

@media (max-width: 768px) {
    .evidence-container {
        grid-template-columns: 1fr;
    }
}
```

### Pattern: Hiding Non-Essential Elements

```css
/* Hide sidebar labels on small screens */
@media (max-width: 768px) {
    .nav-tab-label { display: none; }
    .sidebar { position: static; }
}
```

### Responsive Test Loop

1. Open DevTools responsive mode
2. Test at 375px, 768px, 1024px, 1440px
3. If layout breaks at a breakpoint, add `@media` rule
4. Repeat step 2 until all sizes work

## Dynamic Class Manipulation

See the **javascript** skill for full SPA patterns. Key CSS-relevant patterns:

### Toggle Active State

```javascript
// static/js/app.js — tab switching
document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.section === sectionId);
});
```

The `.active` class must be defined in CSS:

```css
.nav-tab.active {
    background: var(--color-primary);
    color: white;
}
```

### Dynamic Severity Classes

```javascript
// static/js/hosts.js — dynamic badge rendering
const badge = document.createElement('span');
badge.className = `severity-badge ${severity.toLowerCase()}`;
badge.textContent = severity;
```

Requires matching CSS classes: `.severity-badge.critical`, `.severity-badge.high`, etc.

### Drag-and-Drop Visual Feedback

```javascript
// static/js/reporting.js — drag states
element.addEventListener('dragstart', () => element.classList.add('dragging'));
element.addEventListener('dragend', () => element.classList.remove('dragging'));
target.addEventListener('dragover', () => target.classList.add('drag-over'));
target.addEventListener('dragleave', () => target.classList.remove('drag-over'));
```

```css
.dragging { opacity: 0.5; }
.drag-over { border: 2px dashed var(--color-primary); }
```

## Validation Checklist

Before committing UI changes to `static/css/main.css`:

- [ ] All colors use `var(--color-*)` — no hardcoded hex (except host color badges)
- [ ] All spacing uses `var(--spacing-*)` — no raw `px` or `rem` values
- [ ] All border-radius uses `var(--radius-*)` — no raw values
- [ ] All shadows use `var(--shadow-*)` — no raw box-shadow
- [ ] All transitions use `var(--transition-*)` — no raw `ms` values
- [ ] Component works in both light and dark modes
- [ ] Layout doesn't break at 768px mobile width
- [ ] New section has `/* ==== SECTION NAME ==== */` comment header
- [ ] No inline styles added to HTML
- [ ] Interactive elements have `:hover` and `:focus` states
