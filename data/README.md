# Data layout

- **raw_policies/** — Place regulatory PDFs here. See `sources_metadata.json` and [PHASE1_PROPOSAL.md](../PHASE1_PROPOSAL.md) for exact document list and filenames.
- **processed/clean_text/** — Extracted and cleaned text (one `.txt` per document), produced by notebook 01.
- **processed/chunked/** — Clause-aware chunks in JSON format, produced by notebook 02.

Do not commit large PDFs if your repo has size limits; use `.gitignore` for `*.pdf` in `raw_policies` if needed.
