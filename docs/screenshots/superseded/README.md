# Superseded screenshots

Chu-Yun's original captures from 2026-09-20, kept for the record. These are
**not** the ones to grade.

All of them were taken before the `templates/base.html` fix. At the time, two
multi-line `{# ... #}` notes in `base.html` were being printed as literal page
text above `<!DOCTYPE html>`, because Django's `{# #}` comment form only works
on a single line. That stray text is visible across the top of every page in
these images.

Nothing else about them was wrong. The pages, the data and the empty-state
message were all correct already, which is why they are worth keeping.

## What is in here, and what replaced it

| Superseded file | Shows | Current version |
|---|---|---|
| `Views-HttpResponse-FBV-pre-comment-fix.jpeg` | `/skills/manual/` | `../section2-view1-fbv-httpresponse.png` |
| `Views-render-FBV-pre-comment-fix.jpeg` | `/skills/` | `../section2-view2-fbv-render.png` |
| `Views-base-CBV-pre-comment-fix.jpeg` | `/plans/cbv-base/` | `../section2-view3-cbv-base-view.png` |
| `Views-generic-CBV-pre-comment-fix.jpeg` | `/tasks/` | `../section2-view4-cbv-generic-listview.png` |
| `template-normal-list-state-pre-comment-fix.jpeg` | `/tasks/` with rows | `../section3-template-normal-list-state.png` |
| `template-empty-state-pre-comment-fix.jpeg` | `/skills/?q=zzzz` | `../section3-template-empty-state.png` |
| `section3-screenshots-pre-comment-fix.pdf` | Both Section 3 states | the two Section 3 PNGs above |

The four `Views-*` files came from the `upload_screenshots` branch, which was
never merged. They are archived here byte for byte so the work is not lost, and
that branch and its pull request were closed rather than merged, to avoid having
two sets of screenshots for the same four views.
