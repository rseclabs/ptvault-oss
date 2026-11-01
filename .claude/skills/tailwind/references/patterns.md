# CSS Patterns Reference

## Contents
- Design Token Usage
- Component Patterns
- Severity and Badge System
- Layout Patterns
- WARNING: Inline Styles Anti-Pattern
- WARNING: Hardcoded Colors Anti-Pattern
- WARNING: New CSS File Anti-Pattern

## Design Token Usage

Every component MUST use CSS variables, never hardcoded values. This is what makes dark mode work automatically.

```css
/* GOOD - Uses design tokens, dark mode works automatically */
.my-component {
    background: var(--color-bg-primary);
    color: var(--color-text-primary);
    border: 1px solid var(--color-border);
    padding: var(--spacing-lg);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-md);
    transition: all var(--transition-fast);
}
```

### Available Token Categories

| Prefix | Tokens | Example |
|--------|--------|---------|
| `--color-bg-*` | `primary`, `secondary`, `tertiary` | `var(--color-bg-primary)` |
| `--color-text-*` | `primary`, `secondary`, `tertiary` | `var(--color-text-secondary)` |
| `--color-border` | `border`, `border-light` | `var(--color-border)` |
| `--color-primary` | `primary`, `primary-hover`, `primary-light` | `var(--color-primary)` |
| `--color-{severity}` | `critical`, `high`, `medium`, `low` + `-bg` | `var(--color-critical)` |
| `--color-{state}` | `success`, `error`, `warning`, `info` + `-bg` | `var(--color-success-bg)` |
| `--spacing-*` | `xs`(4px), `sm`(8px), `md`(16px), `lg`(24px), `xl`(32px), `2xl`(48px) | `var(--spacing-md)` |
| `--radius-*` | `sm`(4px), `md`(6px), `lg`(8px), `xl`(12px) | `var(--radius-lg)` |
| `--shadow-*` | `sm`, `md`, `lg`, `xl` | `var(--shadow-lg)` |
| `--transition-*` | `fast`(150ms), `base`(200ms), `slow`(300ms) | `var(--transition-base)` |

## Component Patterns

### Buttons

```css
/* Base: .btn — always pair with a variant */
<button class="btn btn-primary">Save</button>
<button class="btn btn-secondary">Cancel</button>
<button class="btn btn-sm btn-primary">Small</button>
<button class="btn btn-block btn-primary">Full Width</button>
<button class="btn btn-error">Delete</button>
```

### Cards

```css
/* From static/css/main.css — engagement card pattern */
.engagement-card {
    background: var(--color-bg-primary);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--spacing-lg);
    transition: all var(--transition-base);
}
.engagement-card:hover {
    box-shadow: var(--shadow-lg);
    transform: translateY(-2px);
}
```

### Forms

```html
<!-- From dashboard.html — standard form pattern -->
<div class="form-group">
    <label>Field Label</label>
    <input type="text" placeholder="Enter value">
</div>
<div class="form-row">  <!-- Two-column row -->
    <div class="form-group">
        <label>Start Date</label>
        <input type="date">
    </div>
    <div class="form-group">
        <label>End Date</label>
        <input type="date">
    </div>
</div>
```

### Modals

```html
<!-- Fixed overlay + centered content -->
<div class="modal" id="myModal">
    <div class="modal-content">
        <div class="modal-header">
            <h3>Title</h3>
            <button class="modal-close">&times;</button>
        </div>
        <div class="modal-body">Content</div>
        <div class="modal-footer">
            <button class="btn btn-secondary">Cancel</button>
            <button class="btn btn-primary">Confirm</button>
        </div>
    </div>
</div>
```

## Severity and Badge System

```html
<!-- Severity badges — used for findings, vulnerabilities -->
<span class="severity-badge critical">Critical</span>
<span class="severity-badge high">High</span>
<span class="severity-badge medium">Medium</span>
<span class="severity-badge low">Low</span>
```

### Host Color Categories

10 colors applied via `data-color` attribute:

```css
/* Applied as left border bar on host-item elements */
.host-color-badge[data-color="red"]    { background: #ef4444; }
.host-color-badge[data-color="orange"] { background: #f97316; }
.host-color-badge[data-color="yellow"] { background: #fbbf24; }
.host-color-badge[data-color="green"]  { background: #10b981; }
.host-color-badge[data-color="blue"]   { background: #3b82f6; }
.host-color-badge[data-color="purple"] { background: #a855f7; }
.host-color-badge[data-color="teal"]   { background: #14b8a6; }
.host-color-badge[data-color="cyan"]   { background: #06b6d4; }
```

## Layout Patterns

### Main Grid (sidebar + content)

```css
/* Two-column layout — collapses on mobile */
.container {
    display: grid;
    grid-template-columns: 280px 1fr;
    gap: var(--spacing-lg);
    padding: var(--spacing-lg);
}
@media (max-width: 768px) {
    .container { grid-template-columns: 1fr; }
}
```

### Auto-fill Card Grid

```css
/* Engagement cards — responsive without breakpoints */
.engagements-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: var(--spacing-lg);
}
```

## WARNING: Inline Styles Anti-Pattern

**The Problem:**

```html
<!-- BAD - Bypasses design system, breaks dark mode -->
<div style="background-color: #f0f0f0; padding: 16px; border-radius: 8px;">
    <span style="color: #666;">This is invisible in dark mode</span>
</div>
```

**Why This Breaks:**
1. **Dark mode fails** — `[data-theme="dark"]` only swaps CSS variables, not inline styles
2. **Inconsistent spacing** — `16px` doesn't match `var(--spacing-lg)` which is `1.5rem` (24px)
3. **Unmaintainable** — Global design changes don't propagate to inline styles

**The Fix:**

```html
<!-- GOOD - Uses existing component classes -->
<div class="engagement-card">
    <span class="text-secondary">Dark mode works automatically</span>
</div>
```

## WARNING: Hardcoded Colors Anti-Pattern

**The Problem:**

```css
/* BAD - Hardcoded hex values */
.my-widget {
    background: #ffffff;
    color: #333333;
    border: 1px solid #e5e7eb;
}
```

**Why This Breaks:**
1. **Dark mode shows white card on dark background** — jarring and unreadable
2. **Design system drift** — when brand colors change, this widget stays stale
3. **No semantic meaning** — `#333333` tells you nothing about hierarchy

**The Fix:**

```css
/* GOOD - CSS variables handle theming automatically */
.my-widget {
    background: var(--color-bg-primary);
    color: var(--color-text-primary);
    border: 1px solid var(--color-border);
}
```

**When You Might Be Tempted:** Severity colors and host indicator colors ARE hardcoded intentionally — they must stay consistent across themes. Use `--color-critical`, `--color-high`, etc. for severity, and `data-color` attributes for host colors.

## WARNING: New CSS File Anti-Pattern

**The Problem:** Creating `static/css/my-feature.css` and adding a new `<link>` tag.

**Why This Breaks:**
1. **Variable scope** — new file may load before `main.css`, causing undefined variable errors
2. **Specificity conflicts** — two files competing for the same selectors
3. **Load order fragility** — browser caching can serve stale versions

**The Fix:** Add a new section to `static/css/main.css` with the standard comment header:

```css
/* ============================================
   MY NEW FEATURE
   ============================================ */
```
