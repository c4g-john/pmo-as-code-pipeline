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

- **Discovery:** `charter`, `business-case`
- **Requirements:** `brd`, `prd`, `frnfr`, `user-story`, `test-cases`
- **Design & governance:** `adr`, `risk-register`, `raci-stakeholder`
- **Delivery:** `qa-test-plan`, `data-migration-plan`
- **Release & operate:** `release-cutover-plan`, `rollback-plan`,
  `hypercare-plan`, `runbook`
- **Report & close:** `status-report`, `post-implementation-review`,
  `benefits-realization`

## Traceability & consistency

Requirements and other traceable rows are authored as **items** with stable IDs
and typed links:

```
- **BR-001**: The business shall reduce onboarding time to under 2 days.
- **PR-014** (traces: BR-001): The product shall provide a self-serve flow.
- **AC-001** (verifies: PR-014): Given a new customer…, then an active account exists.
- **TC-001** (tests: AC-001): Steps… Expected…
```

`docunit consistency` builds the graph across every document and checks it:

- **Structural (blocking):** every link resolves (broken references always
  block), item IDs are unique, and — once a document is `status: approved` —
  every item has its required upstream link and every parent is covered
  downstream. Work-in-progress (`draft`) is never blocked for incompleteness.
- **Semantic (advisory):** the AI judges whether each child genuinely fulfils
  the parent it links to (does PR-014 actually implement BR-001?).

`docunit rtm` renders the Requirements Traceability Matrix (Markdown or CSV)
from the same graph — traceability you can see, derived rather than authored.

The rules (required links, coverage, alignment prompts) live in
`consistency.yaml`, so an org tunes them without touching code.

## How it works

```
 Word / PDF ──▶ doc-to-pmo skill ──▶ documents/charters/aurora.md
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
docunit validate documents/charters/aurora.md

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
| `documents/` | The source of truth — normalized Markdown business documents. |
| `templates/charter.template.md` | The canonical charter shape (fill this in). |
| `schema/charter.schema.json` | JSON Schema for charter frontmatter. |
| `criteria/charter.criteria.yaml` | The configurable audit standard — edit this to tune what "passing" means. |
| `docunit/` | The validator (loader, structural checks, semantic checks, reports, CLI). |
| `.github/workflows/audit.yml` | Runs the audit on every PR and gates the merge. |
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
