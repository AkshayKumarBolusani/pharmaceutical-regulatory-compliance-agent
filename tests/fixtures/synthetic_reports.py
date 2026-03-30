"""
Phase 2 — Synthetic test reports (no real patient data).
Covers: clean, privacy, off-label, AE without reporting, comparative claim.
"""

# 1. Clean compliant report (no PII, no AE trigger keywords, no off-label/comparative phrasing)
CLEAN_REPORT = """
The product is authorised for the management of hypertension in adults as per the label.
Refer to the full prescribing information for safety information.
Patients should discuss any concerns with their healthcare provider.
"""

# 2. Privacy violation — PII/PHI present
PRIVACY_VIOLATION_REPORT = """
Patient John Smith, date of birth 1985-03-12, from Boston, Massachusetts,
contacted us at 555-123-4567 and john.smith@email.com regarding his experience.
He reported taking the medication for two weeks. We have documented his feedback.
"""

# 3. Off-label promotion — promotional phrasing without approved-indication anchor
OFF_LABEL_REPORT = """
This medication is recommended for weight loss and is effective for improving
energy levels. Many physicians use it for off-label indications with good results.
Consider recommending for patients seeking these benefits.
"""

# 4. AE without reporting context — trigger keywords, no escalation flags
AE_WITHOUT_REPORTING_REPORT = """
The patient experienced nausea and dizziness after starting the drug.
She discontinued the medication after three days. No hospitalization was required.
We are collecting follow-up information.
"""

# 5. Comparative claim — superiority language
COMPARATIVE_CLAIM_REPORT = """
Our drug is better than the leading competitor and has been shown to outperform
other treatments in real-world use. Head-to-head studies suggest superior efficacy.
Consider positioning as the number one choice for this indication.
"""

# Optional: AE with mandatory reporting context (escalation flags)
AE_WITH_REPORTING_CONTEXT_REPORT = """
Serious adverse event: patient was hospitalized due to severe hypersensitivity reaction.
The event was life_threatening. Treatment was discontinued. Congenital anomaly was not reported.
Expedited reporting has been initiated.
"""

# All test cases for iteration
ALL_CASES = [
    ("clean", CLEAN_REPORT, "PASS"),
    ("privacy", PRIVACY_VIOLATION_REPORT, "FAIL"),
    ("off_label", OFF_LABEL_REPORT, "FAIL"),
    ("ae_without_reporting", AE_WITHOUT_REPORTING_REPORT, "FAIL"),
    ("comparative", COMPARATIVE_CLAIM_REPORT, "NEEDS_REVIEW"),
]
