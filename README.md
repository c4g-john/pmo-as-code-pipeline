# docunit — unit testing for business documents

Business documents (charters, decisions, business cases) are usually prose in
Word and PDF: unversioned, unvalidated, and impossible to audit at scale.
`docunit` treats them like code. A document is a structured Markdown file. On
every pull request it is **unit tested** against a configurable audit standard,
and it can't merge until it passes.

Beyond validating a single document, `docunit` also checks **consistency across
documents** — that requirements trace end to end (BRD → PRD → F/NFR →
acceptance criteria → test cases) — and generates the traceability matrix from
those links.

This is the working core of **PMO as Code**.

## Document kinds

Each kind is defined by a trio: `templates/<kind>.template.md`,
`schema/<kind>.schema.json`, and `criteria/<kind>.criteria.yaml`. Adding a kind
is adding a trio — no code change for the common cases. Supported today:

- **Project anchor:** `project` (one `project.md` per project folder)
- **Discovery:** `charter`, `business-case`
- **Requirements:** `brd`, `prd`, `frnfr`, `user-story`, `test-cases`
- **Design & governance:** `adr`, `risk-register`, `raci-stakeholder`
- **Delivery:** `qa-test-plan`, `data-migration-plan`
- **Release & operate:** `release-cutover-plan`, `rollback-plan`,
  `hypercare-plan`, `runbook`
- **Report & close:** `status-report`, `post-implementation-review`,
  `benefits-realization`

## Projects & identity

Every document belongs to a project with a unique, self-identifying id:

- **Project id `PRJ-NNN-CODE`** (e.g. `PRJ-001-AUR`) — a unique sequence *and* a
  short mnemonic `CODE`. Each project is anchored by a `project.md` (kind
  `project`) at the root of its folder.
- **Project-first folders:** `documents/PRJ-001-AUR/charter.md`,
  `documents/PRJ-001-AUR/brd.md`, … — one folder per project, not per kind.
- **Namespaced ids:** document ids are `<CODE>-<slug>` (`AUR-brd`) and item ids
  are `<CODE>-<TYPE>-<NNN>` (`AUR-BR-001`). The code prefix makes every id
  globally unique and self-identifying, so `AUR-BR-001` and `ATL-BR-001` are
  distinct requirements in different projects.

`docunit projects --out projects.yaml` regenerates the registry from the
`project.md` anchors; `docunit projects --check` fails CI if it drifts from the
anchors or if any project id/code is duplicated.

## Traceability & consistency

Requirements and other traceable rows are authored as **items** with stable IDs
and typed links:

```
- **AUR-BR-001**: The business shall reduce onboarding time to under 2 days.
- **AUR-PR-014** (traces: AUR-BR-001): The product shall provide a self-serve flow.
- **AUR-AC-001** (verifies: AUR-PR-014): Given a new customer…, then an active account exists.
- **AUR-TC-001** (tests: AUR-AC-001): Steps… Expected…
```

`docunit consistency` builds the graph across every document and checks it:

- **Structural (blocking):** every link resolves (broken references always
  block), item IDs are unique, and — once a document is `status: approved` —
  every item has its required upstream link and every parent is covered
  downstream. Work-in-progress (`draft`) is never blocked for incompleteness.
- **Semantic (advisory):** the AI judges whether each child genuinely fulfils
  the parent it links to (does AUR-PR-014 actually implement AUR-BR-001?).

`docunit rtm` renders the Requirements Traceability Matrix (Markdown or CSV)
from the same graph — traceability you can see, derived rather than authored.

The rules (required links, coverage, alignment prompts) live in
`consistency.yaml`, so an org tunes them without touching code.

## Project status (derived)

`docunit status` produces a status view computed entirely from the documents —
no self-reported RAG. It reads every document's validity, the traceability
coverage, the open risks, and derives its own health: **red** = something is
objectively broken (a failing approved document or a dangling link), **amber** =
carrying risk or coverage gaps, **green** = clean.

```bash
docunit status                          # whole-repo markdown to stdout
docunit status --format md --out STATUS.md       # the committed snapshot
docunit status --project PRJ-001-AUR             # scope to one project
docunit status --index                           # portfolio table (RAG per project)
docunit status --format json                     # machine-readable
docunit pages --out _site               # the full site: index + a page per project
```

Status is **per project**: `--project PRJ-NNN-CODE` scopes the documents,
coverage, risks and RAG to one project, and `--index` rolls every project up
into a portfolio table. `docunit rtm --project PRJ-NNN-CODE` scopes the
traceability matrix the same way.

Four ways it stays live:

1. **`STATUS.md`** in the repo (regenerate with the command above).
2. **A `status` CI job** posts the derived RAG + signals to every pull request.
3. **A Pages site** — `.github/workflows/status-pages.yml` runs `docunit pages`
   on every push to `main`, publishing a **portfolio index** (one linked RAG
   card per project) plus a **discrete status page for each project**.
   One-time setup: Settings → Pages → Source: **GitHub Actions**.
4. **`projects.yaml`** — the generated registry of every project.

## How it works

```
 Word / PDF ──▶ doc-to-pmo skill ──▶ documents/PRJ-001-AUR/charter.md
                                            │
                                     open a Pull Request
                                            │
                                 GitHub Actions runs docunit
                                            │
              ┌─────────────────────────────┴─────────────────────────────┐
     structural checks (deterministic)                 semantic checks (AI)
     required fields, measurable success                is the objective specific?
     criteria, risks with owner+mitigation,             are criteria verifiable?
     valid dates, resolving references                  scored 0–1 with rationale
              │                                                  │
        BLOCK the merge if any fail                     ADVISE reviewers (never block)
```

Two tiers, on purpose:

- **Structural checks are deterministic and blocking.** They are plain Python —
  reliable enough to gate a merge. Required frontmatter and sections, success
  criteria that state a measurable threshold, risks that name an owner and a
  mitigation, consistent dates, unique ids.
- **Semantic checks are AI-graded and advisory.** They use the Anthropic API to
  score softer rubric questions and post the scores to the PR. Because a model
  is non-deterministic, these **never** block a merge — they inform reviewers.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"                 # add ".[ai]" for semantic scoring

# validate the sample charter (passes)
docunit validate documents/PRJ-001-AUR/charter.md

# validate every document across all projects
docunit validate 'documents/**/*.md'

# validate a deliberately weak one (3 blocking failures, exit code 3)
docunit validate tests/fixtures/weak-example.md

# run the checker's own unit tests
pytest
```

To enable AI advisory scoring, set `ANTHROPIC_API_KEY` in your environment (and,
in CI, as a repository secret). Without it, the semantic checks are skipped and
the structural gate still works.

## Repository layout

| Path | Purpose |
|---|---|
| `documents/PRJ-NNN-CODE/` | One folder per project — the source of truth. Each holds a `project.md` anchor plus its Markdown business documents. |
| `projects.yaml` | Generated registry of all projects (`docunit projects`). Kept fresh by CI. |
| `templates/<kind>.template.md` | The canonical shape for each kind (fill these in). |
| `schema/<kind>.schema.json` | JSON Schema for each kind's frontmatter. |
| `criteria/<kind>.criteria.yaml` | The configurable audit standard — edit to tune what "passing" means. |
| `consistency.yaml` | Cross-document traceability rules (required links, coverage, alignment). |
| `docunit/` | The validator (loader, structural checks, semantic checks, graph, reports, CLI). |
| `.github/workflows/audit.yml` | Runs the audit + consistency on every PR and gates the merge. |
| `.claude/skills/doc-to-pmo/` | The Claude skill that converts Word/PDF into a template document. |

## Adding the merge gate

Once pushed to GitHub, protect `main` so the audit must pass:
Settings → Branches → add a rule for `main` → require the **docunit audit**
status check. After that, a PR whose changed documents fail any structural
check cannot be merged until it's fixed.

## Extending to new document kinds

Add `templates/<kind>.template.md`, `schema/<kind>.schema.json`, and
`criteria/<kind>.criteria.yaml`. Structural checks are keyed by id in
`docunit/structural.py`; reuse the existing ones or add new functions to the
`CHECKS` registry.
