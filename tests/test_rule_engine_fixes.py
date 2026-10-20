"""Regression tests for the 2026-10-20 audit fix round (AUDIT.md findings 1-4).

Each test names the finding it covers. These run against the REAL
config/rules.yaml and the fixed src/rule_engine.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.rule_engine import run_checks

RULES = Path(__file__).resolve().parent.parent / "config" / "rules.yaml"


def rule_ids(text):
    return {v["rule_id"] for v in run_checks(text, RULES)}


# Finding 1 — privacy FP: "patient" + any word must not flag as a name.
def test_patient_plus_verb_is_not_a_name():
    text = "The patient experienced nausea and dizziness after starting the drug."
    assert "privacy" not in rule_ids(text)


def test_real_patient_name_still_flags():
    text = "Patient John Smith, contacted us at 555-123-4567 regarding his experience."
    assert "privacy" in rule_ids(text)


def test_titled_name_still_flags():
    assert "privacy" in rule_ids("The report was filed by Dr. Patel yesterday.")


def test_national_id_flags():
    assert "privacy" in rule_ids("The form lists the identifier 123-45-6789 in error.")


# Finding 2 — negation: "No hospitalization was required" is not context.
def test_negated_hospitalization_does_not_suppress_ae():
    text = ("The patient experienced nausea and dizziness after starting the drug. "
            "She discontinued the medication after three days. "
            "No hospitalization was required. We are collecting follow-up information.")
    ids = rule_ids(text)
    assert "adverse_event" in ids
    assert "mandatory_reporting_context" not in ids


def test_real_hospitalization_still_escalates():
    text = "The patient developed a severe rash and hospitalization was required for observation."
    assert "mandatory_reporting_context" in rule_ids(text)


def test_negated_ae_keyword_does_not_trigger():
    text = "The patient reported no nausea and no dizziness during the study visit."
    assert "adverse_event" not in rule_ids(text)


# Finding 3 — off-label anchoring: compliant recitation must not flag.
def test_approved_indication_recitation_is_clean():
    text = ("The product is authorised for the management of hypertension in adults "
            "as per the label. It is approved for once-daily dosing.")
    assert "off_label_promotion" not in rule_ids(text)


def test_unanchored_promotion_still_flags():
    text = ("This medication is recommended for weight loss and is effective for "
            "improving energy levels.")
    assert "off_label_promotion" in rule_ids(text)


def test_explicit_off_label_admission_flags():
    text = "This use is not approved and remains an unapproved indication."
    assert "off_label_promotion" in rule_ids(text)


# Finding 4 — word boundaries: substrings inside other words must not match.
def test_rash_inside_crash_does_not_trigger_ae():
    text = "The delivery vehicle was involved in a crash near the depot on Tuesday."
    assert "adverse_event" not in rule_ids(text)


def test_standalone_rash_still_triggers_ae():
    text = "The patient developed a rash two days after the first dose."
    assert "adverse_event" in rule_ids(text)
