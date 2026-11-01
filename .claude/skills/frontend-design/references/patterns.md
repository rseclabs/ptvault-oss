# Design Patterns Reference

## Contents
- Anti-Patterns
- Consistency Patterns
- Accessibility
- Component Composition
- JavaScript Styling Patterns

## Anti-Patterns

### WARNING: Hardcoded Colors

**The Problem:**

```css
/* BAD — breaks dark mode, inconsistent */
.my-card { background: #fff; color: #333; border: 1px solid #eee; }
```

**Why This Breaks:**
1. Dark mode users see unreadable light content on dark backgrounds
2. Colors drift from the palette — two shades of gray that don't match
3. No semantic meaning — is #333 primary or secondary text?

**The Fix:**

```css
.my-card {
    background: var(--color-bg-primary);
    color: var(--color-text-primary);
    border: 1px solid var(--color-border);
}
```

### WARNING: Inline Styles in JavaScript

**The Problem:**

```javascript
// BAD — hardcoded in JS, bypasses theming, impossible to maintain
element.style.color = '#ff0000';
element.style.padding = '20px';
element.style.backgroundColor = 'white';
```

**Why This Breaks:**
1. Inline styles override CSS classes — dark mode variables ignored
2. Can't be inspected or overridden in the stylesheet
3. Scattered styling logic across JS files instead of centralized CSS

**The Fix:**

```javascript
// GOOD — use CSS classes defined in main.css
element.classList.add('error-state');

// GOOD — toggle states via classes
element.classList.toggle('active', isActive);

// ACCEPTABLE — dynamic values only (e.g., user-set colors)
element.style.borderLeftColor = host.color_category;
```

**When You Might Be Tempted:** Setting severity colors dynamically. Instead, use data attributes:

```javascript
// GOOD — data attribute + CSS selector
badge.dataset.severity = 'critical';
```

```css
[data-severity="critical"] { color: var(--color-critical); }
```

### WARNING: Magic Numbers in Spacing

**The Problem:**

```css
/* BAD — arbitrary values */
.element { padding: 12px 18px; margin-bottom: 22px; gap: 7px; }
```

**Why This Breaks:**
1. No relationship to the spacing scale — looks subtly misaligned
2. Impossible to maintain consistency across components
3. Every developer invents their own values

**The Fix:**

```css
.element {
    padding: var(--spacing-md) var(--spacing-lg);
    margin-bottom: var(--spacing-lg);
    gap: var(--spacing-sm);
}
```

### WARNING: Missing Interactive States

**The Problem:**

```css
/* BAD — no feedback, feels broken on click/tab */
.clickable-thing { cursor: pointer; }
```

**The Fix:**

```css
.clickable-thing {
    cursor: pointer;
    transition: all var(--transition-fast);
}
.clickable-thing:hover {
    border-color: var(--color-primary);
    box-shadow: var(--shadow-md);
}
.clickable-thing:focus {
    outline: none;
    box-shadow: 0 0 0 3px var(--color-primary-light);
}
.clickable-thing:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}
```

### WARNING: Using Tailwind Utilities in Production CSS

PTVault loads Tailwind CDN but the design system is **custom CSS with variables**. Mixing utility classes creates inconsistency.

```html
<!-- BAD — mixing systems -->
<div class="evidence-card bg-white p-4 rounded-lg">

<!-- GOOD — use the established class system -->
<div class="evidence-card">
```

## Consistency Patterns

### Severity Color Mapping

ALWAYS use the same variable pairs for severity:

| Level | Text | Background |
|-------|------|------------|
| Critical | `--color-critical` | `--color-critical-bg` |
| High | `--color-high` | `--color-high-bg` |
| Medium | `--color-medium` | `--color-medium-bg` |
| Low | `--color-low` | `--color-low-bg` |

### Border Radius Scale

| Token | Value | Use |
|-------|-------|-----|
| `--radius-sm` | 4px | Badges, tags, small buttons |
| `--radius-md` | 6px | Inputs, standard buttons |
| `--radius-lg` | 8px | Cards, panels, sidebars |
| `--radius-xl` | 12px | Modals, auth card, engagement cards |

### Left-Border Accent Pattern

PTVault's signature visual: 4px colored left border on feedback elements.

```css
.toast.success { border-left: 4px solid var(--color-success); }
.error-message { border-left: 4px solid var(--color-error); }
```

### Icon Sizing (Lucide Icons)

```html
<i data-lucide="shield" class="icon-sm"></i>  <!-- 16px -->
<i data-lucide="shield" class="icon-md"></i>  <!-- 20px -->
<i data-lucide="shield" class="icon-lg"></i>  <!-- 24px -->
```

After adding icons dynamically, call `lucide.createIcons()` to render them.

## Accessibility

### Color Contrast

- Text on backgrounds: minimum 4.5:1 contrast ratio
- Large text (18px+, or 14px bold): minimum 3:1
- Severity badges must remain distinguishable in both themes

### Focus Ring

Three-layer focus ring visible on any background:

```css
.element:focus {
    outline: none;
    box-shadow:
        0 0 0 1px var(--color-bg-primary),  /* gap ring */
        0 0 0 3px var(--color-primary);       /* visible ring */
}
```

### Screen Reader Text

Icon-only buttons MUST have accessible labels:

```html
<button class="btn btn-icon" title="Delete host">
    <span class="sr-only">Delete host</span>
    <i data-lucide="trash-2"></i>
</button>
```

```css
.sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
}
```

## Component Composition

### New Card Checklist

Copy when creating new card components:
- [ ] Background: `var(--color-bg-primary)`
- [ ] Border: `1px solid var(--color-border)`
- [ ] Border radius: `var(--radius-lg)` (or `--radius-xl` for feature cards)
- [ ] Padding: `var(--spacing-lg)`
- [ ] Hover: border-color change to `var(--color-primary)`
- [ ] Hover: shadow elevation `var(--shadow-md)`
- [ ] Transition: `all var(--transition-fast)`
- [ ] Test in dark mode

### New Panel Checklist

Copy for sidebar panels or content areas:
- [ ] Background: `var(--color-bg-primary)`
- [ ] Border radius: `var(--radius-lg)`
- [ ] Padding: `var(--spacing-lg)` or `var(--spacing-xl)`
- [ ] Shadow: `var(--shadow-md)`
- [ ] Sticky positioning if sidebar: `position: sticky; top: 90px;`

### Validation Workflow

1. Make changes to component styles
2. Test in light mode — verify contrast and readability
3. Toggle to dark mode — verify variables switch correctly
4. Check hover states on interactive elements
5. Tab through with keyboard — verify focus rings
6. Resize to 768px — verify responsive collapse
7. Only proceed when all checks pass

## JavaScript Styling Patterns

### Theme Toggle

See the **javascript** skill for `ThemeManager` implementation details.

```javascript
// Toggle theme
ThemeManager.toggleTheme();

// Check current theme
const isDark = ThemeManager.getTheme() === 'dark';
```

### Dynamic Class Application

```javascript
// GOOD — class-based styling
card.className = `evidence-card ${isActive ? 'active' : ''}`;

// GOOD — conditional severity
badge.className = `severity-badge ${finding.criticality}`;

// GOOD — toggle visibility
panel.classList.toggle('hidden', !isVisible);
```

### Creating Styled Elements

See the **javascript** skill for full DOM creation patterns.

```javascript
// GOOD — use established CSS classes
const card = document.createElement('div');
card.className = 'evidence-card';
card.innerHTML = `
    <h3 class="evidence-title">${title}</h3>
    <span class="severity-badge ${severity}">${severity}</span>
`;
```
