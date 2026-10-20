"""Adversarial / hard-case battery for src/rule_engine.py (workstream D).

Purpose: EXPOSE behaviour, not fix it. Each test asserts the behaviour a
reasonable compliance reviewer would expect from the engine's own rule
definitions (config/rules.yaml). Where the engine deviates, the test is
marked xfail(strict=False) and cites a finding ID (D1..D12) documented in
the workstream D report — the assertion is NOT weakened, so a future fix
turns the test into an XPASS and signals the finding can be closed.

All expected/actual pairs in the finding comments were verified by actually
running run_checks() against the real config/rules.yaml on 2026-10-20.

UPDATE (coordinator, 2026-10-20): findings D1, D2, D3, D4, D5, D6, D7, D9,
D11 and D12 were FIXED in the E1 remediation round (clause-scoped negation
and anchoring, plural tolerance, wider privacy patterns — see
docs/AUDIT_REPORT.md); their xfail markers were removed and the tests now
run as strict assertions. The per-test comments quoting pre-fix "Actual:"
behaviour are historical. D8 (quoted-text keywords) and D10 (first-name-only
patient references) remain xfail as documented deterministic limits.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.rule_engine import run_checks

RULES = Path(__file__).resolve().parent.parent / "config" / "rules.yaml"


def rule_ids(text):
    return {v["rule_id"] for v in run_checks(text, RULES)}


# ---------------------------------------------------------------------------
# Negation scope
# ---------------------------------------------------------------------------

def test_no_nausea_was_reported_no_ae():
    assert "adverse_event" not in rule_ids("No nausea was reported.")


def test_real_ae_with_negated_hospitalization():
    """Real AE present; the only escalation flag is negated -> AE fires,
    mandatory reporting does not."""
    ids = rule_ids("The patient reported nausea. No hospitalization was required.")
    assert "adverse_event" in ids
    assert "mandatory_reporting_context" not in ids


def test_genuine_trigger_with_nearby_negations():
    """AE present; hospitalization AND seriousness both explicitly negated in
    the following sentence -> AE-without-context is the correct outcome."""
    text = ("The patient reported nausea. No hospitalization was required, "
            "and the event was not serious.")
    ids = rule_ids(text)
    assert "adverse_event" in ids
    assert "mandatory_reporting_context" not in ids


def test_negation_in_other_sentence_does_not_suppress_ae():
    text = ("No symptoms were reported by the placebo group. "
            "One participant experienced nausea and vomiting.")
    assert "adverse_event" in rule_ids(text)


def test_negation_in_other_sentence_does_not_suppress_flag():
    text = ("The consent form mentions no disability benefits. "
            "During the trial, one participant developed a permanent disability.")
    assert "mandatory_reporting_context" in rule_ids(text)


def test_nausea_was_not_reported_no_ae():
    """Follower negation ('was not reported') suppresses the keyword."""
    assert "adverse_event" not in rule_ids("Nausea was not reported by any patient.")


def test_patient_denies_symptoms_no_ae():
    assert "adverse_event" not in rule_ids("The patient denies nausea and vomiting.")


def test_death_did_not_occur_no_mandatory():
    """A document whose only content is a negated escalation flag."""
    assert "mandatory_reporting_context" not in rule_ids("Death did not occur.")


# Finding D1 (High) — negation scope is the ENTIRE sentence prefix.
# Input:    "No nausea was reported, but the patient required hospitalization."
# Expected: mandatory_reporting_context fires (hospitalization is affirmed).
# Actual:   no violations at all — _is_negated() scans everything before the
#           match in the sentence and finds the unrelated cue "No", so a real
#           escalation flag is silently suppressed (false negative).
def test_unrelated_negation_in_same_sentence_does_not_suppress_hospitalization():
    text = "No nausea was reported, but the patient required hospitalization."
    assert "mandatory_reporting_context" in rule_ids(text)


# Finding D9 (Medium) — follower-negation window is a fixed 40 characters.
# Input:    "Hospitalization, following a lengthy and complicated series of
#            clinical evaluations, was not required."
# Expected: no mandatory flag (the hospitalization was NOT required).
# Actual:   mandatory_reporting_context fires — "was not required" sits ~70
#           chars after the keyword, outside _is_negated()'s end+40 window,
#           and no preceder cue exists before the keyword (false positive).
def test_distant_follower_negation_suppresses_hospitalization():
    text = ("Hospitalization, following a lengthy and complicated series of "
            "clinical evaluations, was not required.")
    assert "mandatory_reporting_context" not in rule_ids(text)


# ---------------------------------------------------------------------------
# Off-label anchoring
# ---------------------------------------------------------------------------

def test_approved_for_the_stated_indication_no_offlabel():
    assert "off_label_promotion" not in rule_ids(
        "The medicine is approved for the stated indication.")


def test_mixed_anchored_and_promotional_sentences_offlabel_fires():
    """One compliant (anchored) sentence must not shield a violating one."""
    text = ("The drug is approved for hypertension in adults. "
            "It is also recommended for weight loss.")
    assert "off_label_promotion" in rule_ids(text)


# Finding D7 (High) — approval anchor exempts the WHOLE sentence.
# Input:    "Approved for hypertension, the drug is also recommended for
#            weight loss."
# Expected: off_label_promotion fires (the weight-loss claim is unanchored
#           promotion in its own clause).
# Actual:   no violations — _check_off_label() skips any sentence containing
#           an anchor, so a genuine off-label claim sharing a sentence with
#           label language is missed entirely (false negative on a core rule).
def test_anchor_does_not_exempt_unanchored_clause_in_same_sentence():
    text = "Approved for hypertension, the drug is also recommended for weight loss."
    assert "off_label_promotion" in rule_ids(text)


# ---------------------------------------------------------------------------
# Comparative claims
# ---------------------------------------------------------------------------

def test_better_than_every_competing_product_fires():
    assert "comparative_claims" in rule_ids(
        "The medicine is better than every competing product.")


def test_compared_to_in_methods_text_flags_for_review():
    """Documented behaviour: the comparative check has no context gating, so
    neutral methods language ('compared to the control arm') also flags.
    Accepted as by-design for a triage tool because medium severity routes to
    NEEDS_REVIEW (human review), never to FAIL — see workstream D report (c)."""
    assert "comparative_claims" in rule_ids(
        "In the analysis, response rates were compared to the historical control arm.")


# Finding D2 (Medium) — the comparative check ignores negation entirely.
# Input:    "The drug is not better than placebo."
# Expected: no comparative flag (the sentence DENIES superiority; this is
#           standard compliant trial language).
# Actual:   comparative_claims fires — _check_comparative() uses a raw
#           _term_pattern().search() and never calls _is_negated(), unlike
#           the AE / mandatory / off-label checks (false positive).
def test_negated_comparative_claim_no_flag():
    assert "comparative_claims" not in rule_ids("The drug is not better than placebo.")


# ---------------------------------------------------------------------------
# Word boundaries and morphology
# ---------------------------------------------------------------------------

def test_keyword_inside_unrelated_word_no_ae():
    """'rash' inside 'crashed' must not count (word-boundary matching)."""
    assert "adverse_event" not in rule_ids(
        "The truck crashed into the barrier during transport.")


def test_discontinued_is_ae_keyword_not_escalation_flag():
    """Documented behaviour: YAML deliberately lists 'discontinued' (AE
    keyword) and 'discontinuation' (escalation flag) as distinct tokens; the
    engine does not stem, so drug discontinuation alone raises the AE check,
    not the escalation. See workstream D report (c)."""
    ids = rule_ids("The patient discontinued the medication.")
    assert "adverse_event" in ids
    assert "mandatory_reporting_context" not in ids


# Finding D3 (Medium) — morphological variants (plurals) are missed.
# Inputs:   "The patient developed rashes after the second dose."
#           "Side effects were mild and transient."
# Expected: adverse_event fires for both ('rashes', 'side effects').
# Actual:   no violations — \b<token>\b requires the exact singular form, so
#           plural AE mentions, among the most common phrasings in real
#           reports, are missed (false negatives / recall gap).
def test_rashes_plural_fires_ae():
    assert "adverse_event" in rule_ids("The patient developed rashes after the second dose.")


def test_side_effects_plural_fires_ae():
    assert "adverse_event" in rule_ids("Side effects were mild and transient.")


# ---------------------------------------------------------------------------
# Seriousness flags: forms and spellings
# ---------------------------------------------------------------------------

def test_life_threatening_hyphenated_escalates():
    """YAML spells the flag 'life_threatening'; hyphenated text must match."""
    assert "mandatory_reporting_context" in rule_ids(
        "The patient suffered a life-threatening reaction and was admitted.")


# Finding D12 (Low) — the YAML's own literal spelling in text is missed.
# Input:    "The event was coded as life_threatening in the database."
# Expected: mandatory_reporting_context fires.
# Actual:   no violations — _term_pattern() joins word parts with [\s\-]+,
#           which does not include '_', so the canonical snake_case form
#           (plausible in text copied from coded data) never matches.
def test_life_threatening_underscore_literal_escalates():
    assert "mandatory_reporting_context" in rule_ids(
        "The event was coded as life_threatening in the database.")


# ---------------------------------------------------------------------------
# Privacy: identifier formats
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("phone", [
    "+1 (555) 123-4567",
    "5551234567",
    "555.123.4567",
    "(555) 123-4567",
])
def test_us_phone_formats_fire_privacy(phone):
    assert "privacy" in rule_ids(f"Reach the patient at {phone} today.")


@pytest.mark.parametrize("email", [
    "john.smith@example.com",
    "john_smith@hospital.org",
    "john.smith+study@example.co.uk",
    "JOHN.SMITH@EXAMPLE.COM",
])
def test_email_variants_fire_privacy(email):
    assert "privacy" in rule_ids(f"Send it to {email} please.")


def test_ssn_with_dashes_fires_privacy():
    assert "privacy" in rule_ids("The form lists the identifier 123-45-6789 in error.")


def test_dr_title_flags_privacy_documented_behaviour():
    """Documented conservative behaviour: the titled-name branch flags ANY
    'Dr. <Name>', including staff (here, a presenting investigator, not a
    patient). Accepted for a human-in-the-loop triage tool — a name is
    personal data, the flag routes to review, and the engine implements no
    context gating (config/rules.yaml's forbidden_contexts are unused).
    See workstream D report (c) for the full reasoning."""
    assert "privacy" in rule_ids("Dr. Patel presented the results at the conference.")


# Finding D4 (Medium) — space-separated national ID is missed.
# Input:    "The form lists the identifier 123 45 6789 in error."
# Expected: privacy fires (same SSN, spaces instead of dashes — a common
#           written variant).
# Actual:   no violations — NATIONAL_ID_PATTERN requires literal dashes and
#           the phone pattern cannot match the 3-2-4 grouping either
#           (false negative on a declared PII type).
def test_ssn_with_spaces_fires_privacy():
    assert "privacy" in rule_ids("The form lists the identifier 123 45 6789 in error.")


# Finding D5 (Medium) — phone detection is US-only in a multi-jurisdiction tool.
# Input:    "Contact the site at +91 98765 43210 for details."
# Expected: privacy fires (valid Indian mobile in international format; the
#           corpus and rules cover FDA + EMA + CDSCO jurisdictions).
# Actual:   no violations — PHONE_PATTERN only accepts an optional +1 with
#           3-3-4 grouping, or a bare run of 10-11 digits with no separators,
#           so spaced international formats are missed (false negative).
def test_international_phone_fires_privacy():
    assert "privacy" in rule_ids("Contact the site at +91 98765 43210 for details.")


# Finding D11 (Low) — obfuscated (spaced) email is missed.
# Input:    "Reach us at john.smith @ example.com for details."
# Expected: privacy fires (a common deliberate obfuscation of a real address).
# Actual:   no violations — EMAIL_PATTERN requires '@' adjacent to both parts.
def test_spaced_email_fires_privacy():
    assert "privacy" in rule_ids("Reach us at john.smith @ example.com for details.")


# Finding D10 (Low) — first-name-only patient reference is missed.
# Input:    "Patient John was admitted on Tuesday."
# Expected: privacy fires (an identified patient in a report).
# Actual:   no violations — PATIENT_NAME_PATTERN requires 2+ capitalised
#           words after 'patient'. NOTE: src/rule_engine.py documents this as
#           a deliberate recall trade-off; recorded here so the decision is
#           revisited explicitly rather than by accident.
@pytest.mark.xfail(strict=False, reason="D10: single first name after 'Patient' not detected (documented trade-off in rule_engine.py)")
def test_patient_first_name_only_fires_privacy():
    assert "privacy" in rule_ids("Patient John was admitted on Tuesday.")


# ---------------------------------------------------------------------------
# Case handling
# ---------------------------------------------------------------------------

def test_all_caps_ae_keyword_fires():
    """Keyword checks lowercase the text, so ALL-CAPS reports still match."""
    assert "adverse_event" in rule_ids("THE PATIENT REPORTED SEVERE NAUSEA.")


# Finding D6 (Medium) — ALL-CAPS patient names are missed.
# Input:    "PATIENT JOHN SMITH WAS ADMITTED ON MONDAY."
# Expected: privacy fires (report headers are very commonly ALL-CAPS).
# Actual:   no violations — PATIENT_NAME_PATTERN requires [Pp]atient followed
#           by [A-Z][a-z]+ mixed-case words; 'PATIENT' and 'JOHN SMITH' match
#           neither. The keyword checks lowercase first, the name pattern
#           does not, so case handling is inconsistent across rule families
#           (false negative). The fix must not resurrect the pre-2026-10-20
#           false positive ('patient' + any lowercase word).
def test_all_caps_patient_name_fires_privacy():
    assert "privacy" in rule_ids("PATIENT JOHN SMITH WAS ADMITTED ON MONDAY.")


# ---------------------------------------------------------------------------
# Quoted / cited text
# ---------------------------------------------------------------------------

# Finding D8 (Low) — no quotation or citation awareness.
# Input:    'The filing cites the guidance "Management of Nausea and Vomiting
#            in Adults" as its reference.'
# Expected: no adverse_event (the keywords occur inside a quoted guidance
#           title, not as events experienced by any patient).
# Actual:   adverse_event fires — the engine matches keywords anywhere in
#           the text, including quoted titles and citations (false positive).
@pytest.mark.xfail(strict=False, reason="D8: AE keywords inside quoted regulation/guidance titles trigger the AE check")
def test_ae_keyword_in_quoted_guidance_title_no_ae():
    text = ('The filing cites the guidance "Management of Nausea and Vomiting '
            'in Adults" as its reference.')
    assert "adverse_event" not in rule_ids(text)


# ---------------------------------------------------------------------------
# Degenerate inputs
# ---------------------------------------------------------------------------

def test_single_word_input():
    assert "adverse_event" in rule_ids("nausea")


def test_empty_input_is_clean():
    assert rule_ids("") == set()


def test_whitespace_only_input_is_clean():
    assert rule_ids("   ") == set()
