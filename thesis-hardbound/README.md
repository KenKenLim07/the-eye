# Hardbound Thesis (Markdown → DOCX)

This folder is the **hardbound thesis workspace**.

## Workflow
- **Source of truth:** Markdown in `thesis-hardbound/chapters/`
- **Style template:** `thesis-hardbound/reference/reference.docx`
- **Citations:** `thesis-hardbound/bibliography/references.bib` + `thesis-hardbound/bibliography/numeric.csl`
- **Output:** `thesis-hardbound/dist/thesis.docx`

## One-time: convert the current Word thesis into a Markdown baseline
```bash
./thesis-hardbound/scripts/convert_docx_to_md.sh
```

## Build DOCX (hardbound output)
```bash
./thesis-hardbound/scripts/build_docx.sh
```

## Notes
- The baseline Markdown is a starting point; you will refine it into chapter files `01_...md`, etc.
- `thesis-hardbound/SYSTEM_FACTS.md` is meant to be a verified “truth” file you can give to an AI tool while drafting chapters.

