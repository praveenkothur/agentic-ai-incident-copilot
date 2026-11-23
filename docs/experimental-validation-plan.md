

\# Experimental Validation Plan



\## 1. Research Objective



Evaluate the effectiveness of an evidence-driven Agentic AI Incident Response architecture with human approval and an independent action-integrity verification boundary.



The experiments will compare four implementation approaches to determine their differences in diagnostic accuracy, approval enforcement, action integrity, latency, and failure handling.



\## 2. Experimental Baselines



\### B1. Deterministic Diagnosis Without LLM

\- Use deterministic evidence collection and diagnosis.

\- No LLM-generated explanation.

\- Establish baseline diagnostic accuracy and latency.



\### B2. LLM-Assisted Diagnosis

\- Use deterministic evidence with an optional local LLM explanation.

\- Evaluate whether LLM assistance improves diagnostic interpretation.

\- Measure latency and LLM failure behavior.



\### B3. Agent Workflow Without Independent Action-Integrity Gate

\- Execute the incident workflow with human approval.

\- Exclude independent HMAC verification of the proposed action.

\- Evaluate the effect of removing the action-integrity boundary.



\### P1. Proposed Evidence-Driven Architecture

\- Deterministic evidence collection and diagnosis.

\- Optional LLM explanation.

\- Explicit human approval.

\- HMAC-based action-integrity verification.

\- Audit logging.

\- Simulation-only remediation.



\## 3. Evaluation Metrics



| Metric | Evaluation Method |

|---|---|

| Diagnostic accuracy | Compare diagnosis against labeled incident ground truth |

| Action-integrity rejection rate | Measure modified actions rejected by verification |

| Approval enforcement | Verify remediation cannot proceed without approval |

| Replay protection | Test repeated approval requests |

| Concurrent approval safety | Test simultaneous approval requests |

| End-to-end latency | Measure incident investigation and approval workflow duration |

| LLM failure handling | Evaluate behavior during timeout and connection failure |

| Audit completeness | Verify required workflow events are recorded |



\## 4. Experimental Methodology



1\. Prepare a fixed dataset of simulated cloud incident scenarios.

2\. Assign ground-truth labels to each scenario.

3\. Execute every scenario against B1, B2, B3, and P1.

4\. Repeat experiments under consistent configurations.

5\. Record outputs, execution times, failures, and security outcomes.

6\. Compare results using consistent evaluation criteria.

7\. Preserve experiment configurations, test data, and raw results.



\## 5. Current Engineering Baseline



\- Automated tests: 39 passing.

\- Application code coverage: 100%.

\- Python version: 3.12.10.

\- Test framework: pytest 9.1.1.

\- Diagnosis: deterministic evidence-based analysis.

\- LLM: optional local Ollama integration.

\- Approval: human approval gate.

\- Integrity: HMAC-SHA256 action verification.

\- Audit: SQLite.

\- Remediation: simulation only.



\## 6. Research Limitations



\- Current implementation uses in-memory workflow checkpointing.

\- Pending approval state is process-local.

\- Reviewer identity is not independently authenticated.

\- Remediation is simulated and does not modify cloud infrastructure.

\- LLM tests using mocks do not establish actual model accuracy.

\- Production-scale performance and distributed concurrency have not been established.



\## 7. Expected Research Deliverables



\- Reproducible incident dataset.

\- Experimental configuration files.

\- Automated experiment runner.

\- Raw experimental results in CSV format.

\- Statistical comparison of baselines.

\- Evaluation charts and tables.

\- Research paper results and discussion.



\## 8. Research Integrity



All reported results must come from executed experiments. No accuracy, performance, or security improvement claims should be made without measured evidence.



