# Synthetic reports (demo only)

Sample pharmaceutical reports for testing the compliance agent. **Each file has 500–1000 statements (sentences)** for robust testing. No real patient data.

| File | Expected result | Description |
|------|------------------|-------------|
| `01_clean.txt` | PASS | Compliant; no PII, no AE triggers, no off-label/comparative language |
| `02_privacy_violation.txt` | FAIL | PII/PHI: name, phone, email, location |
| `03_off_label.txt` | FAIL | Off-label promotional phrasing |
| `04_ae_without_reporting.txt` | FAIL | AE keywords present, no reporting context |
| `05_comparative_claim.txt` | NEEDS_REVIEW | Comparative/superiority language |
| `06_ae_mandatory_reporting.txt` | FAIL | Escalation flags (serious, hospitalization, etc.) |

**Regenerate (500–1000 statements each):**  
`python synthetic_reports/generate_reports.py`  
(From project root. Uses fixed seed for reproducibility.)

**CLI:** `python compliance_agent.py synthetic_reports/01_clean.txt`

**UI:** Paste the contents of any file (or a portion) into the web form and click Check Compliance.
