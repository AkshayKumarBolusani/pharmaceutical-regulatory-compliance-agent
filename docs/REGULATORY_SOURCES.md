# Regulatory Sources — Provenance & Verification

**Manifest:** `data/raw_policies/sources_metadata.json` (manifest_version 2.0, last verified 2026-10-20)
**Release-candidate working corpus:** `data/processed/clean_text/` — 6 cleaned text files, indexed by `scripts/build_index.py` (255 chunks, verified 2026-10-20). The three excluded EMA/ICH texts are documented in the manifest but are not shipped; restoring them locally produces the historical full-corpus count of 649 chunks.

This document is the human-readable view of the machine-readable manifest.
Every URL below was checked on 2026-10-20 with web search/fetch tooling;
the `url_status` field in the manifest records exactly how far verification
got. **A URL marked `unverified` means no URL is claimed** — the manifest's
`official_url` is intentionally empty for those sources.

## Provenance table

| ID | Document (as named in manifest) | Authority / Jurisdiction | Version / date | Official URL | URL status | Applicable rules |
|---|---|---|---|---|---|---|
| FDA_PROMO | Brief Summary and Adequate Directions for Use: Disclosing Risk Information in Consumer-Directed Print Advertisements and Promotional Labeling for Prescription Drugs | FDA / USA | 2015-08 (Revision 2, revised draft guidance) | [fda.gov PDF](https://www.fda.gov/files/drugs/published/Brief-Summary-and-Adequate-Directions-for-Use---Disclosing-Risk-Information-in-Consumer-Directed-Print-Advertisements-and-Promotional-Labeling-for-Prescription-Drugs.pdf) | verified | off_label_promotion, comparative_claims |
| FDA_AE_1 | Postmarketing Safety Reporting for Human Drug and Biological Products (Guidance for Industry) | FDA / USA | not stated in title (null) | — | unverified | adverse_event, mandatory_reporting_context |
| FDA_AE_2 | Best Practices for FDA Staff in the Postmarketing Safety Surveillance of Human Drug and Biological Products | FDA / USA | 2024-01 (final; Federal Register Vol. 89 No. 18, 26 Jan 2024, Docket FDA-2023-N-2853) | [fda.gov CDER page](https://www.fda.gov/drugs/cder-conversations/understanding-cders-postmarket-safety-surveillance-programs-and-public-data) | landing_page_only | adverse_event, mandatory_reporting_context |
| EMA_GVP_VI | GVP Module VI: Management and reporting of adverse reactions to medicinal products (Rev 1), EMA/873138/2011 | EMA / EU | Rev 1 — adopted 2014-09-08, in effect 2014-09-16 | [ema.europa.eu PDF](https://www.ema.europa.eu/en/documents/scientific-guideline/guideline-good-pharmacovigilance-practices-module-vi-management-and-reporting-adverse-reactions-medicinal-products-rev-1-superseded_en.pdf) | verified | adverse_event, mandatory_reporting_context |
| EMA_GVP_ANNEX_I | GVP Annex I — Definitions (Rev 4), EMA/876333/2011 | EMA / EU | Rev 4 — legal effective date 2017-10-13 | [ema.europa.eu GVP archive page](https://www.ema.europa.eu/it/human-regulatory-overview/post-authorisation/pharmacovigilance-post-authorisation/good-pharmacovigilance-practices-gvp/archive-development-good-pharmacovigilance-practices) | landing_page_only | definitions_supporting |
| CDSCO_PV | Pharmacovigilance Guidance Document for Marketing Authorization Holders of Pharmaceutical Products (Version 2.0) | CDSCO / India | Version 2.0 — 2024-09-17 | [cdsco.gov.in Post-Marketing DSM page](https://cdsco.gov.in/opencms/opencms/en/Post-Marketing-DSM/) | landing_page_only | adverse_event, mandatory_reporting_context |
| INDIA_DMRA_1954 | Drugs and Magic Remedies (Objectionable Advertisements) Act, 1954 | Government of India / India | 1954 (Act No. 21 of 1954) | — | unverified | off_label_promotion |
| ICH_E2D | ICH E2D: Post-Approval Safety Data Management: Definitions and Standards for Expedited Reporting | ICH / International | not stated in title (null); Step 4 adoption Nov 2003 | — | unverified | adverse_event, mandatory_reporting_context |
| HIPAA | HIPAA Privacy Rule (45 CFR Part 160 and Subparts A and E of Part 164) | HHS / USA | not stated in title (null) | [hhs.gov Privacy Rule page](https://www.hhs.gov/hipaa/for-professionals/privacy/laws-regulations/index.html) | landing_page_only | privacy |
| GDPR | Regulation (EU) 2016/679 (General Data Protection Regulation), OJ L 119, 4 May 2016 | European Parliament & Council / EU | 2016-04-27 (applies from 2018-05-25) | [eur-lex.europa.eu](https://eur-lex.europa.eu/legal-content/EN/LSU/?uri=CELEX:32016R0679) | verified | privacy — **NOT IN CORPUS** (see below) |

`definitions_supporting` is not an engine rule ID: GVP Annex I is a
definitions source that underpins the terminology of the other documents.

## Verification notes (evidence, 2026-10-20)

- **FDA_PROMO — verified.** The fda.gov PDF was fetched and read; its title
  page states "August 2015 / Advertising / Revision 2 / Revised Draft
  Guidance", matching the manifest title.
- **EMA_GVP_VI — verified.** The ema.europa.eu PDF was fetched and read;
  it is EMA/873138/2011 Rev 1, adopted 8 September 2014.
- **CDSCO_PV — landing page only.** The CDSCO Post-Marketing DSM page was
  fetched and read; its document table lists the exact guidance title with
  "Version: 2.0" and release date 2024-Sep-17. The direct PDF link behind
  the page's download button was not captured.
- **HIPAA — landing page only.** The hhs.gov page was fetched and read; it
  is HHS's official Privacy Rule page and states the combined rule text is
  at 45 CFR Part 160 and Part 164, Subparts A and E.
- **FDA_AE_2 — landing page only.** No exact document URL was verified.
  The linked FDA CDER page discusses FDA's postmarket safety surveillance
  programme and names the Best Practices document. The final document's
  availability was announced in the Federal Register (Vol. 89, No. 18,
  26 January 2024; Docket No. FDA-2023-N-2853).
- **FDA_AE_1 — unverified.** A candidate fda.gov media-download URL was
  located in search results, but a direct fetch was rejected (HTTP 401),
  so no URL is claimed. External reporting describes the underlying FDA
  document as a March 2001 *draft* guidance ("…Including Vaccines"); the
  manifest title does not state a date or draft status — a manifest
  accuracy gap to resolve when the PDF is next downloaded.
- **INDIA_DMRA_1954 — unverified.** An India Code (indiacode.gov.in)
  content URL serving the Act's text was located in search results, but
  the fetch tooling could not resolve it; no URL is claimed.
- **ICH_E2D — unverified.** No verbatim ich.org URL for the original E2D
  document was obtained.
- **GDPR — URL verified, document absent.** The EUR-Lex page is the
  official summary for CELEX 32016R0679. See the GDPR section below.

## Currency findings (outdated sources in the corpus)

Verification surfaced three sources that are **not the current version** —
the corpus was assembled from older revisions and never refreshed:

1. **EMA GVP Module VI** — corpus holds **Rev 1 (2014)**, which EMA marks
   *superseded*; **Rev 2** is the current version.
2. **EMA GVP Annex I** — corpus holds **Rev 4 (2017)**, marked superseded
   in EMA's archive; **Rev 5 is dated 26 July 2024**.
3. **ICH E2D** — corpus holds the **original E2D (2003)**; ICH adopted
   **E2D(R1)** on 15 September 2025 (per the ICH document history).

Retrieval results and explanations grounded in these texts therefore
reflect superseded revisions. Refreshing the corpus is a content decision
for the project owner, not something done silently here.

## GDPR is missing from the corpus

Early project documents imply GDPR coverage — the manifest itself still
carries a `gdpr_scope_note` claiming pharma-relevant GDPR articles "are
used for compliance reasoning" — **but no GDPR text exists anywhere in the
repository**: there is no GDPR file in `data/processed/clean_text/`, and
the original manifest had no GDPR source entry. The manifest now contains
an explicit GDPR entry with `corpus_status:
"missing_named_in_early_docs_not_in_corpus"` and no `file` key, so the gap
is machine-visible rather than implied. The stale `gdpr_scope_note` was
left untouched (the manifest extension only adds fields) and should be
corrected or removed by the project owner. Until a GDPR text is actually
added, no GDPR-based claim should be made for this system: the `privacy`
rule is grounded in the HIPAA text only.

## PDFs, cleaned texts, and redistribution

- **Source PDFs are not committed.** `data/raw_policies/` contains only
  the manifest; `.gitignore` excludes `data/raw_policies/*.pdf`. PDFs are
  downloaded manually from the official sources (notebook 01 expects them
  there and produces the cleaned texts).
- **The cleaned texts are the working corpus.** `data/processed/
  clean_text/*.txt` (produced by notebook 01 from the PDFs) is what
  `scripts/build_index.py` chunks and indexes. The vector index in
  `outputs/vector_index/` is a generated artifact (also gitignored) —
  rebuild it, don't commit it.
- **Redistribution cautions.** Per-source `reuse_notes` live in the
  manifest. Summary: US federal documents (FDA, HHS) are generally not
  subject to domestic copyright (17 U.S.C. §105); EMA documents state
  reproduction is authorised provided the source is acknowledged; ICH
  guidelines are copyrighted by ICH and are included on a
  reference/citation basis only — **do not redistribute them
  commercially**; CDSCO reuse terms are not stated on the listing page,
  so reference/citation only; Indian legislation is published via India
  Code. These notes are factual pointers, **not legal advice**. The fact
  that cleaned texts of EMA/ICH documents are committed in this repository
  is a pre-existing project state, flagged here for the owner's licensing
  decision — it is not endorsed by this document.
  **Update 2026-10-20:** the project code was licensed MIT (owner's
  decision); the license expressly does not cover these texts, and the
  redistribution question above remains recorded as an unresolved concern
  in the repo-root `NOTICE.md` for the owner to settle before public
  release.
- **Release-candidate exclusion (2026-10-20).** Acting on that concern, the
  cleaned texts of the three EMA/ICH sources (EMA GVP Module VI, EMA GVP
  Annex I, ICH E2D) are **excluded from the release candidate**: the files
  are not shipped, and their manifest entries carry
  `corpus_status: excluded_from_distribution_pending_redistribution_verification`
  with official URLs and restoration instructions. The shipped corpus is
  the other 6 texts (255 index chunks vs 649 for the full corpus). This
  exclusion limits future distribution of the release candidate; it does
  not alter copies already present in the project's earlier public
  history, which only a separate history decision by the owner could
  address.
