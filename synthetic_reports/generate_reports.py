#!/usr/bin/env python3
"""
Generate synthetic report files with 500-1000 statements (sentences) each.
Keeps violation type and expected outcome; fills with neutral report-style sentences.
No real patient data. Run from project root: python synthetic_reports/generate_reports.py
"""

import random
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent
random.seed(42)

# Neutral filler statements (no PII, no AE triggers, no off-label, no comparative)
FILLER = [
    "This document is for internal use only.",
    "The reporting period has been closed.",
    "All materials were reviewed against the approved label.",
    "Healthcare providers should refer to the prescribing information.",
    "The benefit-risk profile remains favourable.",
    "No new safety signals were identified in this period.",
    "Compliance review was completed on schedule.",
    "The summary of product characteristics is the source of truth.",
    "Local regulations have been considered.",
    "Feedback was collected through standard channels.",
    "The product is authorised for the management of hypertension in adults as per the label.",
    "Refer to the full prescribing information for safety information.",
    "Patients should discuss any concerns with their healthcare provider.",
    "Post-marketing data are under continuous review.",
    "The committee noted no deviations from the approved indication.",
    "Training materials were updated in line with the latest guidance.",
    "Adverse events should be reported via the standard process.",
    "This summary does not constitute medical advice.",
    "Confidentiality of the process is maintained.",
    "The next review date has been set.",
    "All stakeholders were informed of the outcome.",
    "Document version control is in place.",
    "The audit trail is complete.",
    "Regulatory requirements have been met.",
    "No further action is required at this time.",
    "The report was prepared in accordance with internal procedures.",
    "Quality checks were performed before release.",
    "The designated contact has been notified.",
    "Archiving was completed as per retention policy.",
    "Cross-functional alignment was achieved.",
]

NUM_CORE_BLOCKS = 8  # how many times to inject violation sentences


def to_text(statements):
    out = []
    for s in statements:
        s = s.strip()
        if s and not s.endswith("."):
            s += "."
        if s:
            out.append(s)
    return " ".join(out) + "\n"


def generate_clean(n):
    """Clean report: only neutral filler. Expected PASS."""
    return to_text([random.choice(FILLER) for _ in range(n)])


def generate_with_core(n, core_list):
    """Build exactly n sentences: (n - NUM_CORE_BLOCKS*len(core)) filler + NUM_CORE_BLOCKS blocks of core."""
    block_len = len(core_list)
    filler_count = n - NUM_CORE_BLOCKS * block_len
    if filler_count < 0:
        filler_count = 0
    slots = ["filler"] * filler_count + ["core"] * NUM_CORE_BLOCKS
    random.shuffle(slots)
    out = []
    for slot in slots:
        if slot == "core":
            out.extend(core_list)
        else:
            out.append(random.choice(FILLER))
    return to_text(out)


def generate_privacy(n):
    core = [
        "Patient John Smith, date of birth 1985-03-12, from Boston, Massachusetts, contacted us at 555-123-4567 and john.smith@email.com regarding his experience.",
        "He reported taking the medication for two weeks.",
        "We have documented his feedback.",
    ]
    return generate_with_core(n, core)


def generate_off_label(n):
    core = [
        "This medication is recommended for weight loss and is effective for improving energy levels.",
        "Many physicians use it for off-label indications with good results.",
        "Consider recommending for patients seeking these benefits.",
    ]
    return generate_with_core(n, core)


def generate_ae_without_reporting(n):
    core = [
        "The patient experienced nausea and dizziness after starting the drug.",
        "She discontinued the medication after three days.",
        "No hospitalization was required.",
        "We are collecting follow-up information.",
    ]
    return generate_with_core(n, core)


def generate_comparative(n):
    core = [
        "Our drug is better than the leading competitor and has been shown to outperform other treatments in real-world use.",
        "Head-to-head studies suggest superior efficacy.",
        "Consider positioning as the number one choice for this indication.",
    ]
    return generate_with_core(n, core)


def generate_ae_mandatory_reporting(n):
    core = [
        "Serious adverse event: patient was hospitalized due to severe hypersensitivity reaction.",
        "The event was life_threatening.",
        "Treatment was discontinued.",
        "Congenital anomaly was not reported.",
        "Expedited reporting has been initiated.",
    ]
    return generate_with_core(n, core)


def main():
    configs = [
        ("01_clean.txt", generate_clean),
        ("02_privacy_violation.txt", generate_privacy),
        ("03_off_label.txt", generate_off_label),
        ("04_ae_without_reporting.txt", generate_ae_without_reporting),
        ("05_comparative_claim.txt", generate_comparative),
        ("06_ae_mandatory_reporting.txt", generate_ae_mandatory_reporting),
    ]
    for filename, gen_fn in configs:
        n = random.randint(500, 1000)
        path = OUTPUT_DIR / filename
        text = gen_fn(n)
        path.write_text(text, encoding="utf-8")
        num_sent = text.count(". ") + (1 if text.strip().endswith(".") else 0)
        print(f"{filename}: target {n} statements, ~{num_sent} sentences, {len(text)} chars")
    print("Done. Synthetic reports updated.")


if __name__ == "__main__":
    main()
