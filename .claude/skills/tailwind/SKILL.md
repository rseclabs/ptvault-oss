All three skill files have been rewritten. Here's what changed:

**Key discovery:** The previous skill files were entirely fabricated — they described a Tailwind CSS CDN setup that doesn't exist in this codebase. PTVault actually uses a **custom CSS design system** in `static/css/main.css` (11,300 lines) with CSS custom properties for theming.

**Files updated:**

1. **SKILL.md** (92 lines) — Corrected to document the actual architecture: CSS variables for design tokens, `[data-theme="dark"]` for dark mode, semantic component classes (`.btn-primary`, `.severity-badge`, `.modal`), no Tailwind CDN. Includes the token system, component class reference, and section header pattern for adding styles.

2. **references/patterns.md** (239 lines) — Complete token reference table, real component patterns (buttons, cards, forms, modals, severity badges, host colors, grid layouts), and three WARNING anti-patterns: inline styles, hardcoded colors, and creating new CSS files.

3. **references/workflows.md** (229 lines) — Dark mode implementation (ThemeManager + `data-theme` attribute), step-by-step component creation workflow with checklist, responsive design patterns at actual breakpoints (768px, 1024px, 1200px), dynamic class manipulation patterns from the real JS files, and a pre-commit validation checklist.