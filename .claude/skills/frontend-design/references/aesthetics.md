# Aesthetics Reference

## Contents
- Color System
- Typography
- Visual Identity
- Dark Mode
- Severity and State Colors
- Host Indicator Colors

## Color System

All colors defined as CSS custom properties in `static/css/main.css`. NEVER hardcode hex values.

### Background Hierarchy

| Variable | Light | Dark | Use |
|----------|-------|------|-----|
| `--color-bg-primary` | #ffffff | #1a202c | Cards, modals, main content |
| `--color-bg-secondary` | #f5f7fa | #2d3748 | Page background, table headers |
| `--color-bg-tertiary` | #e8ecf1 | #4a5568 | Hover states, secondary buttons |

### Text Hierarchy

| Variable | Light | Dark | Use |
|----------|-------|------|-----|
| `--color-text-primary` | #1a202c | #f7fafc | Headings, important content |
| `--color-text-secondary` | #4a5568 | #e2e8f0 | Body text, descriptions |
| `--color-text-tertiary` | #718096 | #cbd5e0 | Metadata, timestamps, labels |

### Brand Color

```css
--color-primary: #4f46e5;       /* Indigo — main brand, active tabs, CTAs */
--color-primary-hover: #4338ca; /* Darker indigo on hover */
--color-primary-light: #eef2ff; /* Light: tint background; Dark: #312e81 */
```

### Border Colors

```css
--color-border: #e2e8f0;       /* Light; Dark: #4a5568 */
--color-border-light: #edf2f7; /* Light; Dark: #2d3748 */
```

### WARNING: Hardcoded Colors

**The Problem:**

```css
/* BAD — breaks dark mode, no semantic meaning */
.my-element { background: #ffffff; color: #333333; }
```

**Why This Breaks:**
1. Dark mode users see white boxes on dark backgrounds — unreadable
2. Colors drift from the palette — inconsistent UI
3. No semantic meaning — is #333 primary or secondary text?

**The Fix:**

```css
/* GOOD — theme-aware, semantic */
.my-element {
    background: var(--color-bg-primary);
    color: var(--color-text-primary);
}
```

## Typography

### Font Stack

```css
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto',
             'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans',
             'Droid Sans', 'Helvetica Neue', sans-serif;
```

System font stack — renders native on every OS. NEVER add Google Fonts or external font loading.

### Type Scale

| Element | Size | Weight | Use |
|---------|------|--------|-----|
| Auth page title | 2rem | 700 | Login/setup branding |
| Section header (h2) | 1.5rem | 700 | Toolbar headings |
| Card title (h3) | 1.1rem | 600 | Evidence, engagement titles |
| Body text | 0.9rem | 400 | General content |
| Small text | 0.85rem | 400-500 | Metadata, descriptions |
| Badge text | 0.8rem | 600 | Severity badges, uppercase |
| Tag/chip | 0.75rem | 500 | Tags, tiny labels |
| Table header | 0.8rem | 600 | Uppercase, letter-spacing 0.05em |

### Line Height

Default: `line-height: 1.6` on body — optimized for readability in dense security data.

## Visual Identity

### What Makes PTVault Distinctive

1. **Indigo brand** (#4f46e5) — professional, security-focused, not the generic blue
2. **High-contrast severity badges** — red/orange/yellow/blue with colored backgrounds
3. **Left-border accents** — 4px colored borders on toasts, alerts, messages
4. **Glow dots** — severity stat dots with colored `box-shadow` glow effect
5. **Auth gradient** — `linear-gradient(135deg, #4f46e5, #6366f1)` on login/setup pages
6. **Dark mode default** — pentester preference, stored in `localStorage`

### Shadows

```css
--shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
--shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
--shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
--shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
```

## Dark Mode

### Implementation

Theme set via `data-theme` attribute on `<html>`, managed by `ThemeManager` in `static/js/utils.js`:

```javascript
// ThemeManager.toggleTheme() switches and persists to localStorage
document.documentElement.setAttribute('data-theme', theme);
```

Default theme: **dark**. All `var(--color-*)` values automatically update.

### Dark Mode Custom Overrides

Only add `[data-theme="dark"]` overrides when the variable system is insufficient:

```css
/* Auth page gradient needs explicit dark treatment */
[data-theme="dark"] .auth-page {
    background: linear-gradient(135deg, #312e81 0%, #4338ca 100%);
}
```

### Testing Checklist

1. Toggle theme via moon/sun icon in navbar
2. All text remains readable (no light-on-light or dark-on-dark)
3. Severity colors remain distinguishable
4. Shadows visible but not harsh
5. Form inputs have visible borders

## Severity and State Colors

### Severity (Vulnerability Levels)

| Level | Text | Light BG | Dark BG |
|-------|------|----------|---------|
| Critical | #dc2626 | #fef2f2 | #7f1d1d |
| High | #ea580c | #fff7ed | #7c2d12 |
| Medium | #ca8a04 | #fefce8 | #713f12 |
| Low | #2563eb | #eff6ff | #1e3a8a |

### State (UI Feedback)

| State | Color | Variable |
|-------|-------|----------|
| Success | #10b981 (green) | `--color-success` |
| Error | #ef4444 (red) | `--color-error` |
| Warning | #f59e0b (amber) | `--color-warning` |
| Info | #3b82f6 (blue) | `--color-info` |

## Host Indicator Colors

10 color categories for host classification:

| Color | Hex | Suggested Use |
|-------|-----|---------------|
| white | #ffffff | Default/unclassified |
| red | #ef4444 | Critical priority |
| orange | #f97316 | Compromised |
| yellow | #fbbf24 | Medium priority |
| green | #10b981 | Completed/documented |
| blue | #3b82f6 | Infrastructure |
| purple | #a855f7 | Domain controllers |
| teal | #14b8a6 | Database servers |
| cyan | #06b6d4 | Web servers |
| brown | #92400e | Out of scope |
