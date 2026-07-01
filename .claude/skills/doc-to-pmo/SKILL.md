---
name: doc-to-pmo
description: Convert an existing business document (Word .docx, PDF, or pasted text) into the standard docunit Markdown template so it can be unit-tested by the pipeline. Use when someone wants to bring an existing charter (or other supported kind) into the PMO-as-Code repo.
---

# doc-to-pmo

Convert a messy source document into a standard-template Markdown file that the
`docunit` pipeline can validate. **Map the content faithfully — never invent
missing facts to make the audit pass.** A document that lacks measurable
success criteria *should* fail the audit; your job is to surface that, not hide
it.

## Steps

1. **Identify the kind.** Currently supported: `charter`. Read
   `templates/charter.template.md` for the required frontmatter and sections,
   and `criteria/charter.criteria.yaml` for what will be checked.

2. **Extract the source text** with the bundled extractor (handles `.docx`,
   `.pdf`, `.md`, `.txt`):

   ```bash
   pip install '.[convert]'                 # one-time: python-docx + pypdf
   python tools/extract.py path/to/source.docx
   ```

   For pasted text or Google Docs, ask the user to paste the content or export
   to `.docx`/`.pdf` first.

3. **Map into the template.** Create `documents/charters/<id>.md` where `<id>`
   is a lowercase, hyphenated slug of the title.
   - Fill frontmatter (`title`, `sponsor`, `budget`, `dates`, `status`) from
     the source. Use `status: draft` unless the source clearly states otherwise.
   - Populate every required section (`Objective`, `Success Criteria`, `Scope`,
     `Milestones`, `Risks`, `Approval`) from the corresponding source content.
   - Format risks as one bullet each, ending with `Owner: <name>. Mitigation:
     <text>.` — pull the owner and mitigation from the source if present.

4. **Flag gaps honestly.** Wherever the source does not supply required
   information, insert a bullet or note beginning with `TODO:` describing what
   is missing (e.g. `- TODO: no measurable success criteria found in the
   source — add a metric and threshold.`). Do **not** fabricate a number, an
   owner, or a mitigation.

5. **Validate and report.** Run
   `docunit validate documents/charters/<id>.md` and show the user the result.
   Summarise what passed, what is blocking, and exactly which TODOs they must
   resolve before the document can merge.

6. **Hand off.** Tell the user to review the generated file, resolve the TODOs,
   then commit it and open a pull request — CI will re-run the same audit and
   gate the merge.

## Guardrails

- Faithful over passing: it is correct and expected for a weak source document
  to produce a file that fails the audit. That is the pipeline working.
- Never write into the `status`-equivalent or invent approvals.
- If you are unsure whether something in the source is a real measurable
  criterion, leave it as-is and let the audit judge it.
