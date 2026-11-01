All 6 frontend-design skill files have been generated. Here's a summary of what was created/updated:

### SKILL.md (132 lines)
- Corrected description: removed "Tailwind CSS CDN" reference, now correctly states "CSS custom properties"
- Added comprehensive design token table with all variable prefixes
- Includes engagement card lift effect and toast patterns
- New component checklist for development workflow

### references/aesthetics.md (187 lines)
- Complete color system: background hierarchy, text hierarchy, brand, borders
- Full type scale (8 levels from 2rem auth titles to 0.75rem tags)
- Visual identity section documenting PTVault's distinctive design elements (indigo brand, glow dots, left-border accents, auth gradient)
- Dark mode implementation details with `ThemeManager`
- Severity, state, and host indicator color tables with hex values

### references/components.md (357 lines)
- 8 component categories: buttons, badges, cards, forms, modals, tables, toasts, navigation tabs
- Card variants: evidence card (border hover) vs engagement card (lift effect + active state)
- Full modal structure with header/body/footer and size variants
- Data table with uppercase letter-spaced headers
- Toast left-border accent pattern

### references/layouts.md (280 lines)
- 5 grid patterns: main layout, engagement cards, stats, features, color selector
- Spacing scale with concrete use cases
- Desktop-first responsive approach with mobile bottom nav
- Specialized layouts: auth page gradient, port grid sticky headers

### references/motion.md (260 lines)
- 3 transition speeds with use case guidance
- 6 hover effect patterns: border+shadow, card lift, button, scale, reveal-on-parent, icon rotation
- Glow effects for severity stat dots and port status dots
- Performance guidelines: compositor properties, reduce-motion, transition targeting

### references/patterns.md (299 lines)
- 5 anti-patterns with full problem/why/fix format: hardcoded colors, inline JS styles, magic numbers, missing interactive states, mixing Tailwind utilities
- Consistency patterns: severity mapping, radius scale, left-border accent, icon sizing
- Accessibility: contrast ratios, focus rings, screen reader text
- Component composition checklists and validation workflow
- JavaScript styling patterns with cross-references to the **javascript** skill