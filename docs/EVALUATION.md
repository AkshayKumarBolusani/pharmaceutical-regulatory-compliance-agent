# Evaluation

What has actually been measured for this project, how, and — just as
important — what has **not** been measured. This document keeps three kinds
of evidence strictly separate:

- **Class A — Unit and integration tests.** Does the implementation behave
  the way its specification says, case by case?
- **Class B — Synthetic benchmark.** How does the engine score on a small
  set of labelled synthetic cases?
- **Class C — Real-world validation.** How does it perform on real,
  independently labelled pharmaceutical documents?

**Class C does not exist for this project.** No real-world accuracy has
been established, and nothing in Class A or B implies it.

## Class A — Unit and integration tests

Run everything:

```bash
python -m pytest
```

Verified results (2026-10-20):

| Environment | Result |
|---|---|
| Full (chromadb + fastapi + openai installed) | **141 passed, 2 xfailed** |
| Minimal (pyyaml / pytest / pydantic / python-dotenv only) | **109 passed, 11 skipped, 2 xfailed** |

The 11 minimal-environment skips are tests that need the optional web /
retrieval / LLM packages; they skip cleanly rather than failing. The suite
covers: per-rule positives and negatives, negation and anchoring behaviour,
the API and CLI (including malformed, oversized and non-UTF-8 input),
security regressions (path traversal, CORS, error leakage, prompt
injection, verdict isolation from LLM output), retrieval against a small
synthetic index, the evaluation lab itself, the review log's hash chain,
and the source-diff tool.

The 2 xfails are documented deterministic limits, kept visible on purpose:

- **D8** — adverse-event keywords inside quoted text (e.g. a quoted
  guidance title such as "Management of Nausea and Vomiting in Adults")
  still trigger the AE check. The engine has no quotation awareness.
- **D10** — a patient referenced by a single first name only
  ("Patient John was admitted") is not detected. The privacy name pattern
  requires a capitalised first + last name (or a titled name) so that
  ordinary prose ("the patient experienced …") does not false-positive;
  the missed single-name case is the deliberate price of that.

## Class B — Synthetic benchmark (Feature-2 evaluation lab)

### How to run

```bash
python scripts/evaluate.py                                  # report to stdout
python scripts/evaluate.py --out-prefix evaluation/results/latest   # also write .md + .json
```

The lab runs the deterministic engine (rules only: no LLM, no vector
index) over `evaluation/labeled_cases.json`. The unit of analysis is **one
rule family on one case**: each of the 24 cases contributes exactly one
TP, FP, FN or TN per rule family (120 rule–case judgements in total).
Precision / recall / F1 are only reported where their denominator is
greater than zero.

### The dataset

24 synthetic cases. Every label is traced to an existing project artifact,
recorded in each case's `origin` field: the test fixtures in
`tests/fixtures/synthetic_reports.py`, the six seeded reports in
`synthetic_reports/` (with the expectations stated in that folder's
README), and inputs from adversarial / regression tests that pass. No
labels were invented for the benchmark, and no case is a real document.

### Results (verified 2026-10-20)

| Rule family | TP | FP | FN | TN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| `privacy` | 2 | 0 | 0 | 22 | 1.000 | 1.000 | 1.000 |
| `adverse_event` | 5 | 0 | 0 | 19 | 1.000 | 1.000 | 1.000 |
| `mandatory_reporting_context` | 3 | 0 | 0 | 21 | 1.000 | 1.000 | 1.000 |
| `off_label_promotion` | 3 | 0 | 0 | 21 | 1.000 | 1.000 | 1.000 |
| `comparative_claims` | 3 | 0 | 0 | 21 | 1.000 | 1.000 | 1.000 |
| **Total** | **16** | **0** | **0** | **104** | | | |

Document-status accuracy: **24/24**. Predicted NEEDS_REVIEW documents: 3.

### Read these numbers correctly — construction bias

The perfect scores above are **by construction, and are not evidence of
accuracy**. The labelled set is the project's own specification cases —
the fixtures, seeded reports and regression tests the rules were written
and fixed against. The benchmark therefore measures *regression
consistency*: that the implementation still agrees with its own
specification. Any future change that breaks a case will show up here as
an FP or FN, which is what the lab is for.

That the machinery itself can report imperfection is proven separately:
the lab's own test suite includes a stipulated mini-dataset in which one
rule is made to score precision = recall = 0.5, and the lab reports
exactly that.

### Adversarial battery

`tests/test_rule_engine_adversarial.py` holds 42 adversarial cases
(negations near real triggers, anchored label language mixed with
promotion, keywords inside unrelated words, identifier format variants,
ALL-CAPS text, and more). The audit behind it raised 12 findings
(D1–D12). Ten were confirmed defects and are fixed — including
sentence-wide negation suppressing an affirmed escalation flag (D1) and a
sentence-wide approval anchor exempting unrelated promotional clauses
(D7). The remaining two (D8, D10, above) are documented deterministic
limits and stay in the suite as xfails so they cannot be silently
forgotten.

Retrieval quality is likewise only smoke-tested: `tests/test_retrieval_synthetic.py`
verifies the index build and retrieval plumbing against a small synthetic
corpus. There is no labelled retrieval evaluation (no relevance judgements
for real queries), so no retrieval precision/recall is claimed.

## Class C — Real-world validation (does not exist)

Nothing in this project measures performance on real pharmaceutical
documents. Doing so would require, at minimum:

- a set of real documents the project is **authorised** to use (no real
  patient data exists in this repository, and none may be added);
- **independent labels** — rule-level and document-level judgements made
  by qualified reviewers who did not write the rules;
- a pre-agreed protocol (unit of analysis, denominators, how
  NEEDS_REVIEW is scored) and error analysis on the disagreements.

Until that exists, any statement of the form "the agent is X% accurate"
would be unfounded. The honest summary of the evidence today is: *the
implementation consistently does what its specification says on synthetic
cases (Class A + B); how that specification performs against real
documents and real regulatory practice is unmeasured (Class C).*
