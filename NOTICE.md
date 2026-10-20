# NOTICE — License scope and third-party content

**Project code license:** MIT (see `LICENSE`). The MIT license covers the
original code, tests, scripts, and documentation written for this project by
its author.

**What the MIT license does NOT cover:**

1. **Regulatory source texts.** The cleaned texts in
   `data/processed/clean_text/` are derived from publications of third-party
   authorities — the U.S. Food and Drug Administration (FDA), the U.S.
   Department of Health and Human Services (HHS/HIPAA), the European
   Medicines Agency (EMA), the Central Drugs Standard Control Organization
   (CDSCO, India), the International Council for Harmonisation (ICH), and
   the Government of India (Drugs and Magic Remedies Act, 1954). These
   remain the property of their issuing bodies under their own terms and are
   **not** relicensed under MIT. Per-source provenance, verification state,
   and reuse notes are recorded in `data/raw_policies/sources_metadata.json`
   and `docs/REGULATORY_SOURCES.md`.
   - U.S. federal works (FDA, HHS) are generally public domain.
   - EMA and ICH documents are copyrighted by their issuers; they are held
     here as research reference material. **Actioned 2026-10-20:** the
     cleaned EMA GVP and ICH E2D texts were **excluded from the release
     candidate** because their redistribution terms have not been verified.
     Their manifest entries, official URLs, and attribution are preserved
     in `data/raw_policies/sources_metadata.json` (status:
     `excluded_from_distribution_pending_redistribution_verification`),
     with instructions for obtaining the documents from official sources
     and restoring them locally. Note: exclusion from this release
     candidate does not alter copies already present in the project's
     earlier public history — see `docs/AUDIT_REPORT.md`.
   - Short regulatory titles and brief quoted phrases appearing in tests and
     fixtures are factual references, not reproduced works.
2. **Dependencies.** Third-party Python packages (ChromaDB, FastAPI, the
   ONNX embedding model, etc.) are **not vendored** in this repository and
   remain under their own licenses; installing them is governed by their
   terms, not this project's.
3. **Datasets.** The synthetic reports, fixtures, and the evaluation set in
   `evaluation/` were authored for this project and are covered by the MIT
   license, except for any regulatory titles/phrases they quote (see 1).
4. **The research paper.** Any manuscript derived from this project will
   carry its own license (e.g. CC BY 4.0) chosen at submission time; it is
   not covered by the code license.

**Provenance check (2026-10-20):** all Python sources were scanned for
third-party copyright headers, attribution notices, or copied-code markers —
none were found; the codebase is the author's original work. The only
third-party content in the repository is the regulatory texts in item 1 and
the items they name.
