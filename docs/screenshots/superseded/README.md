# Superseded screenshots

These are Chu-Yun's original Section 3 screenshots (captured 2026-09-20). They
are kept for the record but are **not** the ones to grade.

They were taken before the `templates/base.html` fix made on the docs-cleanup
branch. At the time, two multi-line `{# ... #}` notes in
`base.html` were being printed as literal page text above `<!DOCTYPE html>`,
because Django's `{# #}` comment form is single-line only. That stray text is
visible at the top of every page in these images.

The current, correct captures are in the parent folder:

| File | Shows |
|---|---|
| `../section3-template-normal-list-state.png` | `/tasks/` with rows |
| `../section3-template-empty-state.png` | `/skills/?q=zzzz`, `{% empty %}` branch |

Nothing else about these images was wrong — the content and the empty-state
message were already right.
