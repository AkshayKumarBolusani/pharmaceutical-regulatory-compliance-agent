# Phase 1 — Proposal: Folder Structure & Regulatory Documents

**Status:** Approved; refinements applied. Notebooks generated.

**Assumptions:** College research project; no production legal use; all sources are publicly available; no scraping of paywalled or copyrighted material. Users download PDFs manually from official links below.

---

## 1. Proposed Folder Structure

```
Pharmaceutical Regulatory Compliance Agent/
├── README.md                    # How to run Phase 1 (after confirmation)
├── PHASE1_PROPOSAL.md           # This file
├── requirements.txt             # Python deps for ingestion, chunking, vector store
│
├── config/
│   ├── chunk_schema.json        # JSON schema for policy chunks (existing)
│   ├── rules.yaml               # Rule taxonomy (to create after confirmation)
│   └── sources_metadata.json    # Optional copy/mirror of data/raw_policies manifest
│
├── data/
│   ├── raw_policies/            # User-downloaded PDFs + manifest
│   │   ├── sources_metadata.json
│   │   └── *.pdf                # One PDF per source (see list below)
│   ├── processed/
│   │   ├── clean_text/          # Extracted, cleaned .txt per document
│   │   └── chunked/             # Clause-aware chunks as JSON (one file per source or combined)
│   └── README.md                # What each folder contains
│
├── notebooks/
│   ├── 01_policy_ingestion.ipynb    # Load PDFs, extract text, preserve headings (to generate)
│   ├── 02_chunking.ipynb            # Clause-aware chunking → JSON (to generate)
│   ├── 03_vector_index.ipynb        # Embeddings + Chroma/FAISS, save index (to generate)
│   └── 04_retrieval_test.ipynb      # Query → retrieved regulation text (to generate)
│
└── outputs/
    ├── vector_index/            # Persisted ChromaDB or FAISS index
    └── reports/                 # Optional: Phase 1 summary report
```

**Note:** Notebooks 01–04 are not yet generated; they will be created after you confirm this proposal.

---

## 2. Exact Regulatory Documents (Traceable, Public)

Each row is one **authoritative public document**. You will place the downloaded PDF in `data/raw_policies/` with the suggested filename. No scraping: manual download only.

| # | Authority | Country | Category | Exact document name / description | Public source (official) | Suggested filename |
|---|-----------|---------|----------|------------------------------------|---------------------------|---------------------|
| 1 | FDA | USA | Promotion | *Brief Summary and Adequate Directions for Use: Disclosing Risk Information in Consumer-Directed Print Advertisements and Promotional Labeling for Prescription Drugs* (Aug 2015, Rev 2) | FDA.gov → Guidance Documents; direct PDF on fda.gov | `FDA_risk_disclosure_promo.pdf` |
| 2 | FDA | USA | Adverse events | *Postmarketing Safety Reporting for Human Drug and Biological Products* (Guidance for Industry) | FDA.gov → Guidance Documents | `FDA_postmarketing_safety_reporting.pdf` |
| 3 | FDA | USA | Adverse events | *Best Practices for FDA Staff in the Postmarketing Safety Surveillance of Human Drug and Biological Products* (Jan 2024) | FDA.gov | `FDA_postmarketing_surveillance_best_practices.pdf` |
| 4 | EMA | EU | Pharmacovigilance | *Good Pharmacovigilance Practices (GVP) — Module VI: Management and reporting of adverse reactions to medicinal products* (Rev 1) | EMA.europa.eu → GVP → Module VI PDF | `EMA_GVP_Module_VI.pdf` |
| 5 | EMA | EU | Pharmacovigilance | *GVP Annex I — Definitions* (Rev 4) | EMA.europa.eu → GVP → Annex I PDF | `EMA_GVP_Annex_I_Definitions.pdf` |
| 6 | CDSCO | India | Adverse events / Pharmacovigilance | *Pharmacovigilance Guidance Document for Marketing Authorization Holders of Pharmaceutical Products* (Version 2.0) | cdsco.gov.in (e.g. Post-Marketing DSM / PV guidance); also IPC | `CDSCO_PV_guidance_pharma.pdf` |
| 7 | India (Central Govt) | India | Promotion | *Drugs and Magic Remedies (Objectionable Advertisements) Act, 1954* — official Indian law restricting objectionable drug advertisements and promotion | indiacode.nic.in or lawmin.gov.in (official Act PDF) | `India_Drugs_and_Magic_Remedies_Act_1954.pdf` |
| 8 | ICH | International | Safety | *ICH E2A: Clinical Safety Data Management: Definitions and Standards for Expedited Reporting* | database.ich.org (E2A Guideline PDF) | `ICH_E2A.pdf` |
| 9 | ICH | International | Safety | *ICH E2D: Post-Approval Safety Data Management: Definitions and Standards for Expedited Reporting* | database.ich.org (E2D Guideline PDF) | `ICH_E2D.pdf` |
| 10 | EU (EUR-Lex) | EU | Privacy | *Regulation (EU) 2016/679* (GDPR) — full text. **GDPR scope:** Only pharma-relevant GDPR articles (e.g. Articles 4, 5, 6, 9, 17) are used for compliance reasoning; the full regulation is stored for traceability. | eur-lex.europa.eu — PDF of 32016R0679 | `GDPR_32016R0679.pdf` |
| 11 | HHS | USA | Privacy | *HIPAA Privacy Rule* — 45 CFR Part 160 and Subparts A and E of Part 164 (e.g. HHS “Privacy Rule” PDF) | hhs.gov/hipaa — official PDFs | `HIPAA_Privacy_Rule.pdf` |

**Mapping for metadata:**  
- **Promotion:** 1, 7  
- **Adverse events / Safety reporting:** 2, 3, 4, 5, 6, 8, 9  
- **Pharmacovigilance:** 4, 5, 6  
- **Privacy:** 10, 11  

**Country/region:** USA (1,2,3,11), EU (4,5,10), India (6,7), International (8,9).

**GDPR scope (viva defence):** Only pharma-relevant GDPR articles (e.g. Articles 4, 5, 6, 9, 17) are used for compliance reasoning; the full regulation is stored for traceability.

---

## 3. Data Ingestion (Notebook 01 — after confirmation)

- **Input:** PDFs in `data/raw_policies/` (filenames matched to `sources_metadata.json` or a simple mapping table).
- **Steps:** Load PDF → extract text (e.g. `pypdf` or `pdfplumber`), preserve section headings where possible, write cleaned text to `data/processed/clean_text/`.
- **Output:** One `.txt` per document; comments in notebook will cite the exact document names and sources from Section 2.

---

## 4. Policy Chunking Strategy (Notebook 02 — after confirmation)

- **Clause-aware chunking:** Split on section numbers, “Article”, “Section”, numbered clauses (e.g. 1.1, 1.2), and similar structure. No fixed character/window chunking.
- **Metadata per chunk:** `source` (authority), `country`, `category` (privacy | AE | promotion | pharmacovigilance | safety), plus optional `source_id`, `chunk_index`, `page_start`, `page_end`.
- **Output:** Structured JSON conforming to `config/chunk_schema.json` (one file per source or one combined `chunks.json`).

---

## 5. Vector Knowledge Base (Notebooks 03 & 04 — after confirmation)

- **Notebook 03:** Embed chunks (e.g. `sentence-transformers`), store in **ChromaDB** (or FAISS), save index under `outputs/vector_index/`.
- **Notebook 04:** Simple retrieval test: input query string → return top-k chunks with `text` and metadata (no LLM).

---

## 6. Rule Taxonomy (YAML/JSON)

- **Deterministic, auditable rules** for:
  - **Privacy:** PII/PHI entity types (e.g. patient name, phone, address) — forbidden in certain contexts.
  - **Adverse events:** Trigger keyword list (e.g. nausea, dizziness, stopped medication).
  - **Off-label promotion:** Phrase patterns (e.g. “use for”, “indicated for” outside approved indication).
  - **Comparative claims:** Indicators for head-to-head or superiority claims (e.g. “better than”, “more effective”).
  - **mandatory_reporting_context:** Used in Phase 2 to decide when an AE must escalate. Example flags: `serious`, `hospitalization`, `death`, `discontinuation`. Phase 1 only defines the rule class; no escalation logic yet.
- Stored in `config/rules.yaml`, no ML, no LLM.

---

## 7. What We Will Not Do (Phase 1)

- No UI, FastAPI, or frontend.
- No LLM reasoning or generation.
- No overclaiming of legal correctness; all references traceable to the authorities above.
- No scraping; user-supplied PDFs only.
- No regulatory approval or certification claims.

---

## 8. Refinements Applied (Audit)

- **CDSCO promotion:** Row #7 fixed to *Drugs and Magic Remedies (Objectionable Advertisements) Act, 1954*; filename `India_Drugs_and_Magic_Remedies_Act_1954.pdf`.
- **GDPR scope:** Explicit statement added: only pharma-relevant articles (e.g. 4, 5, 6, 9, 17) used for compliance reasoning; full regulation stored for traceability.
- **Rule taxonomy:** `mandatory_reporting_context` added (flags: serious, hospitalization, death, discontinuation) for Phase 2 AE escalation.
