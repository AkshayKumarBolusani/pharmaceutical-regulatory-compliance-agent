"""
Phase 2 — Rule-based compliance engine (deterministic).
Uses config/rules.yaml only. No LLM. Returns violation_type, severity, evidence_text, rule_id.
"""

import re
from pathlib import Path
from typing import Any

import yaml


# --- PII/PHI pattern-based detection (no NER, no real data) ---
PHONE_PATTERN = re.compile(
    r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b|\b\d{10,11}\b"
)
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
# "Patient X Y" or "patient: John Smith" or "Mr. Smith" / "Mrs. Jones" (simple heuristic)
PATIENT_NAME_PATTERN = re.compile(
    r"\bpatient\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b|\b(?:Mr|Mrs|Ms|Dr)\.?\s+[A-Z][a-z]+\b",
    re.IGNORECASE,
)


def load_rules(rules_path: Path) -> dict[str, Any]:
    """Load rules from config/rules.yaml (read-only)."""
    with open(rules_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _check_privacy(text: str, rules: dict) -> list[dict]:
    """Detect PII/PHI patterns. Severity: critical."""
    out = []
    evidence_parts = []
    if PHONE_PATTERN.search(text):
        evidence_parts.append("phone number")
    if EMAIL_PATTERN.search(text):
        evidence_parts.append("email")
    if PATIENT_NAME_PATTERN.search(text):
        evidence_parts.append("patient/person name")
    if evidence_parts:
        out.append({
            "violation_type": "Patient Privacy Violation",
            "severity": "critical",
            "evidence_text": "PII/PHI detected: " + ", ".join(evidence_parts),
            "rule_id": "privacy",
        })
    return out


def _check_adverse_event(text: str, rules: dict) -> list[dict]:
    """AE trigger keywords present but no reporting context → high (non-compliance)."""
    ae = rules.get("adverse_event") or {}
    keywords = [k.strip().lower() for k in ae.get("trigger_keywords", [])]
    case_sensitive = ae.get("case_sensitive", False)
    text_check = text if case_sensitive else text.lower()
    found = [kw for kw in keywords if kw in text_check]
    if not found:
        return []
    # Reporting context = presence of mandatory_reporting escalation flags
    mrc = rules.get("mandatory_reporting_context") or {}
    flags = [f.strip().lower() for f in mrc.get("escalation_flags", [])]
    has_context = any(fl in text_check for fl in flags)
    if has_context:
        return []  # Handled by mandatory_reporting_context check
    return [{
        "violation_type": "Adverse Event Without Reporting Context",
        "severity": "high",
        "evidence_text": f"AE trigger keywords found ({', '.join(found[:5])}{'...' if len(found) > 5 else ''}); no reporting context (e.g. serious, hospitalization) provided.",
        "rule_id": "adverse_event",
    }]


def _check_mandatory_reporting(text: str, rules: dict) -> list[dict]:
    """Escalation flags present → mandatory reporting required (high)."""
    mrc = rules.get("mandatory_reporting_context") or {}
    flags = [f.strip().lower() for f in mrc.get("escalation_flags", [])]
    text_lower = text.lower()
    found = [f for f in flags if f in text_lower]
    if not found:
        return []
    return [{
        "violation_type": "Mandatory Reporting Required",
        "severity": "high",
        "evidence_text": f"Mandatory/expedited reporting flags present: {', '.join(found)}. Escalation required.",
        "rule_id": "mandatory_reporting_context",
    }]


def _check_off_label(text: str, rules: dict) -> list[dict]:
    """Off-label phrase patterns → high. We do not have approved-indication DB; phrase detection only."""
    ol = rules.get("off_label_promotion") or {}
    patterns = [p.strip().lower() for p in ol.get("phrase_patterns", [])]
    text_lower = text.lower()
    found = [p for p in patterns if p in text_lower]
    if not found:
        return []
    return [{
        "violation_type": "Off-Label Promotion",
        "severity": "high",
        "evidence_text": f"Promotional phrasing suggesting indication: {', '.join(found)}. Verify against approved indication.",
        "rule_id": "off_label_promotion",
    }]


def _check_comparative(text: str, rules: dict) -> list[dict]:
    """Comparative/superiority indicators → medium."""
    cc = rules.get("comparative_claims") or {}
    indicators = [i.strip().lower() for i in cc.get("indicators", [])]
    text_lower = text.lower()
    found = [i for i in indicators if i in text_lower]
    if not found:
        return []
    return [{
        "violation_type": "Improper Comparative Claim",
        "severity": "medium",
        "evidence_text": f"Comparative/superiority language: {', '.join(found)}. Requires substantiation.",
        "rule_id": "comparative_claims",
    }]


def run_checks(text: str, rules_path: Path) -> list[dict]:
    """
    Run all deterministic checks. Returns list of dicts with:
    violation_type, severity, evidence_text, rule_id.
    """
    rules = load_rules(rules_path)
    violations = []
    violations.extend(_check_privacy(text, rules))
    violations.extend(_check_adverse_event(text, rules))
    violations.extend(_check_mandatory_reporting(text, rules))
    violations.extend(_check_off_label(text, rules))
    violations.extend(_check_comparative(text, rules))
    return violations
