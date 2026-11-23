# ASTA 2027 - Experimental Research Protocol

**Project:** Agentic AI Incident Copilot  
**Research area:** Trustworthy Agentic Workflows, Testing and Authorization  
**Target venue:** ASTA 2027 - IEEE ICST  
**Protocol version:** 1.0  
**Status:** Experimental design

---

## 1. Research objective

Systematically evaluate the reliability, security, and authorization boundaries of an agentic incident-response workflow.

The study investigates whether deterministic diagnosis, optional LLM explanations, exact-action authorization, human approval, and audit logging can be tested through reproducible software-engineering experiments.

The Agentic AI Incident Copilot will serve as the system under test.

## 2. Research questions

### RQ1 - Deterministic diagnosis

How consistently does the deterministic diagnosis component classify incident scenarios against independently established expected outcomes?

### RQ2 - LLM explanation reliability

Does optional LLM-assisted explanation preserve deterministic diagnosis and recommended actions when the model succeeds, fails, or returns unsupported information?

### RQ3 - Authorization integrity

How effectively does exact-action HMAC verification detect modified remediation actions and incorrect incident bindings?

### RQ4 - Human oversight and workflow reliability

Does the proposed architecture prevent unauthorized or duplicate remediation during approval rejection, replay, concurrency, and component failures?

## 3. Experimental configurations

| Configuration | Description |
|---|---|
| B1 | Deterministic diagnosis without LLM |
| B2 | Deterministic diagnosis with optional LLM explanation |
| B3 | Experiment-only workflow without independent HMAC integrity verification |
| P1 | Proposed workflow with deterministic diagnosis, optional LLM, HMAC integrity, human approval, audit logging, and simulation-only remediation |

B3 must be implemented as a separate experimental variant. The main application security implementation must remain unchanged.

## 4. Experimental hypotheses

**H1:** Deterministic diagnosis produces consistent classifications for scenarios whose expected outcomes are correctly specified.

**H2:** LLM explanation failures do not change deterministic diagnosis or recommended actions.

**H3:** Removing independent HMAC verification increases the number of modified actions accepted by the experimental workflow.

**H4:** The proposed architecture rejects unauthorized, modified, and replayed approval requests under the tested conditions.

These hypotheses must be evaluated using recorded experimental results. Do not assume they are confirmed before testing.

## 5. Dataset design

### Existing baseline

The existing dataset contains 20 synthetic incident scenarios:

- 8 payment dependency timeout scenarios.
- 6 HTTP 5xx unconfirmed scenarios.
- 6 insufficient evidence scenarios.

The existing B1 results are preliminary synthetic label-agreement results.

### Expanded dataset

Develop two separate datasets:

**Development dataset**

Used for implementation, debugging, and test refinement.

**Held-out evaluation dataset**

Used only for final evaluation after the diagnosis rules and experimental configurations are frozen.

Target: 60-100 scenarios if sufficient independent scenario coverage can be established.

### Scenario categories

1. Explicit payment dependency timeout.
2. Generic HTTP 504 gateway timeout.
3. HTTP 500, 502, and 503 errors.
4. Missing or conflicting telemetry.
5. Deployment timing inconsistencies.
6. Modified remediation actions.
7. Incorrect incident identifiers.
8. Missing approval.
9. Replayed approval requests.
10. Concurrent approval attempts.
11. LLM unavailable or failed.
12. Prometheus unavailable.
13. Graph execution failures.
14. Missing checkpoint information.
15. Audit and workflow failure conditions.

Every scenario must include:

- Scenario identifier.
- Scenario category.
- Input evidence or test conditions.
- Expected outcome.
- Expected recommended action, where applicable.
- Security or reliability property being evaluated.

Expected outcomes must be established independently of the implementation being tested. Document the labeling process and disagreements.

## 6. Experimental metrics

### Diagnosis metrics

- Classification agreement.
- Accuracy.
- Precision.
- Recall.
- Macro F1 score.
- Confusion matrix.

Use independently labeled held-out scenarios for claims about diagnostic performance.

### LLM metrics

- Successful explanation generation rate.
- Model failure rate.
- Mean, median, and percentile latency.
- Deterministic diagnosis preservation.
- Unsupported claim count.
- Evidence consistency assessment.

Define a reproducible explanation-review rubric before scoring outputs.

### Security metrics

- Action tamper rejection rate.
- Incorrect incident binding rejection rate.
- Replay rejection rate.
- Unauthorized execution count.
- Duplicate execution count.

### Workflow reliability metrics

- Approval enforcement rate.
- Rejection enforcement rate.
- Audit completeness.
- Failure recovery rate.
- End-to-end workflow latency.

Report numerators and denominators alongside percentages.

## 7. Security invariants

The following properties must be tested:

1. No remediation without explicit approval.
2. Rejected approval must not execute remediation.
3. Modified remediation actions must fail integrity verification.
4. Approval requests must not be replayable after completion.
5. Concurrent approval attempts must not cause duplicate execution.
6. LLM failure must not bypass deterministic findings or approval.
7. Remediation must remain simulation-only.
8. Relevant workflow decisions must be auditable.

A passing test demonstrates behavior under its tested conditions. It does not establish universal security.

## 8. Experimental procedure

For each experiment:

1. Record the source-code commit.
2. Record Python and dependency versions.
3. Record dataset version and scenario counts.
4. Record model name and configuration when applicable.
5. Execute the experiment using documented commands.
6. Save raw outputs in CSV or JSON.
7. Calculate metrics using version-controlled scripts.
8. Preserve failed runs and exceptions.
9. Repeat experiments where appropriate.
10. Document deviations from the protocol.

Repeated executions of the same scenario must not be treated as independent incident samples.

## 9. Reproducibility requirements

The research repository should contain:

- Application source code.
- Automated tests.
- Development dataset.
- Held-out evaluation dataset.
- Experiment configuration files.
- B1, B2, B3, and P1 runners.
- Raw experiment results.
- Metric calculation scripts.
- Environment and dependency documentation.
- Experimental execution instructions.

Never commit API keys, HMAC secrets, passwords, or private environment files.

## 10. Threats to validity

### Construct validity

Synthetic labels may not represent actual cloud incident causality. Metrics must be interpreted according to what they measure.

### Internal validity

Changes to diagnosis rules, datasets, model configurations, or test harnesses can influence experimental results. Record these changes.

### External validity

A single-process prototype and synthetic incident dataset do not establish production-scale reliability.

### Conclusion validity

Small scenario counts and repeated executions can create misleading confidence. Report sample counts and avoid unsupported generalizations.

## 11. Current implementation limitations

- Synthetic incident evidence.
- Heuristic deterministic diagnosis.
- Optional local LLM integration.
- Client-supplied reviewer identity.
- In-memory graph checkpointing.
- Single-process approval locking.
- Simulation-only remediation.
- No production-scale distributed testing.

These limitations must remain visible in the final manuscript.

## 12. Experimental completion criteria

An experiment is complete only when:

- Its objective and configuration are documented.
- Its input dataset is versioned.
- Its execution is reproducible.
- Its raw results are retained.
- Its metrics are calculated.
- Its failures are documented.
- Its limitations are stated.

The research paper must distinguish completed experiments from planned experiments.

---

**End of experimental protocol**