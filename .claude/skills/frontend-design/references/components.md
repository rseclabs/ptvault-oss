# Components Reference

## Contents
- Buttons
- Badges
- Cards
- Forms
- Modals
- Tables
- Toasts and Alerts
- Navigation Tabs

## Buttons

### Base Button

```css
.btn {
    padding: var(--spacing-md) var(--spacing-lg);
    border: none;
    border-radius: var(--radius-md);
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    transition: all var(--transition-fast);
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-sm);
}
```

### Variants

| Class | Background | Use Case |
|-------|------------|----------|
| `.btn-primary` | `--color-primary` | Save, Create, primary CTA |
| `.btn-secondary` | `--color-bg-tertiary` | Cancel, Close, secondary |
| `.btn-success` | `--color-success` | Confirm positive action |
| `.btn-error` | `--color-error` | Delete, destructive action |
| `.btn-icon` | `--color-primary` | Icon-only (square, `--radius-lg`) |

### Modifiers

```css
.btn-sm { padding: var(--spacing-sm) var(--spacing-md); font-size: 0.85rem; }
.btn-block { width: 100%; justify-content: center; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
```

### WARNING: Buttons Without Hover States

**The Problem:**
```css
/* BAD — no feedback, feels broken */
.btn-custom { background: var(--color-info); }
```

**The Fix:**
```css
.btn-custom { background: var(--color-info); }
.btn-custom:hover:not(:disabled) {
    filter: brightness(0.9);
    box-shadow: var(--shadow-md);
}
```

## Badges

### Severity Badges

```html
<span class="severity-badge critical">Critical</span>
<span class="severity-badge high">High</span>
<span class="severity-badge medium">Medium</span>
<span class="severity-badge low">Low</span>
```

```css
.severity-badge {
    padding: var(--spacing-xs) var(--spacing-md);
    border-radius: var(--radius-md);
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
}
```

### Status Badges

```css
.status-badge {
    font-size: 0.75rem;
    font-weight: 500;
    padding: 0.25rem 0.5rem;
    border-radius: var(--radius-md);
    text-transform: capitalize;
}
.status-active { background: var(--color-success-bg); color: var(--color-success); }
.status-completed { background: var(--color-info-bg); color: var(--color-info); }
```

### Port State Badges

```css
.state-badge.state-open { background: rgba(46, 204, 113, 0.2); color: #27ae60; }
.state-badge.state-filtered { background: rgba(241, 196, 15, 0.2); color: #f39c12; }
```

### Tags

```css
.tag {
    background: var(--color-bg-tertiary);
    color: var(--color-text-secondary);
    padding: var(--spacing-xs) var(--spacing-sm);
    border-radius: var(--radius-sm);
    font-size: 0.75rem;
    font-weight: 500;
}
```

## Cards

### Evidence Card

```css
.evidence-card {
    background: var(--color-bg-primary);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--spacing-lg);
    transition: all var(--transition-fast);
    cursor: pointer;
}
.evidence-card:hover {
    border-color: var(--color-primary);
    box-shadow: var(--shadow-md);
}
```

### Engagement Card (with lift)

```css
.engagement-card {
    background: var(--color-bg-primary);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    padding: var(--spacing-lg);
    transition: all var(--transition-base);
    box-shadow: var(--shadow-sm);
}
.engagement-card:hover {
    border-color: var(--color-primary);
    box-shadow: var(--shadow-md);
    transform: translateY(-2px);
}
.engagement-card.active {
    border-color: var(--color-primary);
    background: var(--color-primary-light);
}
```

### Card HTML Anatomy

```html
<div class="evidence-card">
    <div class="evidence-header">
        <h3>Title</h3>
        <span class="severity-badge critical">Critical</span>
    </div>
    <div class="evidence-content">Content preview...</div>
    <div class="evidence-footer">
        <div class="evidence-tags"><span class="tag">xss</span></div>
        <span class="evidence-meta">2026-01-15</span>
    </div>
</div>
```

## Forms

### Form Group

```css
.form-group {
    margin-bottom: var(--spacing-lg);
}
.form-group label {
    display: block;
    font-weight: 600;
    color: var(--color-text-primary);
    margin-bottom: var(--spacing-sm);
    font-size: 0.9rem;
}
.form-group input,
.form-group select,
.form-group textarea {
    width: 100%;
    padding: var(--spacing-md);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-primary);
    color: var(--color-text-primary);
    font-size: 0.9rem;
    transition: all var(--transition-fast);
}
.form-group input:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: 0 0 0 3px var(--color-primary-light);
}
```

### Two-Column Form Row

```css
.form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--spacing-md);
}
```

## Modals

### Structure

```css
.modal {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.9);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    padding: 20px;
}
.modal-content {
    background: var(--color-bg-primary);
    border-radius: 12px;
    max-width: 600px;
    width: 100%;
    max-height: 90vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}
.modal-header {
    padding: 16px 20px;
    border-bottom: 1px solid var(--color-border);
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.modal-body { padding: 20px; overflow-y: auto; flex: 1; }
.modal-footer {
    padding: 16px 20px;
    border-top: 1px solid var(--color-border);
    background: var(--color-bg-secondary);
    display: flex;
    gap: 10px;
    justify-content: flex-end;
}
```

### Sizes

| Class | Max Width | Use |
|-------|-----------|-----|
| (default) | 600px | Standard dialogs |
| `.modal-lg` | 900px | Complex forms |
| `.modal-xl` | 1200px | Report builder, data views |

## Tables

### Data Table

```css
.data-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.data-table th {
    text-align: left;
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--color-bg-secondary);
    color: var(--color-text-secondary);
    font-weight: 600;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 2px solid var(--color-border);
}
.data-table td {
    padding: var(--spacing-sm) var(--spacing-md);
    border-bottom: 1px solid var(--color-border);
}
.data-table tr:hover { background: var(--color-bg-secondary); }
```

## Toasts and Alerts

### Toast (left-border accent pattern)

```css
.toast {
    background: var(--color-bg-primary);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--spacing-md) var(--spacing-lg);
    box-shadow: var(--shadow-lg);
    min-width: 300px;
    animation: slideIn 0.3s ease-out;
}
.toast.success { border-left: 4px solid var(--color-success); }
.toast.error { border-left: 4px solid var(--color-error); }
.toast.warning { border-left: 4px solid var(--color-warning); }
.toast.info { border-left: 4px solid var(--color-info); }
```

### Alert Messages

```css
.error-message {
    padding: var(--spacing-md);
    border-radius: var(--radius-md);
    background: var(--color-error-bg);
    color: var(--color-error);
    border-left: 4px solid var(--color-error);
}
```

## Navigation Tabs

```css
.nav-tabs {
    display: flex;
    gap: var(--spacing-xs);
    background: var(--color-bg-secondary);
    padding: var(--spacing-xs);
    border-radius: var(--radius-lg);
}
.nav-tab {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    padding: var(--spacing-sm) var(--spacing-lg);
    background: transparent;
    color: var(--color-text-secondary);
    border: none;
    border-radius: var(--radius-md);
    transition: all var(--transition-fast);
}
.nav-tab.active {
    background: var(--color-primary);
    color: white;
    box-shadow: var(--shadow-sm);
}
```
