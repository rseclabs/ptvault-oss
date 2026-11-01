# Layouts Reference

## Contents
- Main Layout
- Grid Patterns
- Spacing Scale
- Responsive Breakpoints
- Container Patterns
- Panel Layouts
- Specialized Layouts

## Main Layout

PTVault uses a **two-column grid** with fixed sidebar, collapsing to single column on mobile:

```css
.container {
    display: grid;
    grid-template-columns: 280px 1fr;
    gap: var(--spacing-lg);
    padding: var(--spacing-lg);
}

.container.sidebar-collapsed {
    grid-template-columns: 80px 1fr;
}

@media (max-width: 768px) {
    .container { grid-template-columns: 1fr; }
}
```

## Grid Patterns

### Engagement Cards Grid

Auto-fill responsive grid:

```css
.engagements-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: var(--spacing-lg);
}
```

### Stats Grid (2x2)

```css
.stats-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--spacing-md);
}
```

### Feature Grid (auto-fit)

```css
.placeholder-features {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--spacing-lg);
}
```

### Color Selector (5-column)

```css
.color-selector {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: var(--spacing-xs);
}
```

### Two-Column Form

```css
.form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--spacing-md);
}

@media (max-width: 768px) {
    .form-row { grid-template-columns: 1fr; }
}
```

## Spacing Scale

| Token | Value | Use |
|-------|-------|-----|
| `--spacing-xs` | 0.25rem (4px) | Tight gaps, inline spacing, tag padding |
| `--spacing-sm` | 0.5rem (8px) | Button padding (small), icon gaps |
| `--spacing-md` | 1rem (16px) | Standard padding, form inputs, grid gaps |
| `--spacing-lg` | 1.5rem (24px) | Card padding, section spacing |
| `--spacing-xl` | 2rem (32px) | Main content padding, large gaps |
| `--spacing-2xl` | 3rem (48px) | Auth card padding, page-level spacing |

### WARNING: Inconsistent Spacing

**The Problem:**
```css
/* BAD — magic numbers outside the scale */
.component { padding: 12px 18px; margin-bottom: 22px; }
```

**Why This Breaks:**
1. No relationship to the spacing scale — looks misaligned with adjacent elements
2. Impossible to maintain consistency across 11K lines of CSS
3. Changing the scale later requires hunting every hardcoded value

**The Fix:**
```css
.component {
    padding: var(--spacing-md) var(--spacing-lg);
    margin-bottom: var(--spacing-lg);
}
```

## Responsive Breakpoints

PTVault uses a **desktop-first** approach with a primary breakpoint at 768px:

| Breakpoint | Width | Behavior |
|------------|-------|----------|
| Desktop | > 768px | Two-column grid, horizontal nav tabs |
| Mobile | <= 768px | Single column, bottom nav, stacked forms |

### Mobile Adaptations

```css
@media (max-width: 768px) {
    .container { grid-template-columns: 1fr; }
    .form-row { grid-template-columns: 1fr; }

    /* Bottom navigation */
    .nav-tabs {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        border-radius: 0;
        z-index: 100;
        box-shadow: var(--shadow-lg);
    }

    .nav-tab {
        flex-direction: column;
        padding: var(--spacing-sm) var(--spacing-md);
        gap: var(--spacing-xs);
    }

    .nav-tab-label { font-size: 0.75rem; }
}
```

## Container Patterns

### Sidebar

```css
.sidebar {
    background: var(--color-bg-primary);
    border-radius: var(--radius-lg);
    padding: var(--spacing-lg);
    box-shadow: var(--shadow-md);
    height: fit-content;
    position: sticky;
    top: 90px; /* Below navbar */
}
```

### Main Content

```css
.main-content {
    background: var(--color-bg-primary);
    border-radius: var(--radius-lg);
    padding: var(--spacing-xl);
    box-shadow: var(--shadow-md);
}
```

### Navbar

```css
.navbar {
    background: var(--color-bg-primary);
    border-bottom: 1px solid var(--color-border);
    padding: var(--spacing-md) var(--spacing-lg);
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 100;
}
```

## Panel Layouts

### Section Toolbar (split left/right)

```css
.section-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--spacing-lg);
    flex-wrap: wrap;
    gap: var(--spacing-md);
}
.toolbar-left { display: flex; align-items: center; gap: var(--spacing-md); }
.toolbar-right { display: flex; gap: var(--spacing-sm); }
```

### Flex List (vertical stack)

```css
.evidence-list {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
}
```

## Specialized Layouts

### Auth Page (centered card on gradient)

```css
.auth-page {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: var(--spacing-lg);
    background: linear-gradient(135deg, var(--color-primary) 0%, #6366f1 100%);
}
.auth-card {
    background: var(--color-bg-primary);
    border-radius: var(--radius-xl);
    padding: var(--spacing-2xl);
    box-shadow: var(--shadow-xl);
}
```

### Port Grid (sticky headers)

```css
.port-grid-table {
    border-collapse: collapse;
    font-size: 0.75rem;
    width: max-content;
}
.port-grid-table .host-column {
    position: sticky;
    left: 0;
    z-index: 20;
    background: var(--color-bg-primary);
    box-shadow: 2px 0 4px rgba(0, 0, 0, 0.1);
}
```

### License Warning Banner

```css
.license-warning-banner {
    background: var(--color-warning-bg);
    border-left: 4px solid var(--color-warning);
    padding: var(--spacing-md);
    display: flex;
    align-items: center;
    justify-content: space-between;
}
```
