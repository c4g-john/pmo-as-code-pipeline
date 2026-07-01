# The conversion front-door

This directory demonstrates the front of the pipeline: turning an arbitrary
source document into a standard template document that `docunit` can validate.

## The flow

```
examples/source/project-meridian.docx      a charter written in Word, as prose
        │  python tools/extract.py …        deterministic text extraction
        ▼
   (the doc-to-pmo skill maps it into the charter template,
    filling what the source provides and flagging what it doesn't)
        │
        ▼
   first pass, with honest TODOs           ← fails the audit on real gaps
        │  a human resolves the TODOs
        ▼
documents/charters/meridian.md             ← passes the audit, mergeable
```

## Try it

```bash
pip install '.[convert]'
python tools/extract.py examples/source/project-meridian.docx
```

The sample source (`project-meridian.docx`) is a synthetic Word charter written
the way people actually write them: prose, some buzzwords, and gaps. It states
a sponsor, a budget, and a timeline, but its "success" is qualitative ("work
orders get done faster") and its risks name no owners.

## Why the first pass fails — and why that's correct

The skill maps the source **faithfully**. It does not invent measurable targets
or risk owners the source never supplied. So the first-pass document fails two
structural checks:

- `measurable-success-criteria` — the source's success was qualitative.
- `risks-have-owner-and-mitigation` — the source's risks had no owners.

That is the pipeline working as intended: the gaps in the original document are
surfaced immediately, as specific, actionable failures, instead of being
smoothed over. A human resolves the TODOs (see `documents/charters/meridian.md`
for the completed result), and the document then passes and can merge.
