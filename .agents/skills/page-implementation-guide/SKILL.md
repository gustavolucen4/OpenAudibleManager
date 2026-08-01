---
name: page-implementation-guide
description: Use when creating or refactoring pages in the bot-promotion admin so new UI follows the internal Design System, Tailwind tokens, loading states, accessibility rules, async data patterns, and connection UX documented in docs/.
---

# Page Implementation Guide

Use this skill before adding or refactoring any admin page.

## Required Reading

Read these project docs before editing UI:
- `docs/DESIGN_SYSTEM.md`
- `docs/PAGE_CREATION_GUIDE.md`
- `docs/COMPONENTS.md`
- `docs/COLORS.md`
- `docs/LOADINGS.md`
- `docs/ERROR_HANDLING.md`

For connection screens, also read:
- `docs/CONNECTIONS_ARCHITECTURE.md`

## Workflow

1. Identify the page purpose and primary user action.
2. Use existing shared components before creating new ones.
3. Use Tailwind tokens/classes already present in `apps/admin/app/styles.css`.
4. Add local loading, empty, error and success states.
5. Prevent duplicate async actions by disabling buttons while pending.
6. Keep technical integration errors in logs and show friendly copy in the UI.
7. Run the relevant frontend build or type check after edits.

## UI Rules

- Do not add large colored borders to indicate status.
- Use neutral surfaces, compact badges, dots, icons and typography for hierarchy.
- Keep operational pages dense and scannable.
- Use marketplace logos through the central registry/component.
- Keep mobile layout single-column and avoid text overlap.
