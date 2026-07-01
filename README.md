# pmo-as-code-pipeline

A **live reference deployment of [PMO as Code](https://c4g-john.github.io/pmo-as-code/)** —
a real repository run entirely with [`docassert`](https://github.com/c4g-john/docassert),
the tool that unit-tests business documents.

This repo is the *example*, not the tool. It holds sample projects as
version-controlled Markdown, gates every change on `docassert`, and publishes a
derived status dashboard.

- **Tool:** [`docassert`](https://github.com/c4g-john/docassert) · `pip install docassert`
- **Live dashboard:** https://c4g-john.github.io/pmo-as-code-pipeline/
- **The standard:** https://c4g-john.github.io/pmo-as-code/

## What's here

```
documents/
  PRJ-001-AUR/   Aurora — full onboarding spine (charter → benefits realization)
  PRJ-002-ATL/   Atlas — partner portal
  PRJ-003-MER/   Meridian
  PRJ-004-PHX/   Phoenix
projects.yaml    generated project registry
STATUS.md        derived status snapshot
examples/        a Word-doc → PMO conversion example (doc-to-pmo)
```

Every project is anchored by a `project.md` (`PRJ-NNN-CODE`); document ids and
traceable items are namespaced by the project code (`AUR-BR-001`). The document
model, kinds, and checks are documented in the
[docassert README](https://github.com/c4g-john/docassert).

## How the gate works

On every pull request, GitHub Actions installs docassert from PyPI and runs it:

- **`audit`** — `docassert validate` on the changed documents (structural checks
  block the merge; AI advisory is informational).
- **`consistency`** — `docassert consistency` across the whole set (referential
  integrity, coverage, required links, profile completeness) plus a
  `projects.yaml` freshness check.
- **`status`** — posts the derived RAG to the PR and flags a stale `STATUS.md`.

`main` is branch-protected: `audit` and `consistency` must pass to merge.

## The dashboard

`.github/workflows/status-pages.yml` runs `docassert pages` on every push to
`main`, publishing a portfolio index plus a page per project to GitHub Pages.

## Run it yourself

```bash
pip install "docassert[ai]"
docassert validate documents/**/*.md
docassert consistency
docassert status --index
```

No config lives in this repo — docassert ships the default criteria, schema, and
profiles. To customize the standard, run `docassert init` to scaffold them, then
edit.

## License

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE). © 2026 C4G Enterprises Inc.
