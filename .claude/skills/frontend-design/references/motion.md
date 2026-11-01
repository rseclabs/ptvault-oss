# Motion Reference

## Contents
- Transition Variables
- Hover Effects
- Keyframe Animations
- Focus States
- Performance Guidelines

## Transition Variables

Three speeds defined in `static/css/main.css`:

```css
--transition-fast: 150ms ease-in-out;  /* Micro-interactions */
--transition-base: 200ms ease-in-out;  /* Standard transitions */
--transition-slow: 300ms ease-in-out;  /* Complex animations */
```

### When to Use Each

| Speed | Use Case | Example |
|-------|----------|---------|
| `--transition-fast` | Button hover, input focus, badge toggle | `.btn:hover` |
| `--transition-base` | Card hover, color picker, sidebar toggle | `.engagement-card:hover` |
| `--transition-slow` | Modal entrance, panel expand, toast | `.modal` open |

## Hover Effects

### Card Border + Shadow

Most cards use border color change + shadow elevation:

```css
.evidence-card {
    transition: all var(--transition-fast);
}
.evidence-card:hover {
    border-color: var(--color-primary);
    box-shadow: var(--shadow-md);
}
```

### Card Lift (Engagement Cards)

Engagement cards add `translateY` for a physical lift effect:

```css
.engagement-card {
    transition: all var(--transition-base);
    box-shadow: var(--shadow-sm);
}
.engagement-card:hover {
    border-color: var(--color-primary);
    box-shadow: var(--shadow-md);
    transform: translateY(-2px);
}
```

### Button Hover

```css
.btn-primary:hover:not(:disabled) {
    background: var(--color-primary-hover);
    box-shadow: var(--shadow-md);
}
```

Always use `:not(:disabled)` to prevent hover on disabled buttons.

### Scale on Hover (Color Picker)

```css
.color-option {
    transition: all var(--transition-base);
}
.color-option:hover {
    transform: scale(1.15);
    box-shadow: var(--shadow-sm);
}
```

### Reveal on Parent Hover

Delete buttons hidden until parent is hovered:

```css
.btn-delete-engagement {
    opacity: 0;
    transition: all var(--transition-fast);
}
.engagement-item:hover .btn-delete-engagement {
    opacity: 1;
}
```

### Sidebar Toggle Icon Rotation

```css
.sidebar-toggle-icon {
    transition: transform var(--transition-fast);
}
.container.sidebar-collapsed .sidebar-toggle-icon {
    transform: rotate(180deg);
}
```

## Keyframe Animations

### Toast Slide In

```css
@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateX(100%);
    }
    to {
        opacity: 1;
        transform: translateX(0);
    }
}

.toast {
    animation: slideIn 0.3s ease-out;
}
```

### Glow Effect (Severity Stat Dots)

```css
.stat-dot-critical {
    background-color: #ef4444;
    box-shadow: 0 0 4px rgba(239, 68, 68, 0.5);
}
.stat-dot-high {
    background-color: #f97316;
    box-shadow: 0 0 4px rgba(249, 115, 22, 0.5);
}
```

### Port Status Dots

```css
.port-dot.port-open {
    background: #10b981;
    box-shadow: 0 0 4px #10b981;
}
.port-dot.port-filtered {
    background: #f59e0b;
    box-shadow: 0 0 4px #f59e0b;
}
```

### WARNING: Dynamic Elements Without Entry Animation

**The Problem:**

```css
/* BAD — element pops in abruptly */
.new-element { display: block; }
```

**Why This Breaks:**
1. Abrupt appearance is jarring — users miss it or feel the UI is broken
2. No visual continuity — the element seems disconnected from the action that created it

**The Fix:**

```css
/* GOOD — smooth entry */
.new-element {
    animation: slideIn 0.3s ease-out;
}
```

## Focus States

### Focus Ring Pattern

All interactive elements use the indigo focus ring:

```css
input:focus,
select:focus,
textarea:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: 0 0 0 3px var(--color-primary-light);
}
```

### Focus vs Active (Color Picker)

```css
/* Focus — keyboard navigation */
.color-option:focus {
    box-shadow: 0 0 0 3px var(--color-primary);
}

/* Active — currently selected state */
.color-option.active {
    border-color: var(--color-text-primary);
    box-shadow: 0 0 0 1px var(--color-bg-primary),
                0 0 0 3px var(--color-primary);
}
```

## Performance Guidelines

### Animate Only Compositor Properties

Use `transform` and `opacity` for 60fps. NEVER animate layout properties.

| Safe (GPU-accelerated) | Avoid (triggers layout) |
|------------------------|------------------------|
| `transform` | `width`, `height` |
| `opacity` | `margin`, `padding` |
| `box-shadow` | `top`, `left`, `right`, `bottom` |
| `border-color` | `font-size` |

**BAD — triggers layout recalculation:**
```css
.element:hover { margin-left: 10px; height: 100px; }
```

**GOOD — GPU-accelerated:**
```css
.element:hover { transform: translateX(10px); }
```

### Reduce Motion

Respect `prefers-reduced-motion` for accessibility:

```css
@media (prefers-reduced-motion: reduce) {
    * {
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
    }
}
```

### Transition Property Targeting

Prefer specific properties over `all` for complex components:

```css
/* Acceptable for simple elements */
.simple { transition: all var(--transition-fast); }

/* Better for complex elements with many properties */
.complex {
    transition: border-color var(--transition-fast),
                box-shadow var(--transition-fast),
                transform var(--transition-fast);
}
```
